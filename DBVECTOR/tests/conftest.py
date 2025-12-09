"""
Configuração de fixtures para testes.
"""
import os
import tempfile
import pytest
from typing import List
import numpy as np
from fastapi.testclient import TestClient

from src.schema import Doc, get_dummy_docs
from src import embeddings, config


@pytest.fixture
def search_backend():
    """Fixture que retorna backend de busca configurado."""
    return os.getenv("SEARCH_BACKEND", config.SEARCH_BACKEND)


@pytest.fixture
def client():
    """Fixture com TestClient da API FastAPI."""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def dummy_docs() -> List[Doc]:
    """Fixture com documentos dummy para testes."""
    return get_dummy_docs()


@pytest.fixture
def sample_doc() -> Doc:
    """Fixture com um documento simples para testes."""
    return Doc(
        id="test_doc_1",
        title="Documento de Teste",
        text="Este é um documento de teste para verificar funcionalidades do sistema RAG jurídico.",
        court="Teste",
        code="TEST",
        article="1",
        date="2024-01-01"
    )


@pytest.fixture
def dummy_vectors(dummy_docs) -> np.ndarray:
    """Fixture com embeddings dos documentos dummy."""
    texts = [doc.text for doc in dummy_docs]
    return embeddings.encode_texts(texts)


@pytest.fixture
def temp_faiss_path():
    """Fixture com diretório temporário para índices FAISS."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configura paths temporários via environment
        os.environ["FAISS_INDEX_PATH"] = temp_dir
        os.environ["FAISS_METADATA_PATH"] = os.path.join(temp_dir, "metadata.parquet")
        yield temp_dir
        # Limpa environment após teste
        os.environ.pop("FAISS_INDEX_PATH", None)
        os.environ.pop("FAISS_METADATA_PATH", None)


@pytest.fixture
def opensearch_test_index():
    """Fixture que retorna nome de índice de teste para OpenSearch."""
    return "test-juridico-docs"


@pytest.fixture
def query_vector() -> np.ndarray:
    """Fixture com vetor de query para testes."""
    return embeddings.encode_single_text("direitos fundamentais constitucionais")


def pytest_configure(config):
    """Configura markers customizados."""
    config.addinivalue_line(
        "markers", "opensearch: marca testes que requerem OpenSearch disponível"
    )


def pytest_collection_modifyitems(config, items):
    """
    Marca automaticamente para skip testes OpenSearch se container não disponível.
    """
    # Verifica se OpenSearch está disponível
    try:
        from opensearchpy import OpenSearch
        from src.config import get_opensearch_config
        
        os_config = get_opensearch_config()
        client = OpenSearch(**os_config, timeout=2)
        client.info()
        opensearch_available = True
    except Exception:
        opensearch_available = False
    
    # Aplica skip aos testes marcados como opensearch
    skip_opensearch = pytest.mark.skip(reason="OpenSearch não disponível")
    for item in items:
        if "opensearch" in item.keywords and not opensearch_available:
            item.add_marker(skip_opensearch)
