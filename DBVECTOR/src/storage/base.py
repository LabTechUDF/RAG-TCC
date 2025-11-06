"""
Interface base para stores de busca vetorial.
"""
from abc import ABC, abstractmethod
from typing import List
import numpy as np
from src.schema import Doc, SearchResult


class VectorStore(ABC):
    """Interface abstrata para stores de busca vetorial."""
    
    @abstractmethod
    def index(self, docs: List[Doc]) -> None:
        """
        Indexa documentos no store.
        
        Args:
            docs: Lista de documentos para indexar
        """
        pass
    
    @abstractmethod
    def search(self, query_vector: np.ndarray, k: int = 5) -> List[SearchResult]:
        """
        Busca documentos similares ao vetor query.
        
        Args:
            query_vector: Vetor de consulta (embedding)
            k: Número de resultados a retornar
            
        Returns:
            Lista de resultados ordenados por relevância (score desc)
        """
        pass
    
    @abstractmethod
    def get_doc_count(self) -> int:
        """Retorna número total de documentos indexados."""
        pass