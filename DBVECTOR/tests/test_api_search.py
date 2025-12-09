"""
Testes para API de busca (/search endpoint).
"""
import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client):
    """Testa endpoint raiz."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data
    assert "backend" in data
    assert "endpoints" in data


def test_health_endpoint(client):
    """Testa endpoint de health check."""
    response = client.get("/health")
    
    # Pode retornar 200 (se há docs) ou 503 (se não inicializou)
    assert response.status_code in [200, 503]
    
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "backend" in data
        assert "documents" in data


def test_search_valid_query(client):
    """Testa busca com query válida."""
    payload = {
        "q": "direitos fundamentais",
        "k": 5
    }
    
    response = client.post("/search", json=payload)
    
    # Se não há documentos, retorna 404, caso contrário 200
    if response.status_code == 404:
        # Sem documentos indexados
        data = response.json()
        assert "detail" in data
        assert "indexado" in data["detail"].lower()
    else:
        assert response.status_code == 200
        data = response.json()
        
        # Verifica estrutura da resposta
        assert "query" in data
        assert "total" in data
        assert "backend" in data
        assert "results" in data
        
        assert data["query"] == "direitos fundamentais"
        assert isinstance(data["results"], list)
        assert len(data["results"]) <= 5
        
        # Verifica estrutura dos resultados
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "id" in result
            assert "text" in result
            assert "score" in result
            assert isinstance(result["score"], (int, float))


def test_search_empty_query(client):
    """Testa busca com query vazia."""
    payload = {
        "q": "",
        "k": 5
    }
    
    response = client.post("/search", json=payload)
    assert response.status_code == 422  # Validation error


def test_search_query_only_spaces(client):
    """Testa busca com query contendo apenas espaços."""
    payload = {
        "q": "   ",
        "k": 5
    }
    
    response = client.post("/search", json=payload)
    # Pode ser 422 (validação Pydantic) ou 422 (validação adicional no endpoint)
    assert response.status_code == 422


def test_search_with_k_parameter(client):
    """Testa busca com diferentes valores de k."""
    # k = 1
    response = client.post("/search", json={"q": "teste", "k": 1})
    if response.status_code == 200:
        data = response.json()
        assert len(data["results"]) <= 1
    
    # k = 10
    response = client.post("/search", json={"q": "teste", "k": 10})
    if response.status_code == 200:
        data = response.json()
        assert len(data["results"]) <= 10


def test_search_k_out_of_range(client):
    """Testa busca com k fora do intervalo permitido."""
    # k = 0 (inválido)
    response = client.post("/search", json={"q": "teste", "k": 0})
    assert response.status_code == 422
    
    # k = 21 (acima do máximo)
    response = client.post("/search", json={"q": "teste", "k": 21})
    assert response.status_code == 422
    
    # k negativo
    response = client.post("/search", json={"q": "teste", "k": -1})
    assert response.status_code == 422


def test_search_missing_query(client):
    """Testa busca sem campo q."""
    payload = {"k": 5}
    response = client.post("/search", json=payload)
    assert response.status_code == 422


def test_search_response_fields(client):
    """Testa que resposta contém todos os campos esperados."""
    payload = {"q": "direitos fundamentais", "k": 5}
    response = client.post("/search", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        
        # Campos obrigatórios da resposta
        required_fields = ["query", "total", "backend", "results"]
        for field in required_fields:
            assert field in data
        
        # Verifica campos dos resultados
        if len(data["results"]) > 0:
            result = data["results"][0]
            
            # Campos obrigatórios do resultado
            assert "id" in result
            assert "text" in result
            assert "score" in result
            
            # Campos opcionais (podem estar presentes ou não)
            optional_fields = ["title", "court", "code", "article", "date", "meta"]
            # Apenas verifica que se existem, são do tipo correto
            if "title" in result and result["title"] is not None:
                assert isinstance(result["title"], str)


def test_search_score_ordering(client):
    """Testa que resultados estão ordenados por score (descendente)."""
    payload = {"q": "direitos fundamentais", "k": 10}
    response = client.post("/search", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        results = data["results"]
        
        if len(results) > 1:
            # Verifica ordem decrescente de score
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)


def test_search_different_queries(client):
    """Testa busca com diferentes queries."""
    queries = [
        "constituição federal",
        "habeas corpus",
        "direito do consumidor",
        "prescrição decadência"
    ]
    
    for query in queries:
        payload = {"q": query, "k": 5}
        response = client.post("/search", json=payload)
        
        # Aceita 200 (sucesso) ou 404 (sem documentos)
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["query"] == query


def test_search_unicode_query(client):
    """Testa busca com caracteres unicode."""
    payload = {
        "q": "direção ação São Paulo",
        "k": 5
    }
    
    response = client.post("/search", json=payload)
    assert response.status_code in [200, 404]


def test_search_long_query(client):
    """Testa busca com query longa."""
    long_query = " ".join(["palavra"] * 100)
    payload = {
        "q": long_query,
        "k": 5
    }
    
    response = client.post("/search", json=payload)
    # Deve aceitar queries longas
    assert response.status_code in [200, 404]


def test_search_default_k(client):
    """Testa que k padrão é 5 quando não fornecido."""
    payload = {"q": "teste"}
    response = client.post("/search", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        assert len(data["results"]) <= 5


def test_search_backend_in_response(client):
    """Testa que backend é retornado na resposta."""
    payload = {"q": "teste", "k": 5}
    response = client.post("/search", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        assert "backend" in data
        assert data["backend"] in ["faiss", "opensearch"]
