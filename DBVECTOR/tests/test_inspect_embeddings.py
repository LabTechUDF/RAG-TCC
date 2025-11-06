"""
Testes para inspeção de embeddings.
"""
import pytest
import json
import numpy as np
from pathlib import Path

from src.eval.inspect_embeddings import (
    inspect_embeddings,
    load_embeddings_from_jsonl,
    load_embeddings_from_npy,
    generate_embeddings_from_jsonl
)


def test_inspect_embeddings_valid():
    """Testa inspeção de embeddings válidos."""
    # Cria vetores válidos (10 docs, dim 384)
    vectors = np.random.randn(10, 384).astype(np.float32)
    # Normaliza
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    
    report = inspect_embeddings(vectors)
    
    assert report["num_vectors"] == 10
    assert report["dimension"] == 384
    assert report["dimension_ok"] is True
    assert report["has_nan"] is False
    assert report["has_inf"] is False
    assert report["num_nan"] == 0
    assert report["num_inf"] == 0


def test_inspect_embeddings_with_nan():
    """Testa detecção de NaN."""
    vectors = np.random.randn(10, 384).astype(np.float32)
    
    # Injeta NaN
    vectors[0, 0] = np.nan
    vectors[1, 5] = np.nan
    
    report = inspect_embeddings(vectors)
    
    assert report["has_nan"] is True
    assert report["num_nan"] == 2


def test_inspect_embeddings_with_inf():
    """Testa detecção de Inf."""
    vectors = np.random.randn(10, 384).astype(np.float32)
    
    # Injeta Inf
    vectors[0, 0] = np.inf
    vectors[1, 5] = -np.inf
    
    report = inspect_embeddings(vectors)
    
    assert report["has_inf"] is True
    assert report["num_inf"] == 2


def test_inspect_embeddings_collapsed():
    """Testa detecção de vetores colapsados."""
    # Vetores com norma muito baixa
    vectors = np.random.randn(10, 384).astype(np.float32) * 0.01  # Norma ~ 0.01
    
    report = inspect_embeddings(vectors)
    
    # Deve detectar vetores colapsados
    assert report["collapsed_vectors"] > 0
    assert report["collapsed_pct"] > 0


def test_inspect_embeddings_near_duplicates():
    """Testa detecção de near-duplicates."""
    vectors = np.random.randn(10, 384).astype(np.float32)
    
    # Normaliza
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    
    # Cria duplicatas exatas
    vectors[5] = vectors[0].copy()
    vectors[6] = vectors[1].copy()
    
    report = inspect_embeddings(vectors, near_dupes_threshold=0.995)
    
    # Deve detectar pelo menos 2 pares de duplicatas
    assert report["near_duplicates"]["count"] >= 2


def test_inspect_embeddings_dimension_mismatch():
    """Testa detecção de dimensão incorreta."""
    # Dimensão diferente da esperada
    vectors = np.random.randn(10, 256).astype(np.float32)
    
    report = inspect_embeddings(vectors)
    
    assert report["dimension"] == 256
    assert report["expected_dimension"] == 384
    assert report["dimension_ok"] is False


def test_inspect_embeddings_norms():
    """Testa cálculo de normas L2."""
    # Vetores com norma ~1.0
    vectors = np.random.randn(100, 384).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    
    report = inspect_embeddings(vectors)
    
    # Normas devem estar próximas de 1.0
    assert 0.9 < report["norm_l2"]["mean"] < 1.1
    assert 0.9 < report["norm_l2"]["p5"] < 1.1
    assert 0.9 < report["norm_l2"]["p95"] < 1.1


def test_inspect_embeddings_similarities():
    """Testa cálculo de similaridades."""
    # Vetores aleatórios ortogonais
    vectors = np.random.randn(100, 384).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    
    report = inspect_embeddings(vectors)
    
    # Similaridade média deve ser próxima de 0 para vetores aleatórios
    assert -0.2 < report["cosine_similarity"]["mean"] < 0.2


def test_load_embeddings_from_npy(tmp_path):
    """Testa carregamento de embeddings de arquivo .npy."""
    vectors = np.random.randn(10, 384).astype(np.float32)
    
    npy_file = tmp_path / "embeddings.npy"
    np.save(npy_file, vectors)
    
    loaded = load_embeddings_from_npy(npy_file)
    
    assert loaded.shape == vectors.shape
    assert np.allclose(loaded, vectors)


def test_load_embeddings_from_jsonl(tmp_path):
    """Testa carregamento de embeddings de JSONL."""
    vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9]
    ]
    
    jsonl_file = tmp_path / "embeddings.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for vec in vectors:
            f.write(json.dumps({"vector": vec}) + "\n")
    
    loaded = load_embeddings_from_jsonl(jsonl_file)
    
    assert loaded.shape == (3, 3)
    assert np.allclose(loaded, np.array(vectors))


def test_load_embeddings_from_jsonl_with_empty_lines(tmp_path):
    """Testa que linhas vazias são ignoradas."""
    jsonl_file = tmp_path / "embeddings.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"vector": [1, 2, 3]}) + "\n")
        f.write("\n")  # Linha vazia
        f.write(json.dumps({"vector": [4, 5, 6]}) + "\n")
    
    loaded = load_embeddings_from_jsonl(jsonl_file)
    
    assert loaded.shape == (2, 3)


def test_generate_embeddings_from_jsonl(tmp_path):
    """Testa geração on-the-fly de embeddings."""
    jsonl_file = tmp_path / "docs.jsonl"
    docs = [
        {"id": "1", "text": "Primeiro documento de teste"},
        {"id": "2", "text": "Segundo documento de teste"}
    ]
    
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    
    vectors = generate_embeddings_from_jsonl(jsonl_file)
    
    assert vectors.shape[0] == 2
    assert vectors.shape[1] == 384  # Dimensão do modelo


def test_generate_embeddings_no_text_field(tmp_path):
    """Testa erro quando não há campo 'text'."""
    jsonl_file = tmp_path / "docs.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "1", "content": "texto"}) + "\n")
    
    with pytest.raises(ValueError, match="Nenhum texto encontrado"):
        generate_embeddings_from_jsonl(jsonl_file)


def test_inspect_embeddings_large_dataset():
    """Testa inspeção com dataset grande (usa amostragem)."""
    # Simula 2000 vetores
    vectors = np.random.randn(2000, 384).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    
    report = inspect_embeddings(vectors)
    
    assert report["num_vectors"] == 2000
    assert report["dimension"] == 384
    # Amostragem deve funcionar sem explodir memória


def test_inspect_embeddings_threshold_variations():
    """Testa diferentes thresholds de near-duplicates."""
    vectors = np.random.randn(50, 384).astype(np.float32)
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    
    # Cria alguns duplicatas
    vectors[10] = vectors[0].copy()
    vectors[20] = vectors[5].copy()
    
    # Threshold alto: deve detectar mais
    report_high = inspect_embeddings(vectors, near_dupes_threshold=0.99)
    
    # Threshold muito alto: deve detectar menos
    report_very_high = inspect_embeddings(vectors, near_dupes_threshold=0.999)
    
    assert report_high["near_duplicates"]["count"] >= report_very_high["near_duplicates"]["count"]


def test_inspect_embeddings_report_structure():
    """Testa estrutura completa do relatório."""
    vectors = np.random.randn(10, 384).astype(np.float32)
    
    report = inspect_embeddings(vectors)
    
    # Verifica campos obrigatórios
    required_fields = [
        "num_vectors", "dimension", "expected_dimension", "dimension_ok",
        "has_nan", "has_inf", "num_nan", "num_inf",
        "norm_l2", "collapsed_vectors", "collapsed_pct",
        "cosine_similarity", "near_duplicates"
    ]
    
    for field in required_fields:
        assert field in report
    
    # Verifica sub-estruturas
    assert "mean" in report["norm_l2"]
    assert "p5" in report["norm_l2"]
    assert "p95" in report["norm_l2"]
    
    assert "mean" in report["cosine_similarity"]
    assert "count" in report["near_duplicates"]
    assert "pct" in report["near_duplicates"]
    assert "threshold" in report["near_duplicates"]


def test_inspect_embeddings_realistic_scenario():
    """Testa cenário realista com embeddings de modelo real."""
    from src import embeddings as emb
    
    texts = [
        "Direitos fundamentais na Constituição",
        "Habeas corpus e liberdade",
        "Prescrição no direito civil",
        "Responsabilidade do fornecedor"
    ]
    
    vectors = emb.encode_texts(texts)
    
    report = inspect_embeddings(vectors)
    
    # Verifica saúde dos embeddings
    assert report["dimension_ok"] is True
    assert report["has_nan"] is False
    assert report["has_inf"] is False
    assert report["collapsed_vectors"] == 0
    
    # Vetores de modelo real devem ter norma razoável
    assert report["norm_l2"]["mean"] > 0.5
