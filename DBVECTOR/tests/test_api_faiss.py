"""
Testes de integração para API com backend FAISS.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Força uso do FAISS para estes testes
os.environ["SEARCH_BACKEND"] = "faiss"

from src.api.main import app
from src.storage.factory import get_faiss_store
from src.schema import get_dummy_docs


@pytest.fixture
def test_client():
    """Cliente de teste para FastAPI."""
    return TestClient(app)


@pytest.fixture
def setup_faiss_with_data():
    """Configura FAISS temporário com dados dummy."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configura paths temporários
        os.environ["FAISS_INDEX_PATH"] = temp_dir
        os.environ["FAISS_METADATA_PATH"] = os.path.join(temp_dir, "metadata.parquet")
        
        # Indexa dados dummy
        store = get_faiss_store()
        docs = get_dummy_docs()
        store.index(docs)
        
        yield temp_dir
        
        # Cleanup
        os.environ.pop("FAISS_INDEX_PATH", None)
        os.environ.pop("FAISS_METADATA_PATH", None)


def test_api_root(test_client):
    """Testa endpoint raiz."""
    response = test_client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data
    assert "backend" in data
    assert data["backend"] == "faiss"


def test_api_health_no_data(test_client):
    """Testa health check sem dados indexados."""
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["FAISS_INDEX_PATH"] = temp_dir
        os.environ["FAISS_METADATA_PATH"] = os.path.join(temp_dir, "metadata.parquet")
        
        # Cria novo cliente para reinicializar store
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["backend"] == "faiss"
            assert data["documents"] == 0
        
        # Cleanup
        os.environ.pop("FAISS_INDEX_PATH", None)
        os.environ.pop("FAISS_METADATA_PATH", None)


def test_api_health_with_data(setup_faiss_with_data):
    """Testa health check com dados indexados."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["documents"] > 0


def test_api_search_no_data(test_client):
    """Testa busca sem dados indexados."""
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["FAISS_INDEX_PATH"] = temp_dir
        os.environ["FAISS_METADATA_PATH"] = os.path.join(temp_dir, "metadata.parquet")
        
        with TestClient(app) as client:
            response = client.post("/search", json={"q": "teste", "k": 5})
            assert response.status_code == 404
            assert "Nenhum documento indexado" in response.json()["detail"]
        
        # Cleanup
        os.environ.pop("FAISS_INDEX_PATH", None)
        os.environ.pop("FAISS_METADATA_PATH", None)


def test_api_search_with_data(setup_faiss_with_data):
    """Testa busca com dados indexados."""
    with TestClient(app) as client:
        # Busca simples
        response = client.post("/search", json={"q": "direitos fundamentais", "k": 3})
        assert response.status_code == 200
        
        data = response.json()
        assert "query" in data
        assert "total" in data
        assert "backend" in data
        assert "results" in data
        
        assert data["query"] == "direitos fundamentais"
        assert data["backend"] == "faiss"
        assert data["total"] > 0
        assert len(data["results"]) <= 3
        
        # Verifica estrutura dos resultados
        for result in data["results"]:
            assert "id" in result
            assert "text" in result
            assert "score" in result
            assert isinstance(result["score"], float)


def test_api_search_parameter_validation(setup_faiss_with_data):
    """Testa validação de parâmetros da busca."""
    with TestClient(app) as client:
        # Teste sem query
        response = client.post("/search", json={"k": 5})
        assert response.status_code == 422
        
        # Teste com k inválido (muito alto)
        response = client.post("/search", json={"q": "teste", "k": 25})
        assert response.status_code == 422
        
        # Teste com k inválido (negativo)
        response = client.post("/search", json={"q": "teste", "k": -1})
        assert response.status_code == 422
        
        # Teste válido com k=1
        response = client.post("/search", json={"q": "teste", "k": 1})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) <= 1


def test_api_search_different_queries(setup_faiss_with_data):
    """Testa busca com diferentes tipos de consulta."""
    with TestClient(app) as client:
        queries = [
            "constituição federal",
            "habeas corpus",
            "prescrição civil",
            "direito consumidor"
        ]
        
        for query in queries:
            response = client.post("/search", json={"q": query, "k": 2})
            assert response.status_code == 200
            
            data = response.json()
            assert data["query"] == query
            assert data["total"] >= 0
            
            # Se houver resultados, verifica estrutura
            if data["total"] > 0:
                for result in data["results"]:
                    assert "id" in result
                    assert "score" in result
                    assert result["score"] > 0


def test_api_search_empty_query(setup_faiss_with_data):
    """Testa busca com query vazia."""
    with TestClient(app) as client:
        response = client.post("/search", json={"q": "", "k": 5})
        assert response.status_code == 422  # Query não pode ser vazia