"""
Testes para avaliação de recuperação (retrieval_eval).
"""
import pytest
import numpy as np

from src.eval.retrieval_eval import (
    precision_at_k,
    recall_at_k,
    mean_reciprocal_rank,
    dcg_at_k,
    ndcg_at_k
)


def test_precision_at_k():
    """Testa cálculo de Precision@K."""
    retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    relevant = ["doc1", "doc3", "doc5"]
    
    # P@3 = 2/3 (doc1 e doc3)
    assert precision_at_k(retrieved, relevant, 3) == pytest.approx(2/3, abs=0.01)
    
    # P@5 = 3/5
    assert precision_at_k(retrieved, relevant, 5) == pytest.approx(3/5, abs=0.01)
    
    # P@1 = 1/1
    assert precision_at_k(retrieved, relevant, 1) == 1.0
    
    # K=0
    assert precision_at_k(retrieved, relevant, 0) == 0.0


def test_precision_at_k_no_relevant():
    """Testa P@K quando não há documentos relevantes nos resultados."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc4", "doc5"]
    
    assert precision_at_k(retrieved, relevant, 3) == 0.0


def test_recall_at_k():
    """Testa cálculo de Recall@K."""
    retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    relevant = ["doc1", "doc3", "doc5", "doc7"]  # 4 relevantes, 3 recuperados
    
    # R@3 = 2/4 (doc1 e doc3)
    assert recall_at_k(retrieved, relevant, 3) == pytest.approx(2/4, abs=0.01)
    
    # R@5 = 3/4 (doc1, doc3, doc5)
    assert recall_at_k(retrieved, relevant, 5) == pytest.approx(3/4, abs=0.01)
    
    # R@1 = 1/4
    assert recall_at_k(retrieved, relevant, 1) == pytest.approx(1/4, abs=0.01)


def test_recall_at_k_no_relevant():
    """Testa R@K quando lista de relevantes é vazia."""
    retrieved = ["doc1", "doc2"]
    relevant = []
    
    assert recall_at_k(retrieved, relevant, 2) == 0.0


def test_recall_at_k_all_retrieved():
    """Testa R@K quando todos relevantes foram recuperados."""
    retrieved = ["doc1", "doc2", "doc3", "doc4"]
    relevant = ["doc1", "doc3"]
    
    assert recall_at_k(retrieved, relevant, 4) == 1.0


def test_mean_reciprocal_rank():
    """Testa cálculo de MRR."""
    # Primeiro doc relevante na posição 1
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc1"]
    assert mean_reciprocal_rank(retrieved, relevant) == 1.0
    
    # Primeiro doc relevante na posição 2
    retrieved = ["doc2", "doc1", "doc3"]
    relevant = ["doc1"]
    assert mean_reciprocal_rank(retrieved, relevant) == 0.5
    
    # Primeiro doc relevante na posição 3
    retrieved = ["doc2", "doc3", "doc1"]
    relevant = ["doc1"]
    assert mean_reciprocal_rank(retrieved, relevant) == pytest.approx(1/3, abs=0.01)


def test_mean_reciprocal_rank_no_relevant():
    """Testa MRR quando nenhum doc relevante foi recuperado."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc4", "doc5"]
    
    assert mean_reciprocal_rank(retrieved, relevant) == 0.0


def test_mean_reciprocal_rank_multiple_relevant():
    """Testa MRR com múltiplos docs relevantes (usa primeiro)."""
    retrieved = ["doc1", "doc2", "doc3", "doc4"]
    relevant = ["doc2", "doc4"]
    
    # Primeiro relevante em posição 2
    assert mean_reciprocal_rank(retrieved, relevant) == 0.5


def test_dcg_at_k():
    """Testa cálculo de DCG@K."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc1", "doc3"]
    
    # DCG@3 = 1/log2(2) + 0 + 1/log2(4)
    # = 1.0 + 0 + 0.5 = 1.5
    expected_dcg = 1.0 / np.log2(2) + 0 + 1.0 / np.log2(4)
    
    assert dcg_at_k(retrieved, relevant, 3) == pytest.approx(expected_dcg, abs=0.01)


def test_dcg_at_k_all_relevant():
    """Testa DCG quando todos docs são relevantes."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc1", "doc2", "doc3"]
    
    expected_dcg = (1.0 / np.log2(2) + 
                    1.0 / np.log2(3) + 
                    1.0 / np.log2(4))
    
    assert dcg_at_k(retrieved, relevant, 3) == pytest.approx(expected_dcg, abs=0.01)


def test_ndcg_at_k():
    """Testa cálculo de nDCG@K."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc1", "doc3"]
    
    # DCG real
    actual_dcg = dcg_at_k(retrieved, relevant, 3)
    
    # DCG ideal (todos relevantes no topo)
    ideal_retrieved = ["doc1", "doc3", "dummy"]
    ideal_dcg = dcg_at_k(ideal_retrieved, relevant, 3)
    
    expected_ndcg = actual_dcg / ideal_dcg
    
    assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(expected_ndcg, abs=0.01)


def test_ndcg_at_k_perfect():
    """Testa nDCG quando ordenação é perfeita."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = ["doc1", "doc2"]
    
    # Ordenação perfeita: nDCG = 1.0
    assert ndcg_at_k(retrieved, relevant, 3) == pytest.approx(1.0, abs=0.01)


def test_ndcg_at_k_no_relevant():
    """Testa nDCG quando não há relevantes."""
    retrieved = ["doc1", "doc2", "doc3"]
    relevant = []
    
    assert ndcg_at_k(retrieved, relevant, 3) == 0.0


def test_ndcg_at_k_worst_case():
    """Testa nDCG no pior caso (relevantes no final)."""
    retrieved = ["doc3", "doc4", "doc5", "doc1", "doc2"]
    relevant = ["doc1", "doc2"]
    
    # Relevantes nas posições 4 e 5: nDCG < 1.0
    ndcg = ndcg_at_k(retrieved, relevant, 5)
    assert 0.0 < ndcg < 1.0


def test_metrics_edge_cases():
    """Testa casos extremos das métricas."""
    # Lista vazia de retrieved
    assert precision_at_k([], ["doc1"], 5) == 0.0
    assert recall_at_k([], ["doc1"], 5) == 0.0
    assert mean_reciprocal_rank([], ["doc1"]) == 0.0
    
    # K maior que número de docs
    retrieved = ["doc1", "doc2"]
    relevant = ["doc1"]
    assert precision_at_k(retrieved, relevant, 10) == 1/10  # Conta zeros
    assert recall_at_k(retrieved, relevant, 10) == 1.0  # Todos relevantes foram pegos


def test_metrics_consistency():
    """Testa consistência entre métricas."""
    retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    relevant = ["doc1", "doc3", "doc5"]
    
    # P@5 = R@5 quando todos relevantes foram recuperados
    p5 = precision_at_k(retrieved, relevant, 5)
    r5 = recall_at_k(retrieved, relevant, 5)
    
    # P@5 = 3/5, R@5 = 3/3 = 1.0
    assert p5 == 0.6
    assert r5 == 1.0


def test_real_world_scenario():
    """Testa cenário realista de busca."""
    # Simulação: busca por "direitos fundamentais"
    retrieved = [
        "cf88_art5",     # Relevante
        "stf_hc_12345",  # Relevante
        "cc_art100",     # Não relevante
        "stj_resp_999",  # Não relevante
        "cf88_art1"      # Relevante
    ]
    
    relevant = ["cf88_art5", "stf_hc_12345", "cf88_art1", "outro_doc"]
    
    # Métricas
    p5 = precision_at_k(retrieved, relevant, 5)
    r5 = recall_at_k(retrieved, relevant, 5)
    mrr = mean_reciprocal_rank(retrieved, relevant)
    ndcg5 = ndcg_at_k(retrieved, relevant, 5)
    
    assert p5 == 0.6  # 3/5
    assert r5 == 0.75  # 3/4
    assert mrr == 1.0  # Primeiro é relevante
    assert 0.8 < ndcg5 <= 1.0  # Boa ordenação mas não perfeita
