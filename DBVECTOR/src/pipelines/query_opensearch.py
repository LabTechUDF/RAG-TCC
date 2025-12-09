"""
Pipeline para consultar documentos no OpenSearch.
"""
import sys
from pathlib import Path

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.factory import get_opensearch_store
from src import embeddings, config


def main():
    """Consulta documentos no OpenSearch."""
    print("🔍 Iniciando pipeline de query OpenSearch...")
    
    try:
        # Query da configuração
        query = config.QUERY
        print(f"❓ Query: '{query}'")
        
        # Cria store OpenSearch
        store = get_opensearch_store()
        
        # Verifica se há documentos indexados
        doc_count = store.get_doc_count()
        if doc_count == 0:
            print("⚠️ Nenhum documento indexado! Execute 'make os-build' primeiro")
            return
        
        print(f"📊 {doc_count} documentos no índice")
        
        # Gera embedding da query
        print("🔄 Gerando embedding da query...")
        query_vector = embeddings.encode_single_text(query)
        
        # Busca documentos similares
        print("🔍 Buscando documentos similares...")
        results = store.search(query_vector, k=3)
        
        # Mostra resultados
        print(f"\n📋 {len(results)} resultados encontrados:")
        print("=" * 80)
        
        for i, result in enumerate(results, 1):
            doc = result.doc
            print(f"\n{i}. {doc.title} (Score: {result.score:.4f})")
            print(f"   ID: {doc.id}")
            if doc.court:
                print(f"   Tribunal: {doc.court}")
            if doc.code and doc.article:
                print(f"   Código: {doc.code} - Art. {doc.article}")
            if doc.date:
                print(f"   Data: {doc.date}")
            print(f"   Texto: {doc.text[:200]}...")
            
            if i < len(results):
                print("-" * 80)
                
    except Exception as e:
        print(f"❌ Erro no pipeline OpenSearch: {e}")
        print("💡 Verifique se o OpenSearch está rodando e indexado: make os-up && make os-build")
        sys.exit(1)


if __name__ == "__main__":
    main()