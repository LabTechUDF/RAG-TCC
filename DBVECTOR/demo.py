#!/usr/bin/env python3
"""
Script de demonstração rápida do RAG Jurídico.
Execute: python demo.py
"""

import sys
import os
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("🏛️ Demo RAG Jurídico")
    print("====================")
    
    try:
        # Importa módulos
        from src.storage.factory import get_faiss_store
        from src.schema import get_dummy_docs
        from src import embeddings
        
        print("📦 Carregando dados dummy...")
        docs = get_dummy_docs()
        print(f"✅ {len(docs)} documentos carregados")
        
        # Usa diretório temporário para demo
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"📁 Usando diretório temporário: {temp_dir}")
            
            # Configura store FAISS temporário
            store = get_faiss_store(
                index_path=temp_dir,
                metadata_path=os.path.join(temp_dir, "metadata.parquet")
            )
            
            print("🔄 Indexando documentos...")
            store.index(docs)
            print(f"✅ {store.get_doc_count()} documentos indexados")
            
            # Testa buscas
            queries = [
                "direitos fundamentais",
                "habeas corpus",
                "prescrição civil",
                "responsabilidade consumidor"
            ]
            
            for query in queries:
                print(f"\n🔍 Busca: '{query}'")
                print("-" * 50)
                
                # Gera embedding e busca
                query_vector = embeddings.encode_single_text(query)
                results = store.search(query_vector, k=2)
                
                if results:
                    for i, result in enumerate(results, 1):
                        doc = result.doc
                        print(f"{i}. {doc.title} (Score: {result.score:.3f})")
                        print(f"   {doc.code} - {doc.court}")
                        print(f"   {doc.text[:100]}...")
                else:
                    print("   Nenhum resultado encontrado")
            
        print(f"\n✅ Demo concluída!")
        print(f"\n💡 Para usar o sistema completo:")
        print(f"   1. cp .env.example .env")
        print(f"   2. make faiss-build")
        print(f"   3. make api")
        print(f"   4. Acesse: http://localhost:8000/docs")
        
    except ImportError as e:
        print(f"❌ Erro de import: {e}")
        print("💡 Execute: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()