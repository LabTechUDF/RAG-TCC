"""
Benchmarks de latência de query (/search endpoint).
Valida SLO de p95 de latência.
"""
import pytest
import time
from fastapi.testclient import TestClient

from src import config


@pytest.fixture
def api_client():
    """Cliente da API para benchmarks."""
    from src.api.main import app
    return TestClient(app)


def test_query_latency_k5(benchmark, api_client):
    """
    Benchmark de latência de query com k=5.
    Valida SLO: p95 <= SLO_P95_MS.
    """
    def search_k5():
        response = api_client.post(
            "/search",
            json={"q": "direitos fundamentais", "k": 5}
        )
        # Se há documentos, deve retornar 200; senão 404
        assert response.status_code in [200, 404]
        return response
    
    # Executa benchmark
    result = benchmark(search_k5)
    
    # Obtém estatísticas
    stats = result.stats
    
    # Converte para milissegundos
    mean_ms = stats.mean * 1000
    median_ms = stats.median * 1000
    
    # Calcula p95 (aproximação usando quartis)
    # pytest-benchmark não expõe p95 diretamente, então usamos max como proxy conservador
    # Em runs com múltiplas iterações, max é uma boa aproximação de cauda
    p95_ms = stats.max * 1000
    
    print(f"\n📊 Latência k=5:")
    print(f"   Mean: {mean_ms:.2f}ms")
    print(f"   Median: {median_ms:.2f}ms")
    print(f"   P95 (approx): {p95_ms:.2f}ms")
    print(f"   SLO: {config.SLO_P95_MS}ms")
    
    # Valida SLO
    assert p95_ms <= config.SLO_P95_MS, \
        f"SLO violated: p95={p95_ms:.2f}ms > {config.SLO_P95_MS}ms"


def test_query_latency_k10(benchmark, api_client):
    """
    Benchmark de latência de query com k=10.
    Valida SLO: p95 <= SLO_P95_MS * 1.2 (permite +20% para k maior).
    """
    def search_k10():
        response = api_client.post(
            "/search",
            json={"q": "direitos fundamentais", "k": 10}
        )
        assert response.status_code in [200, 404]
        return response
    
    result = benchmark(search_k10)
    stats = result.stats
    
    mean_ms = stats.mean * 1000
    p95_ms = stats.max * 1000
    
    # SLO relaxado para k=10
    slo_k10 = config.SLO_P95_MS * 1.2
    
    print(f"\n📊 Latência k=10:")
    print(f"   Mean: {mean_ms:.2f}ms")
    print(f"   P95 (approx): {p95_ms:.2f}ms")
    print(f"   SLO: {slo_k10:.2f}ms")
    
    assert p95_ms <= slo_k10, \
        f"SLO violated: p95={p95_ms:.2f}ms > {slo_k10:.2f}ms"


def test_query_latency_complex_query(benchmark, api_client):
    """Benchmark com query complexa."""
    complex_query = (
        "direitos fundamentais habeas corpus prisão preventiva "
        "liberdade constitucional supremo tribunal"
    )
    
    def search_complex():
        response = api_client.post(
            "/search",
            json={"q": complex_query, "k": 5}
        )
        assert response.status_code in [200, 404]
        return response
    
    result = benchmark(search_complex)
    stats = result.stats
    
    p95_ms = stats.max * 1000
    
    print(f"\n📊 Latência query complexa:")
    print(f"   P95 (approx): {p95_ms:.2f}ms")
    
    # Query complexa pode ter SLO relaxado
    slo_complex = config.SLO_P95_MS * 1.5
    
    assert p95_ms <= slo_complex, \
        f"SLO violated for complex query: p95={p95_ms:.2f}ms > {slo_complex:.2f}ms"


@pytest.mark.parametrize("k", [1, 5, 10, 20])
def test_query_latency_scaling(benchmark, api_client, k):
    """
    Testa escalabilidade de latência com diferentes valores de k.
    Garante que latência não cresce excessivamente com k.
    """
    def search_k():
        response = api_client.post(
            "/search",
            json={"q": "direitos fundamentais", "k": k}
        )
        assert response.status_code in [200, 404]
        return response
    
    result = benchmark(search_k)
    mean_ms = result.stats.mean * 1000
    
    print(f"\n📊 Latência k={k}: {mean_ms:.2f}ms")
    
    # Latência não deve crescer linearmente com k
    # Para k=20, permitimos no máximo 2x o SLO base
    max_allowed = config.SLO_P95_MS * (1 + (k / 20))
    
    assert mean_ms <= max_allowed, \
        f"Latência cresce muito com k={k}: {mean_ms:.2f}ms > {max_allowed:.2f}ms"


def test_concurrent_queries_throughput(api_client):
    """
    Testa throughput com queries concorrentes simuladas.
    Não é um benchmark pytest-benchmark, mas mede QPS.
    """
    num_queries = 50
    query = "direitos fundamentais"
    
    start = time.time()
    
    for _ in range(num_queries):
        response = api_client.post(
            "/search",
            json={"q": query, "k": 5}
        )
        assert response.status_code in [200, 404]
    
    elapsed = time.time() - start
    qps = num_queries / elapsed
    
    print(f"\n📊 Throughput:")
    print(f"   Queries: {num_queries}")
    print(f"   Tempo: {elapsed:.2f}s")
    print(f"   QPS: {qps:.2f}")
    
    # Threshold mínimo de throughput: 10 QPS
    min_qps = 10
    assert qps >= min_qps, \
        f"Throughput muito baixo: {qps:.2f} < {min_qps} QPS"
