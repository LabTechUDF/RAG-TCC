"""
Pipeline para indexar documentos dummy no FAISS.
"""
import sys
from pathlib import Path

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.factory import get_faiss_store
from src.schema import get_dummy_docs
from src.tools.chunking import chunk_documents
from src import config


def main():
    """Indexa documentos dummy no FAISS."""
    print("🚀 Iniciando pipeline de build FAISS...")
    
    # Carrega documentos dummy
    docs = get_dummy_docs()
    print(f"📄 Carregados {len(docs)} documentos originais")

    # Aplica chunking aos documentos
    print(f"✂️  Aplicando chunking (chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP})...")
    chunk_docs = chunk_documents(docs, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    print(f"📦 Gerados {len(chunk_docs)} chunks de {len(docs)} documentos originais")

    # Cria store FAISS
    store = get_faiss_store()
    
    # Indexa chunks
    store.index(chunk_docs)
    
    print(f"✅ Pipeline concluído! {store.get_doc_count()} chunks indexados")
    
    # Mostra resumo dos documentos originais e chunks
    print("\n📋 Documentos originais processados:")
    for doc in docs:
        doc_chunks = [c for c in chunk_docs if c.meta.get('original_id') == doc.id]
        print(f"  • {doc.id}: {doc.title} → {len(doc_chunks)} chunks")


if __name__ == "__main__":
    main()