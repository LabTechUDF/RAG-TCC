"""
Testes para módulo de embeddings.
"""
import numpy as np
import pytest

from src import embeddings, config


def test_load_model():
    """Testa carregamento do modelo."""
    model = embeddings.load_model()
    assert model is not None
    
    # Testa singleton - deve retornar a mesma instância
    model2 = embeddings.load_model()
    assert model is model2


def test_get_embedding_dimension():
    """Testa obtenção da dimensão dos embeddings."""
    dim = embeddings.get_embedding_dimension()
    assert dim == config.EMBEDDING_DIM
    assert isinstance(dim, int)
    assert dim > 0


def test_encode_single_text():
    """Testa codificação de texto único."""
    text = "Este é um teste de embedding"
    vector = embeddings.encode_single_text(text)
    
    assert isinstance(vector, np.ndarray)
    assert vector.dtype == np.float32
    assert vector.shape == (config.EMBEDDING_DIM,)
    
    # Testa se é determinístico
    vector2 = embeddings.encode_single_text(text)
    np.testing.assert_array_equal(vector, vector2)


def test_encode_texts():
    """Testa codificação de múltiplos textos."""
    texts = [
        "Primeiro texto de teste",
        "Segundo texto de teste", 
        "Terceiro texto de teste"
    ]
    
    vectors = embeddings.encode_texts(texts)
    
    assert isinstance(vectors, np.ndarray)
    assert vectors.dtype == np.float32
    assert vectors.shape == (len(texts), config.EMBEDDING_DIM)
    
    # Cada linha deve ser diferente
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            assert not np.array_equal(vectors[i], vectors[j])


def test_encode_texts_empty():
    """Testa codificação de lista vazia."""
    vectors = embeddings.encode_texts([])
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (0, config.EMBEDDING_DIM)


def test_normalization_config():
    """Testa se normalização está sendo aplicada conforme configuração."""
    text = "Texto para testar normalização"
    vector = embeddings.encode_single_text(text)
    
    if config.NORMALIZE_EMBEDDINGS:
        # Se normalizado, norma deve ser próxima de 1
        norm = np.linalg.norm(vector)
        assert abs(norm - 1.0) < 1e-5
    else:
        # Se não normalizado, norma pode ser qualquer valor
        norm = np.linalg.norm(vector)
        assert norm > 0