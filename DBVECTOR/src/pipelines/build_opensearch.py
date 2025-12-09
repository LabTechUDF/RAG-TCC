"""
Pipeline para indexar documentos dummy no OpenSearch.
"""
import sys
from pathlib import Path

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.factory import get_opensearch_store
from src.schema import get_dummy_docs
from src import config


def main():
    """Indexa documentos dummy no OpenSearch."""
    print("🚀 Iniciando pipeline de build OpenSearch...")
    
    try:
        # Cria store OpenSearch
        store = get_opensearch_store()
        
        # Garante que o índice existe
        print(f"🔧 Verificando índice '{config.OPENSEARCH_INDEX}'...")
        store.ensure_index(dimension=config.EMBEDDING_DIM)
        
        # Carrega documentos dummy
        docs = get_dummy_docs()
        print(f"📄 Carregados {len(docs)} documentos dummy")
        
        # Indexa documentos
        store.index(docs)
        
        print(f"✅ Pipeline concluído! {store.get_doc_count()} documentos indexados")
        
        # Mostra resumo dos documentos
        print("\n📋 Documentos indexados:")
        for doc in docs:
            print(f"  • {doc.id}: {doc.title}")
            
    except Exception as e:
        print(f"❌ Erro no pipeline OpenSearch: {e}")
        print("💡 Verifique se o OpenSearch está rodando: make os-up")
        sys.exit(1)


if __name__ == "__main__":
    main()