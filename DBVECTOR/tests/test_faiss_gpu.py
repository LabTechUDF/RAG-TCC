"""
Testes para funcionalidade GPU do FAISS.
Verifica fallback automático e funcionamento básico.
"""
import os
import pytest
import numpy as np
import faiss
from src.storage.faiss_store import FAISSStore, _gpu_available, maybe_to_gpu
from src.schema import Doc


def test_gpu_availability_detection():
    """Testa se a detecção de GPU funciona sem erro."""
    has_gpu = _gpu_available()
    assert isinstance(has_gpu, bool)
    
    if has_gpu:
        print("✅ FAISS GPU disponível nesta build")
    else:
        print("⚠️ FAISS GPU não disponível - rodando em CPU")


def test_maybe_to_gpu_fallback_when_disabled():
    """Testa que maybe_to_gpu retorna CPU index quando GPU está desabilitado."""
    # Desabilita GPU temporariamente
    original_value = os.getenv("USE_FAISS_GPU")
    os.environ["USE_FAISS_GPU"] = "false"
    
    try:
        # Cria índice simples
        dimension = 128
        index = faiss.IndexFlatIP(dimension)
        
        # Deve retornar o mesmo índice (CPU)
        result = maybe_to_gpu(index)
        assert result is index  # Mesmo objeto
        
    finally:
        # Restaura valor original
        if original_value is None:
            os.environ.pop("USE_FAISS_GPU", None)
        else:
            os.environ["USE_FAISS_GPU"] = original_value


def test_maybe_to_gpu_fallback_when_unavailable():
    """Testa fallback quando GPU não está disponível mas está habilitado."""
    original_value = os.getenv("USE_FAISS_GPU")
    os.environ["USE_FAISS_GPU"] = "true"
    
    try:
        dimension = 128
        index = faiss.IndexFlatIP(dimension)
        
        # Chama maybe_to_gpu - deve fazer fallback se GPU não disponível
        result = maybe_to_gpu(index)
        
        # Se GPU disponível, deve ser GpuIndex; senão, CPU index
        if _gpu_available():
            assert isinstance(result, faiss.GpuIndex)
        else:
            # Fallback para CPU - não deve lançar exceção
            assert result is not None
            
    finally:
        if original_value is None:
            os.environ.pop("USE_FAISS_GPU", None)
        else:
            os.environ["USE_FAISS_GPU"] = original_value


def test_faiss_store_with_gpu_enabled(tmp_path):
    """Teste E2E: cria store, indexa docs, faz query - com GPU habilitado."""
    original_value = os.getenv("USE_FAISS_GPU")
    os.environ["USE_FAISS_GPU"] = "true"
    
    try:
        # Cria store temporário
        index_path = str(tmp_path / "test_index")
        metadata_path = str(tmp_path / "metadata.parquet")
        
        store = FAISSStore(index_path=index_path, metadata_path=metadata_path)
        
        # Cria documentos de teste
        docs = [
            Doc(
                id=f"doc_{i}",
                text=f"Este é um documento de teste número {i} sobre direito penal.",
                title=f"Documento {i}",
                court="STF",
                code="CPP",
                article="312",
                date="2024-01-01",
                meta={}
            )
            for i in range(10)
        ]
        
        # Indexa
        store.index(docs)
        
        # Verifica que indexou
        assert store.get_doc_count() == 10
        
        # Faz query
        from src import embeddings
        query = "documento sobre direito penal"
        query_vector = embeddings.encode_texts([query])[0]
        
        results = store.search(query_vector, k=5)
        
        # Valida resultados
        assert len(results) > 0
        assert len(results) <= 5
        assert all(r.score > 0 for r in results)
        assert all(r.doc.id.startswith("doc_") for r in results)
        
        print(f"✅ Teste E2E passou! {len(results)} resultados retornados")
        
    finally:
        if original_value is None:
            os.environ.pop("USE_FAISS_GPU", None)
        else:
            os.environ["USE_FAISS_GPU"] = original_value


def test_faiss_store_with_gpu_disabled(tmp_path):
    """Teste E2E: mesmo teste mas com GPU explicitamente desabilitado."""
    original_value = os.getenv("USE_FAISS_GPU")
    os.environ["USE_FAISS_GPU"] = "false"
    
    try:
        index_path = str(tmp_path / "test_index_cpu")
        metadata_path = str(tmp_path / "metadata_cpu.parquet")
        
        store = FAISSStore(index_path=index_path, metadata_path=metadata_path)
        
        docs = [
            Doc(
                id=f"doc_{i}",
                text=f"Documento CPU teste {i}",
                title=f"Doc {i}",
                court="STF",
                code="CPP",
                article="312",
                date="2024-01-01",
                meta={}
            )
            for i in range(5)
        ]
        
        store.index(docs)
        assert store.get_doc_count() == 5
        
        from src import embeddings
        query_vector = embeddings.encode_texts(["teste"])[0]
        results = store.search(query_vector, k=3)
        
        assert len(results) > 0
        print(f"✅ Teste CPU passou! {len(results)} resultados")
        
    finally:
        if original_value is None:
            os.environ.pop("USE_FAISS_GPU", None)
        else:
            os.environ["USE_FAISS_GPU"] = original_value


@pytest.mark.skipif(not _gpu_available(), reason="FAISS GPU não disponível")
def test_gpu_transfer():
    """Teste específico de GPU: verifica transferência CPU -> GPU."""
    os.environ["USE_FAISS_GPU"] = "true"
    
    try:
        dimension = 128
        cpu_index = faiss.IndexFlatIP(dimension)
        
        # Adiciona alguns vetores
        vectors = np.random.rand(10, dimension).astype(np.float32)
        cpu_index.add(vectors)
        
        # Move para GPU
        gpu_index = maybe_to_gpu(cpu_index)
        
        # Verifica que é GPU index
        assert isinstance(gpu_index, faiss.GpuIndex)
        assert gpu_index.ntotal == 10
        
        # Faz busca no GPU
        query = np.random.rand(1, dimension).astype(np.float32)
        distances, indices = gpu_index.search(query, k=5)
        
        assert distances.shape == (1, 5)
        assert indices.shape == (1, 5)
        
        print("✅ Transferência e busca GPU funcionaram!")
        
    finally:
        os.environ.pop("USE_FAISS_GPU", None)
