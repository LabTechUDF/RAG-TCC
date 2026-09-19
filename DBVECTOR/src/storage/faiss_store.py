"""
Store FAISS para busca vetorial local.
"""
import os
import logging
import faiss
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.storage.base import VectorStore
from src.schema import Doc, SearchResult
from src import embeddings, config

log = logging.getLogger(__name__)


def _gpu_available():
    """Verifica se FAISS tem suporte a GPU."""
    return hasattr(faiss, "StandardGpuResources")


def maybe_to_gpu(index):
    """
    Move índice FAISS para GPU se configurado e disponível.
    Fallback automático para CPU se houver erro ou GPU não disponível.
    """
    if not config.USE_FAISS_GPU:
        log.info("FAISS GPU desabilitado via config (USE_FAISS_GPU=false)")
        return index
    
    if not _gpu_available():
        log.warning("FAISS GPU não disponível nesta build; usando CPU.")
        return index
    
    try:
        res = faiss.StandardGpuResources()
        gpu_index = faiss.index_cpu_to_gpu(res, config.FAISS_GPU_DEVICE, index)
        log.info("FAISS index movido para GPU (device %d).", config.FAISS_GPU_DEVICE)
        return gpu_index
    except Exception as e:
        log.warning("Falha ao mover índice para GPU (%s); usando CPU.", e)
        return index


class FAISSStore(VectorStore):
    """Store FAISS com persistência local."""
    
    def __init__(self, index_path: str = None, metadata_path: str = None, lazy_metadata: bool = None):
        # Permite sobrescrever via variáveis de ambiente em tempo de execução
        self.index_path = index_path or os.getenv("FAISS_INDEX_PATH", config.FAISS_INDEX_PATH)
        self.metadata_path = metadata_path or os.getenv("FAISS_METADATA_PATH", config.FAISS_METADATA_PATH)
        self._index = None
        self.metadata = {}
        # Modo somente leitura com metadados mapeados em memória (para a API): evita carregar
        # centenas de milhares de textos como objetos Python (> 16 GB com ~730 mil documentos)
        if lazy_metadata is None:
            lazy_metadata = os.getenv("FAISS_LAZY_METADATA", "false").lower() in {"1", "true", "yes"}
        self.lazy_metadata = lazy_metadata
        self._meta_table = None
        self._sorted_ids = None
        self._sorted_rows = None
        
        # Cria diretórios se necessário
        Path(self.index_path).mkdir(parents=True, exist_ok=True)
        
        # Carrega index existente se houver
        self._load_index()
    
    def _get_index_file(self) -> str:
        """Retorna caminho do arquivo de índice FAISS."""
        return os.path.join(self.index_path, "index.faiss")
    
    def _load_index(self) -> None:
        """Carrega índice FAISS e metadados se existirem."""
        index_file = self._get_index_file()
        
        if os.path.exists(index_file):
            print(f"📁 Carregando índice FAISS: {index_file}")
            self._index = faiss.read_index(index_file)
            
            # Move para GPU se configurado
            self._index = maybe_to_gpu(self._index)

            # Carrega metadados
            if os.path.exists(self.metadata_path) and self.lazy_metadata:
                self._open_lazy_metadata()
            elif os.path.exists(self.metadata_path):
                df = pd.read_parquet(self.metadata_path)
                
                # Converte meta de string JSON de volta para dict
                if 'meta' in df.columns:
                    import ast
                    df['meta'] = df['meta'].apply(
                        lambda x: ast.literal_eval(x) if x and isinstance(x, str) else {}
                    )
                
                self.metadata = df.set_index('internal_id').to_dict('index')
                print(f"✅ Índice carregado! {len(self.metadata)} documentos")
            else:
                print("⚠️ Arquivo de metadados não encontrado")
        else:
            print("📝 Nenhum índice FAISS encontrado - será criado novo")
    
    def _open_lazy_metadata(self) -> None:
        """Abre os metadados como Arrow IPC mapeado em memória (somente leitura).

        Na primeira vez (ou se o parquet for mais novo) converte o parquet, row group por row group,
        para um arquivo Arrow sem compressão ao lado dele; depois só mapeia o arquivo, sem copiar os
        textos para a memória do processo (as páginas ficam no cache do sistema, recuperáveis).
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        cache = self.metadata_path + ".arrow"
        if not os.path.exists(cache) or os.path.getmtime(cache) < os.path.getmtime(self.metadata_path):
            print(f"🗂️ Convertendo metadados para Arrow (uma vez): {cache}")
            source = pq.ParquetFile(self.metadata_path)
            # Colunas totalmente vazias podem ter sido gravadas com tipo null
            schema = pa.schema([
                pa.field(f.name, pa.string() if pa.types.is_null(f.type) else f.type)
                for f in source.schema_arrow
            ])
            tmp = cache + ".tmp"
            with pa.OSFile(tmp, "wb") as sink, pa.ipc.new_file(sink, schema) as writer:
                for i in range(source.metadata.num_row_groups):
                    writer.write_table(source.read_row_group(i).cast(schema))
            os.replace(tmp, cache)

        self._meta_table = pa.ipc.open_file(pa.memory_map(cache, "r")).read_all()
        # Leitura por batch: juntar os chunks da coluna de texto estoura o limite de 2 GB do tipo string
        self._meta_batches = self._meta_table.to_batches()
        self._batch_starts = np.cumsum([0] + [b.num_rows for b in self._meta_batches])
        ids = self._meta_table.column("internal_id").to_numpy()
        order = np.argsort(ids, kind="stable")
        self._sorted_ids = ids[order]
        self._sorted_rows = order
        print(f"✅ Metadados mapeados (somente leitura): {self._meta_table.num_rows:,} documentos")

    def _lazy_lookup(self, internal_ids) -> Dict[int, Dict[str, Any]]:
        """Lê do Arrow mapeado apenas as linhas dos ids retornados pelo FAISS."""
        import ast
        import pyarrow as pa

        if self._sorted_ids is None or len(self._sorted_ids) == 0:
            return {}
        wanted = np.asarray([i for i in internal_ids if i != -1], dtype=np.int64)
        if wanted.size == 0:
            return {}
        pos = np.minimum(np.searchsorted(self._sorted_ids, wanted), len(self._sorted_ids) - 1)
        found = self._sorted_ids[pos] == wanted
        rows = self._sorted_rows[pos[found]]
        lookup = {}
        for row in rows:
            batch_index = int(np.searchsorted(self._batch_starts, row, side="right")) - 1
            local = int(row - self._batch_starts[batch_index])
            record = self._meta_batches[batch_index].slice(local, 1).to_pylist()[0]
            meta = record.get("meta")
            record["meta"] = ast.literal_eval(meta) if meta and isinstance(meta, str) else {}
            lookup[int(record["internal_id"])] = record
        return lookup

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Metadados completos de um documento pelo id textual (varre a coluna id, batch por batch)."""
        import ast
        import pyarrow.compute as pc

        if self._meta_table is None:
            for record in self.metadata.values():
                if record.get("id") == doc_id:
                    return record
            return None
        for batch in self._meta_batches:
            hits = pc.indices_nonzero(pc.equal(batch.column("id"), doc_id))
            if len(hits):
                record = batch.slice(hits[0].as_py(), 1).to_pylist()[0]
                meta = record.get("meta")
                record["meta"] = ast.literal_eval(meta) if meta and isinstance(meta, str) else {}
                return record
        return None

    def _save_index(self) -> None:
        """Salva índice FAISS e metadados no disco."""
        if self.lazy_metadata:
            raise RuntimeError("FAISSStore em modo somente leitura (FAISS_LAZY_METADATA); use src.tools.append_faiss para gravar")
        if self._index is None:
            return
        
        # Se o índice estiver na GPU, move para CPU antes de salvar
        index_to_save = self._index
        if _gpu_available() and isinstance(self._index, faiss.GpuIndex):
            log.info("Movendo índice de GPU para CPU antes de salvar...")
            index_to_save = faiss.index_gpu_to_cpu(self._index)
            
        index_file = self._get_index_file()
        print(f"💾 Salvando índice FAISS: {index_file}")
        faiss.write_index(index_to_save, index_file)

        # Salva metadados
        if self.metadata:
            df = pd.DataFrame.from_dict(self.metadata, orient='index')
            df.index.name = 'internal_id'
            df.reset_index(inplace=True)
            
            # Converte meta dict para JSON string (PyArrow não suporta struct vazio)
            if 'meta' in df.columns:
                df['meta'] = df['meta'].apply(lambda x: str(x) if x else None)
            
            df.to_parquet(self.metadata_path, index=False)
            print(f"💾 Metadados salvos: {self.metadata_path}")
    
    def _doc_to_internal_id(self, doc_id: str) -> int:
        """Converte ID do documento para ID interno FAISS (simples hash)."""
        return hash(doc_id) % (2**31 - 1)  # Positivo int32
    
    def index(self, docs: List[Doc]) -> None:
        """Indexa documentos no FAISS."""
        if not docs:
            return
            
        # Suprime mensagem repetitiva se muitos documentos
        if len(docs) > 100:
            log.info(f"Indexando {len(docs)} documentos no FAISS...")
        else:
            print(f"🔄 Indexando {len(docs)} documentos no FAISS...")
        
        if self.lazy_metadata:
            raise RuntimeError("FAISSStore em modo somente leitura (FAISS_LAZY_METADATA); use src.tools.append_faiss para indexar")

        # Gera embeddings
        texts = [doc.text for doc in docs]
        vectors = embeddings.encode_texts(texts)
        
        # Cria índice se não existir
        if self._index is None:
            dimension = vectors.shape[1]
            print(f"📊 Criando índice FAISS com dimensão {dimension}")
            
            # Usa IndexFlatIP para busca por produto interno (cosseno se normalizado)
            base_index = faiss.IndexFlatIP(dimension)
            # Usa IndexIDMap2 para manter mapeamento de IDs
            self._index = faiss.IndexIDMap2(base_index)
            
            # Move para GPU se configurado
            self._index = maybe_to_gpu(self._index)

        # Prepara IDs internos e metadados
        internal_ids = []
        for doc in docs:
            internal_id = self._doc_to_internal_id(doc.id)
            internal_ids.append(internal_id)
            
            # Armazena metadados
            self.metadata[internal_id] = {
                'id': doc.id,
                'title': doc.title,
                'text': doc.text,
                'court': doc.court,
                'code': doc.code,
                'article': doc.article,
                'date': doc.date,
                'meta': doc.meta
            }
        
        # Adiciona ao índice (em memória, sem salvar no disco)
        self._index.add_with_ids(vectors, np.array(internal_ids, dtype=np.int64))
        
        if len(docs) <= 100:
            print(f"✅ {len(docs)} documentos adicionados ao índice (não salvo ainda)")
    
    def save(self) -> None:
        """Salva índice e metadados no disco explicitamente."""
        self._save_index()
    
    def _filtered_internal_ids(self, id_prefix: Optional[str], court: Optional[str]) -> np.ndarray:
        """IDs internos dos documentos cujo id começa com id_prefix e/ou cujo tribunal é court (cache por filtro)."""
        import pyarrow.compute as pc

        cache = self.__dict__.setdefault("_filter_cache", {})
        key = (id_prefix or "", (court or "").upper())
        if key in cache:
            return cache[key]
        if self._meta_table is not None:
            parts = []
            for batch in self._meta_batches:
                mask = pc.starts_with(batch.column("id"), id_prefix) if id_prefix else None
                if court:
                    same_court = pc.equal(pc.utf8_upper(batch.column("court")), court.upper())
                    mask = same_court if mask is None else pc.and_(mask, same_court)
                parts.append(pc.filter(batch.column("internal_id"), pc.fill_null(mask, False)).to_numpy())
            ids = np.concatenate(parts).astype(np.int64) if parts else np.empty(0, dtype=np.int64)
        else:
            ids = np.array([iid for iid, r in self.metadata.items()
                            if (not id_prefix or str(r.get("id") or "").startswith(id_prefix))
                            and (not court or (r.get("court") or "").upper() == court.upper())], dtype=np.int64)
        if len(cache) >= 32:
            cache.pop(next(iter(cache)))
        cache[key] = ids
        return ids

    def search(self, query_vector: np.ndarray, k: int = 5, id_prefix: Optional[str] = None,
               court: Optional[str] = None) -> List[SearchResult]:
        """Busca documentos similares; id_prefix/court restringem a busca (exata) a esse subconjunto."""
        if self._index is None or self._index.ntotal == 0:
            print("⚠️ Índice vazio ou não inicializado")
            return []

        # Garante que query_vector é 2D
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        # Busca no FAISS (com seletor de IDs quando há filtro)
        if id_prefix or court:
            allowed = self._filtered_internal_ids(id_prefix, court)
            if allowed.size == 0:
                return []
            selector = faiss.IDSelectorBatch(allowed)
            scores, internal_ids = self._index.search(query_vector, k, params=faiss.SearchParameters(sel=selector))
        else:
            scores, internal_ids = self._index.search(query_vector, k)

        results = []
        lookup = self._lazy_lookup(internal_ids[0]) if self._meta_table is not None else None
        for score, internal_id in zip(scores[0], internal_ids[0]):
            if internal_id == -1:  # ID inválido
                continue
                
            doc_data = lookup.get(int(internal_id)) if lookup is not None else self.metadata.get(internal_id)
            if doc_data:
                doc = Doc(
                    id=doc_data['id'],
                    text=doc_data['text'],
                    title=doc_data['title'],
                    court=doc_data['court'],
                    code=doc_data['code'],
                    article=doc_data['article'],
                    date=doc_data['date'],
                    meta=doc_data['meta']
                )
                results.append(SearchResult(doc=doc, score=float(score)))
        
        return results
    
    def get_doc_count(self) -> int:
        """Retorna número de documentos indexados."""
        if self._index is None:
            return 0
        return self._index.ntotal
