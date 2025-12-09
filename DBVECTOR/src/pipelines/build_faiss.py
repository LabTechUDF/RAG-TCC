"""
Pipeline para indexar documentos no FAISS.

OTIMIZAÇÕES:
- Batch buffer: acumula múltiplos batches antes de salvar no disco
- Salvamento periódico: reduz I/O salvando a cada N documentos
- Batch size configurável: permite ajuste fino do processamento
- Checkpoint automático: salva progresso em intervalos regulares
"""
import sys
import json
import os
from pathlib import Path
from tqdm import tqdm
from typing import List, Iterator

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.factory import get_faiss_store
from src.schema import get_dummy_docs, Doc


def load_docs_from_jsonl(file_path: str, batch_size: int = 1000) -> Iterator[List[Doc]]:
    """
    Carrega documentos de um arquivo JSONL em batches.
    
    Args:
        file_path: Caminho para o arquivo JSONL
        batch_size: Número de documentos por batch
        
    Yields:
        Lista de documentos Doc
    """
    batch = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
                
            try:
                data = json.loads(line)
                doc = Doc.from_dict(data)
                batch.append(doc)
                
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
                    
            except Exception as e:
                print(f"⚠️ Erro ao processar linha: {e}")
                continue
    
    # Yield remaining docs
    if batch:
        yield batch


def main():
    """Indexa documentos no FAISS com otimizações de performance."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Indexar documentos no FAISS")
    parser.add_argument(
        "--input",
        type=str,
        default="data/merged_clean.jsonl",
        help="Arquivo JSONL de entrada (default: data/merged_clean.jsonl)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("FAISS_BUILD_BATCH_SIZE", "1000")),
        help="Número de documentos por batch de embedding"
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=int(os.getenv("FAISS_SAVE_EVERY", "10000")),
        help="Salvar índice a cada N documentos (0 = apenas no final)"
    )
    parser.add_argument(
        "--buffer-batches",
        type=int,
        default=int(os.getenv("FAISS_BUFFER_BATCHES", "10")),
        help="Número de batches a acumular antes de adicionar ao índice"
    )
    parser.add_argument(
        "--dummy",
        action="store_true",
        help="Usar dados dummy para testes"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Não salvar índice (útil para benchmarks)"
    )
    
    args = parser.parse_args()
    
    print("🚀 Iniciando pipeline de build FAISS (OTIMIZADO)...")
    print(f"⚙️  Configurações:")
    print(f"   • Batch size: {args.batch_size} docs")
    print(f"   • Buffer: {args.buffer_batches} batches")
    print(f"   • Save every: {args.save_every if args.save_every > 0 else 'apenas no final'}")
    
    # Cria store FAISS
    store = get_faiss_store()
    
    if args.dummy:
        # Carrega documentos dummy
        docs = get_dummy_docs()
        print(f"📄 Carregados {len(docs)} documentos dummy")
        
        # Indexa documentos  
        store.index(docs)
        
        print(f"✅ Pipeline concluído! {store.get_doc_count()} documentos indexados")
        
        # Mostra resumo dos documentos
        print("\n📋 Documentos indexados:")
        for doc in docs:
            print(f"  • {doc.id}: {doc.title}")
    else:
        # Carrega de arquivo
        print(f"📁 Arquivo de entrada: {args.input}")
        
        # Verifica se arquivo existe
        if not Path(args.input).exists():
            print(f"❌ Arquivo não encontrado: {args.input}")
            sys.exit(1)
        
        # Conta total de linhas para progresso
        print("📊 Contando documentos...")
        with open(args.input, 'r', encoding='utf-8') as f:
            total_lines = sum(1 for line in f if line.strip())
        print(f"📄 Total de documentos: {total_lines:,}")
        
        # Processa documentos em batches com buffer
        total_indexed = 0
        buffer = []
        last_save_count = 0
        
        with tqdm(total=total_lines, desc="Indexando", unit="docs") as pbar:
            for batch in load_docs_from_jsonl(args.input, batch_size=args.batch_size):
                buffer.extend(batch)
                total_indexed += len(batch)
                pbar.update(len(batch))
                
                # Quando buffer atinge o tamanho desejado, indexa
                if len(buffer) >= (args.batch_size * args.buffer_batches):
                    store.index(buffer)
                    buffer = []
                    
                    # Checkpoint periódico (salvamento)
                    if args.save_every > 0 and (total_indexed - last_save_count) >= args.save_every:
                        if not args.no_save:
                            pbar.set_postfix_str("💾 salvando checkpoint...")
                            store.save()
                            last_save_count = total_indexed
                            pbar.set_postfix_str("")
            
            # Indexa documentos restantes no buffer
            if buffer:
                store.index(buffer)
        
        # Salvamento final
        if not args.no_save:
            print("💾 Salvando índice final...")
            store.save()
        
        print(f"\n✅ Pipeline concluído!")
        print(f"📊 Total indexado: {total_indexed:,} documentos")
        print(f"📊 Documentos no índice: {store.get_doc_count():,}")
        
        if args.no_save:
            print("⚠️  Índice NÃO foi salvo (modo --no-save)")


if __name__ == "__main__":
    main()