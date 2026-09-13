"""
Acrescenta documentos de um JSONL ao índice FAISS existente com memória limitada.

O build_faiss carrega todos os metadados num dict Python e monta um DataFrame inteiro para
salvar; com ~730 mil documentos isso passa de 20 GB e o processo é morto por falta de memória.

Aqui o pico fica perto de --memory-budget-gb (padrão 8 GB):
- os ids novos são conferidos lendo só as colunas id/internal_id;
- o índice FAISS recebe apenas os vetores novos, é gravado em .tmp e liberado da memória;
- os metadados são copiados row group por row group para um parquet novo, com leitura
  antecipada em paralelo dimensionada pelo orçamento de memória; as linhas novas vão no final;
- os arquivos .tmp só substituem os originais no final.

Uso (a partir de DBVECTOR):
    systemd-run --user --scope -p MemoryMax=10G -p MemorySwapMax=0 \\
      venv/bin/python -m src.tools.append_faiss --input ../legislacao_scraper/data/legislacao.jsonl
"""
import argparse
import gc
import json
import os
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Set

import faiss
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import config, embeddings
from src.schema import Doc

COLUMNS = ["internal_id", "id", "title", "text", "court", "code", "article", "date", "meta"]
SCHEMA = pa.schema([("internal_id", pa.int64())] + [(name, pa.string()) for name in COLUMNS[1:]])
MAX_INTERNAL_ID = 2**31 - 1
GB = 1024**3
# Ler um row group aloca mais que o tamanho descomprimido do rodapé (buffers de strings, cast)
READ_OVERHEAD = 2.0
# Processo Python + torch + modelo de embeddings já carregado
BASE_RESERVED = 1.5 * GB


def peak_rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2  # ru_maxrss em KB no Linux


def log(start: float, message: str) -> None:
    print(f"[{time.monotonic() - start:6.1f}s | pico {peak_rss_gb():4.1f} GB] {message}", flush=True)


def load_docs(path: str) -> List[Doc]:
    with open(path, "r", encoding="utf-8") as f:
        return [Doc.from_dict(json.loads(line)) for line in f if line.strip()]


def assign_internal_ids(docs: List[Doc], used: Set[int]) -> List[int]:
    """Mesmo esquema do FAISSStore (hash % 2^31-1), mas sem sobrescrever ids já usados."""
    internal_ids = []
    for doc in docs:
        internal_id = hash(doc.id) % MAX_INTERNAL_ID
        while internal_id in used:
            internal_id = (internal_id + 1) % MAX_INTERNAL_ID
        used.add(internal_id)
        internal_ids.append(internal_id)
    return internal_ids


def plan_readahead(metadata: pq.FileMetaData, budget: int, reserved: int, max_readahead: int) -> int:
    largest = max(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))
    readahead = int((budget - reserved) // (largest * READ_OVERHEAD))
    if readahead < 1:
        print(f"⚠️  Maior row group tem {largest / GB:.1f} GB descomprimido: não cabe no orçamento de "
              f"{budget / GB:.1f} GB. Seguindo com 1 por vez (o pico vai passar do orçamento).")
    return max(1, min(readahead, max_readahead, metadata.num_row_groups))


def copy_row_groups(path: Path, writer: pq.ParquetWriter, readahead: int, row_group_size: int) -> int:
    """Copia os row groups em ordem, lendo até `readahead` deles em paralelo."""
    num_row_groups = pq.ParquetFile(path).metadata.num_row_groups

    def read(i: int) -> pa.Table:
        # Um ParquetFile por thread: o leitor não é garantidamente thread-safe
        table = pq.ParquetFile(path).read_row_group(i, columns=COLUMNS)
        # Colunas vazias podem ter sido gravadas com tipo null
        return table.cast(SCHEMA).replace_schema_metadata(None)

    rows = 0
    with ThreadPoolExecutor(max_workers=readahead) as pool:
        for start in range(0, num_row_groups, readahead):
            futures = [pool.submit(read, i) for i in range(start, min(start + readahead, num_row_groups))]
            for n, future in enumerate(futures):
                table = future.result()
                futures[n] = None  # libera o resultado assim que for gravado
                writer.write_table(table, row_group_size=row_group_size)
                rows += table.num_rows
                del table
    return rows


def main():
    parser = argparse.ArgumentParser(description="Acrescenta documentos ao índice FAISS com memória limitada")
    parser.add_argument("--input", required=True, help="Arquivo JSONL com os documentos novos")
    parser.add_argument("--index-path", default=os.getenv("FAISS_INDEX_PATH", config.FAISS_INDEX_PATH))
    parser.add_argument("--metadata-path", default=os.getenv("FAISS_METADATA_PATH", config.FAISS_METADATA_PATH))
    parser.add_argument("--memory-budget-gb", type=float, default=8.0, help="Orçamento de memória para dimensionar a leitura paralela")
    parser.add_argument("--max-readahead", type=int, default=6, help="Máximo de row groups lidos em paralelo")
    parser.add_argument("--row-group-size", type=int, default=50_000, help="Linhas por row group no parquet regravado")
    parser.add_argument("--dry-run", action="store_true", help="Faz tudo menos gravar os arquivos")
    args = parser.parse_args()

    start = time.monotonic()
    index_file = Path(args.index_path) / "index.faiss"
    metadata_file = Path(args.metadata_path)
    budget = int(args.memory_budget_gb * GB)

    docs = load_docs(args.input)
    new_ids = [doc.id for doc in docs]
    if len(set(new_ids)) != len(new_ids):
        sys.exit("❌ O JSONL tem ids repetidos")
    log(start, f"📄 {len(docs):,} documentos em {args.input}")

    # Só as colunas pequenas: evita carregar o texto dos documentos existentes
    ids_table = pq.read_table(metadata_file, columns=["internal_id", "id"])
    existing_ids = set(ids_table.column("id").to_pylist())
    used_internal_ids = set(ids_table.column("internal_id").to_pylist())
    del ids_table
    already = [doc_id for doc_id in new_ids if doc_id in existing_ids]
    if already:
        sys.exit(f"❌ {len(already)} ids já estão no índice (ex.: {already[:3]}). Restaure o backup antes de reindexar.")
    del existing_ids
    internal_ids = assign_internal_ids(docs, used_internal_ids)
    log(start, f"🔎 {len(used_internal_ids) - len(docs):,} ids existentes conferidos")
    del used_internal_ids

    vectors = np.asarray(embeddings.encode_texts([doc.text for doc in docs]), dtype=np.float32)
    # O modelo fica num singleton; não precisamos mais dele
    embeddings._model = None
    gc.collect()
    log(start, f"🧠 {len(docs):,} embeddings gerados")

    index = faiss.read_index(str(index_file))
    if vectors.shape[1] != index.d:
        sys.exit(f"❌ Dimensão dos embeddings ({vectors.shape[1]}) diferente da do índice ({index.d})")
    previous_total = index.ntotal
    index.add_with_ids(vectors, np.array(internal_ids, dtype=np.int64))
    total = index.ntotal
    del vectors
    log(start, f"➕ Índice: {previous_total:,} → {total:,} vetores")

    new_rows = pa.table(
        {
            "internal_id": pa.array(internal_ids, pa.int64()),
            "id": new_ids,
            "title": [doc.title for doc in docs],
            "text": [doc.text for doc in docs],
            "court": [doc.court for doc in docs],
            "code": [doc.code for doc in docs],
            "article": [doc.article for doc in docs],
            "date": [doc.date for doc in docs],
            # Mesmo formato do FAISSStore: dict serializado com str(), lido de volta com ast.literal_eval
            "meta": [str(doc.meta) if doc.meta else None for doc in docs],
        },
        schema=SCHEMA,
    )
    del docs

    source = pq.ParquetFile(metadata_file)
    readahead = plan_readahead(source.metadata, budget, BASE_RESERVED + new_rows.nbytes, args.max_readahead)
    log(start, f"📚 Metadados: {source.metadata.num_rows:,} linhas em {source.metadata.num_row_groups} row groups; "
               f"lendo {readahead} em paralelo (orçamento {args.memory_budget_gb:.1f} GB)")
    del source

    if args.dry_run:
        log(start, "⚠️  --dry-run: nada foi gravado")
        return

    tmp_index = index_file.with_name(index_file.name + ".tmp")
    tmp_metadata = metadata_file.with_name(metadata_file.name + ".tmp")
    faiss.write_index(index, str(tmp_index))
    del index
    gc.collect()
    log(start, f"💾 {tmp_index} gravado e índice liberado da memória")

    try:
        with pq.ParquetWriter(tmp_metadata, SCHEMA) as writer:
            copied = copy_row_groups(metadata_file, writer, readahead, args.row_group_size)
            writer.write_table(new_rows, row_group_size=args.row_group_size)
    except BaseException:
        tmp_metadata.unlink(missing_ok=True)
        tmp_index.unlink(missing_ok=True)
        raise
    log(start, f"💾 {tmp_metadata} gravado ({copied:,} + {new_rows.num_rows:,} linhas)")

    written_rows = pq.ParquetFile(tmp_metadata).metadata.num_rows
    if written_rows != copied + new_rows.num_rows:
        tmp_metadata.unlink(missing_ok=True)
        tmp_index.unlink(missing_ok=True)
        sys.exit(f"❌ Parquet gravado tem {written_rows:,} linhas, esperado {copied + new_rows.num_rows:,}")

    os.replace(tmp_metadata, metadata_file)
    os.replace(tmp_index, index_file)
    log(start, f"✅ Concluído: {total:,} vetores | {written_rows:,} linhas de metadados")


if __name__ == "__main__":
    main()
