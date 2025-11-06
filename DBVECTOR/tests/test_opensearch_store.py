"""
Testes para OpenSearch store.
Estes testes são executados apenas se OpenSearch estiver disponível.
"""
import pytest
import requests
from opensearchpy import OpenSearch
from opensearchpy.exceptions import ConnectionError

from src import config
from src.storage.opensearch_store import OpenSearchStore


def is_opensearch_available() -> bool:
    """Verifica se OpenSearch está disponível."""
    try:
        response = requests.get(
            f"http://{config.OPENSEARCH_HOST}:{config.OPENSEARCH_PORT}",
            timeout=2
        )
        return response.status_code == 200
    except:
        return False


# Skip todos os testes se OpenSearch não estiver disponível
pytestmark = pytest.mark.skipif(
    not is_opensearch_available(),
    reason="OpenSearch não está disponível em localhost:9200"
)


@pytest.fixture
def opensearch_store(opensearch_test_index):
    """Fixture para store OpenSearch de teste."""
    store = OpenSearchStore(index_name=opensearch_test_index)
    
    # Limpa índice se existir
    try:
        store.delete_index()
    except:
        pass
    
    yield store
    
    # Cleanup após teste
    try:
        store.delete_index()
    except:
        pass


def test_opensearch_connection():
    """Testa conexão com OpenSearch."""
    client = OpenSearch(**config.get_opensearch_config())
    info = client.info()
    assert "version" in info
    assert "number" in info["version"]


def test_opensearch_store_init(opensearch_store):
    """Testa inicialização do OpenSearch store."""
    assert opensearch_store.client is not None
    assert opensearch_store.index_name.startswith("test-")
    assert opensearch_store.get_doc_count() == 0


def test_opensearch_ensure_index(opensearch_store):
    """Testa criação de índice."""
    # Index não deve existir inicialmente
    assert not opensearch_store.client.indices.exists(index=opensearch_store.index_name)
    
    # Cria índice
    opensearch_store.ensure_index(dimension=384)
    
    # Index deve existir agora
    assert opensearch_store.client.indices.exists(index=opensearch_store.index_name)
    
    # Verifica mapeamento
    mapping = opensearch_store.client.indices.get_mapping(index=opensearch_store.index_name)
    properties = mapping[opensearch_store.index_name]["mappings"]["properties"]
    
    assert "vector" in properties
    assert properties["vector"]["type"] == "knn_vector"
    assert properties["vector"]["dimension"] == 384


def test_opensearch_index_and_search(opensearch_store, dummy_docs):
    """Testa indexação e busca no OpenSearch."""
    # Indexa documentos
    opensearch_store.index(dummy_docs)
    
    # Verifica contagem
    assert opensearch_store.get_doc_count() == len(dummy_docs)
    
    # Testa busca
    from src import embeddings
    query_vector = embeddings.encode_single_text("direitos fundamentais")
    results = opensearch_store.search(query_vector, k=3)
    
    assert len(results) > 0
    assert len(results) <= 3
    
    # Verifica estrutura dos resultados
    for result in results:
        assert hasattr(result, 'doc')
        assert hasattr(result, 'score')
        assert isinstance(result.score, float)
        assert result.score >= 0  # OpenSearch kNN scores são [0,1]
        assert result.doc.id in [doc.id for doc in dummy_docs]


def test_opensearch_search_empty_index(opensearch_store):
    """Testa busca em índice vazio."""
    # Garante que índice existe mas está vazio
    opensearch_store.ensure_index()
    assert opensearch_store.get_doc_count() == 0
    
    from src import embeddings
    query_vector = embeddings.encode_single_text("qualquer query")
    results = opensearch_store.search(query_vector, k=5)
    
    assert results == []


def test_opensearch_delete_index(opensearch_store, sample_doc):
    """Testa remoção de índice."""
    # Cria índice e indexa documento
    opensearch_store.index([sample_doc])
    assert opensearch_store.get_doc_count() == 1
    
    # Remove índice
    opensearch_store.delete_index()
    
    # Índice não deve mais existir
    assert not opensearch_store.client.indices.exists(index=opensearch_store.index_name)
    assert opensearch_store.get_doc_count() == 0


def test_opensearch_search_relevance(opensearch_store, dummy_docs):
    """Testa relevância dos resultados de busca."""
    opensearch_store.index(dummy_docs)
    
    from src import embeddings
    
    # Query específica para direitos constitucionais
    query_vector = embeddings.encode_single_text("direitos fundamentais constituição")
    results = opensearch_store.search(query_vector, k=5)
    
    assert len(results) > 0
    
    # Scores devem estar em ordem decrescente
    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)
    
    # Primeiro resultado deve ter score maior que 0
    assert results[0].score > 0