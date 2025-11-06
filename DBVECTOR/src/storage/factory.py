"""
Factory para criar stores baseado na configuração.
"""
from src.storage.base import VectorStore
from src.storage.faiss_store import FAISSStore
from src.storage.opensearch_store import OpenSearchStore
from src import config


def get_store() -> VectorStore:
    """
    Retorna store configurado baseado em SEARCH_BACKEND.
    
    Returns:
        Instância de VectorStore (FAISS ou OpenSearch)
    """
    backend = config.SEARCH_BACKEND.lower()
    
    if backend == "faiss":
        print(f"🔧 Usando backend FAISS: {config.FAISS_INDEX_PATH}")
        return FAISSStore()
    
    elif backend == "opensearch":
        print(f"🔧 Usando backend OpenSearch: {config.OPENSEARCH_HOST}:{config.OPENSEARCH_PORT}")
        return OpenSearchStore()
    
    else:
        raise ValueError(f"Backend não suportado: {backend}. Use 'faiss' ou 'opensearch'")


def get_faiss_store(index_path: str = None, metadata_path: str = None) -> FAISSStore:
    """Retorna store FAISS específico (útil para testes)."""
    return FAISSStore(index_path=index_path, metadata_path=metadata_path)


def get_opensearch_store(index_name: str = None) -> OpenSearchStore:
    """Retorna store OpenSearch específico (útil para testes).""" 
    return OpenSearchStore(index_name=index_name)