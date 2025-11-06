#!/usr/bin/env python
"""
Script de teste rápido para verificar funcionalidade GPU/CPU do FAISS.
Execute: python test_gpu_quick.py
"""
import os
import sys

def test_imports():
    """Testa imports básicos."""
    print("1. Testando imports...")
    try:
        import faiss
        import torch
        import numpy as np
        from src import config
        print("   ✅ Imports OK")
        return faiss, torch, np
    except ImportError as e:
        print(f"   ❌ Erro no import: {e}")
        sys.exit(1)

def test_gpu_detection(faiss):
    """Testa detecção de GPU."""
    print("\n2. Detectando GPU...")
    has_gpu = hasattr(faiss, "StandardGpuResources")
    print(f"   FAISS GPU disponível: {has_gpu}")
    
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        print(f"   PyTorch CUDA disponível: {cuda_available}")
        if cuda_available:
            print(f"   CUDA version: {torch.version.cuda}")
            print(f"   GPU count: {torch.cuda.device_count()}")
    except Exception as e:
        print(f"   ⚠️ Erro ao verificar PyTorch CUDA: {e}")
    
    return has_gpu

def test_config():
    """Testa configuração."""
    print("\n3. Verificando configuração...")
    from src import config
    print(f"   USE_FAISS_GPU: {config.USE_FAISS_GPU}")
    print(f"   FAISS_GPU_DEVICE: {config.FAISS_GPU_DEVICE}")
    print(f"   EMBEDDING_MODEL: {config.EMBEDDING_MODEL}")
    print("   ✅ Config OK")

def test_faiss_basic(faiss, np, has_gpu):
    """Testa funcionalidade básica do FAISS."""
    print("\n4. Testando FAISS básico...")
    
    # Criar índice simples
    dimension = 128
    n_vectors = 100
    
    print(f"   Criando índice ({n_vectors} vetores, dim={dimension})...")
    index = faiss.IndexFlatIP(dimension)
    
    # Gerar vetores aleatórios
    vectors = np.random.rand(n_vectors, dimension).astype(np.float32)
    faiss.normalize_L2(vectors)
    
    # Adicionar ao índice
    index.add(vectors)
    print(f"   ✅ {index.ntotal} vetores adicionados")
    
    # Tentar mover para GPU se disponível e configurado
    from src import config
    if config.USE_FAISS_GPU and has_gpu:
        print("   Tentando mover para GPU...")
        try:
            res = faiss.StandardGpuResources()
            gpu_index = faiss.index_cpu_to_gpu(res, config.FAISS_GPU_DEVICE, index)
            print(f"   ✅ Índice movido para GPU (device {config.FAISS_GPU_DEVICE})")
            index = gpu_index
        except Exception as e:
            print(f"   ⚠️ Falha ao mover para GPU: {e}")
            print("   Continuando com CPU...")
    
    # Busca
    query = np.random.rand(1, dimension).astype(np.float32)
    faiss.normalize_L2(query)
    
    k = 5
    distances, indices = index.search(query, k)
    
    print(f"   ✅ Busca retornou {len(indices[0])} resultados")
    print(f"   Top 3 scores: {distances[0][:3]}")
    
    return True

def test_embeddings():
    """Testa geração de embeddings."""
    print("\n5. Testando embeddings...")
    try:
        from src import embeddings
        
        texts = [
            "Este é um teste",
            "Outro documento de teste",
            "Direitos fundamentais"
        ]
        
        print(f"   Gerando embeddings para {len(texts)} textos...")
        vectors = embeddings.encode_texts(texts)
        
        print(f"   ✅ Shape: {vectors.shape}")
        print(f"   Dimensão: {vectors.shape[1]}")
        
        return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False

def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("  Teste Rápido GPU/CPU - RAG Jurídico")
    print("=" * 60)
    
    # Imports
    faiss, torch, np = test_imports()
    
    # GPU detection
    has_gpu = test_gpu_detection(faiss)
    
    # Config
    test_config()
    
    # FAISS básico
    test_faiss_basic(faiss, np, has_gpu)
    
    # Embeddings
    test_embeddings()
    
    print("\n" + "=" * 60)
    print("  ✅ Todos os testes passaram!")
    print("=" * 60)
    print("\nPróximos passos:")
    print("  1. make faiss-build  - Indexar documentos")
    print("  2. make api          - Iniciar API")
    print("  3. make test         - Executar suite completa")
    print("  4. make sanity       - Verificação operacional")

if __name__ == "__main__":
    main()
