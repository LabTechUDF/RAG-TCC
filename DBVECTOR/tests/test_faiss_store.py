"""
Testes para FAISS store.
"""
import os
import pytest
import numpy as np

from src.storage.faiss_store import FAISSStore
from src.schema import Doc


def test_faiss_store_init(temp_faiss_path):
    """Testa inicialização do FAISS store."""
    store = FAISSStore(index_path=temp_faiss_path)
    assert store.index_path == temp_faiss_path
    assert store.get_doc_count() == 0


def test_faiss_store_index_and_search(temp_faiss_path, dummy_docs):
    """Testa indexação e busca no FAISS."""
    store = FAISSStore(
        index_path=temp_faiss_path,
        metadata_path=os.path.join(temp_faiss_path, "test_metadata.parquet")
    )
    
    # Indexa documentos
    store.index(dummy_docs)
    assert store.get_doc_count() == len(dummy_docs)
    
    # Testa busca
    from src import embeddings
    query_vector = embeddings.encode_single_text("direitos fundamentais")
    results = store.search(query_vector, k=3)
    
    assert len(results) > 0
    assert len(results) <= 3
    
    # Verifica estrutura dos resultados
    for result in results:
        assert hasattr(result, 'doc')
        assert hasattr(result, 'score')
        assert isinstance(result.score, float)
        assert result.doc.id in [doc.id for doc in dummy_docs]


def test_faiss_store_persistence(temp_faiss_path, sample_doc):
    """Testa persistência do índice FAISS."""
    metadata_path = os.path.join(temp_faiss_path, "test_metadata.parquet")
    
    # Cria store e indexa
    store1 = FAISSStore(index_path=temp_faiss_path, metadata_path=metadata_path)
    store1.index([sample_doc])
    assert store1.get_doc_count() == 1
    
    # Cria novo store no mesmo path - deve carregar índice existente
    store2 = FAISSStore(index_path=temp_faiss_path, metadata_path=metadata_path)
    assert store2.get_doc_count() == 1
    
    # Busca deve retornar o documento
    from src import embeddings
    query_vector = embeddings.encode_single_text(sample_doc.text)
    results = store2.search(query_vector, k=1)
    
    assert len(results) == 1
    assert results[0].doc.id == sample_doc.id


def test_faiss_store_empty_search(temp_faiss_path):
    """Testa busca em store vazio."""
    store = FAISSStore(index_path=temp_faiss_path)
    
    from src import embeddings
    query_vector = embeddings.encode_single_text("qualquer query")
    results = store.search(query_vector, k=5)
    
    assert results == []


def test_faiss_store_doc_to_internal_id(temp_faiss_path):
    """Testa conversão de IDs de documento para IDs internos."""
    store = FAISSStore(index_path=temp_faiss_path)
    
    # Testa conversão determinística
    doc_id = "test_doc_123"
    internal_id1 = store._doc_to_internal_id(doc_id)
    internal_id2 = store._doc_to_internal_id(doc_id)
    
    assert internal_id1 == internal_id2
    assert isinstance(internal_id1, int)
    assert internal_id1 >= 0  # Deve ser positivo
    
    # IDs diferentes devem gerar internals diferentes
    different_id = "test_doc_456"
    different_internal = store._doc_to_internal_id(different_id)
    assert different_internal != internal_id1


def test_faiss_store_query_vector_shapes(temp_faiss_path, sample_doc):
    """Testa busca com diferentes formatos de vetor."""
    store = FAISSStore(index_path=temp_faiss_path)
    store.index([sample_doc])
    
    from src import embeddings
    
    # Vetor 1D
    query_vector_1d = embeddings.encode_single_text("teste")
    results_1d = store.search(query_vector_1d, k=1)
    assert len(results_1d) == 1
    
    # Vetor 2D (1, dim)
    query_vector_2d = query_vector_1d.reshape(1, -1)
    results_2d = store.search(query_vector_2d, k=1)
    assert len(results_2d) == 1
    
    # Resultados devem ser idênticos
    assert results_1d[0].doc.id == results_2d[0].doc.id
    assert abs(results_1d[0].score - results_2d[0].score) < 1e-6