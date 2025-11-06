"""
Store OpenSearch para busca vetorial distribuída.
"""
import json
import numpy as np
from typing import List, Dict, Any
from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
from opensearchpy.exceptions import RequestError

from src.storage.base import VectorStore  
from src.schema import Doc, SearchResult
from src import embeddings, config


class OpenSearchStore(VectorStore):
    """Store OpenSearch com busca kNN."""
    
    def __init__(self, client: OpenSearch = None, index_name: str = None):
        self.client = client or OpenSearch(**config.get_opensearch_config())
        self.index_name = index_name or config.OPENSEARCH_INDEX
        
        # Testa conexão
        try:
            info = self.client.info()
            print(f"✅ Conectado ao OpenSearch {info['version']['number']}")
        except Exception as e:
            print(f"❌ Erro ao conectar no OpenSearch: {e}")
            raise
    
    def ensure_index(self, dimension: int = None, shards: int = 1, replicas: int = 0) -> None:
        """Cria índice OpenSearch se não existir."""
        dimension = dimension or config.EMBEDDING_DIM
        
        if self.client.indices.exists(index=self.index_name):
            print(f"📁 Índice '{self.index_name}' já existe")
            return
        
        # Mapeamento com campo knn_vector
        mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "text": {"type": "text", "analyzer": "standard"},
                    "title": {"type": "text", "analyzer": "standard"},
                    "court": {"type": "keyword"},
                    "code": {"type": "keyword"}, 
                    "article": {"type": "keyword"},
                    "date": {"type": "date", "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ss||epoch_millis"},
                    "meta": {"type": "object", "enabled": False},
                    "vector": {
                        "type": "knn_vector",
                        "dimension": dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil" if config.NORMALIZE_EMBEDDINGS else "l2",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    }
                }
            },
            "settings": {
                "index": {
                    "number_of_shards": shards,
                    "number_of_replicas": replicas,
                    "knn": True,
                    "knn.algo_param.ef_search": 100
                }
            }
        }
        
        print(f"🔄 Criando índice '{self.index_name}' (dim={dimension})")
        self.client.indices.create(index=self.index_name, body=mapping)
        print(f"✅ Índice criado com sucesso!")
    
    def index(self, docs: List[Doc]) -> None:
        """Indexa documentos no OpenSearch."""
        if not docs:
            return
            
        print(f"🔄 Indexando {len(docs)} documentos no OpenSearch...")
        
        # Gera embeddings
        texts = [doc.text for doc in docs]
        vectors = embeddings.encode_texts(texts)
        
        # Garante que o índice existe
        self.ensure_index()
        
        # Prepara documentos para bulk insert
        actions = []
        for doc, vector in zip(docs, vectors):
            action = {
                "_index": self.index_name,
                "_id": doc.id,
                "_source": {
                    "id": doc.id,
                    "text": doc.text,
                    "title": doc.title,
                    "court": doc.court,
                    "code": doc.code,
                    "article": doc.article,
                    "date": doc.date,
                    "meta": doc.meta,
                    "vector": vector.tolist()  # OpenSearch precisa de lista, não numpy array
                }
            }
            # Remove campos None
            action["_source"] = {k: v for k, v in action["_source"].items() if v is not None}
            actions.append(action)
        
        # Bulk insert
        try:
            success, failed = bulk(self.client, actions, refresh=True)
            print(f"✅ {success} documentos indexados, {len(failed)} falharam")
            
            if failed:
                for failure in failed[:3]:  # Mostra apenas primeiros 3 erros
                    print(f"❌ Erro: {failure}")
                    
        except Exception as e:
            print(f"❌ Erro no bulk insert: {e}")
            raise
    
    def search(self, query_vector: np.ndarray, k: int = 5) -> List[SearchResult]:
        """Busca documentos similares usando kNN."""
        try:
            # Query kNN básica
            query = {
                "size": k,
                "query": {
                    "knn": {
                        "vector": {
                            "vector": query_vector.tolist(),
                            "k": k
                        }
                    }
                },
                "_source": {
                    "excludes": ["vector"]  # Exclui vetor da resposta para economizar bandwidth
                }
            }
            
            response = self.client.search(index=self.index_name, body=query)
            
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                doc = Doc(
                    id=source["id"],
                    text=source["text"],
                    title=source.get("title"),
                    court=source.get("court"),
                    code=source.get("code"),
                    article=source.get("article"),
                    date=source.get("date"),
                    meta=source.get("meta")
                )
                
                # OpenSearch kNN retorna score normalizado [0,1]
                score = hit["_score"]
                results.append(SearchResult(doc=doc, score=score))
            
            return results
            
        except Exception as e:
            print(f"❌ Erro na busca OpenSearch: {e}")
            return []
    
    def get_doc_count(self) -> int:
        """Retorna número de documentos no índice."""
        try:
            response = self.client.count(index=self.index_name)
            return response["count"]
        except Exception:
            return 0
    
    def delete_index(self) -> None:
        """Remove o índice (útil para testes)."""
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            print(f"🗑️ Índice '{self.index_name}' removido")