"""
Utilitário para chunking de documentos jurídicos.
Implementa quebra inteligente com overlap para preservar contexto.
"""
import re
from typing import List, Dict, Any
import tiktoken

from src.rag_schemas import ChunkingConfig, DocumentoParaChunking


class DocumentChunker:
    """
    Chunker para documentos jurídicos com overlap.
    
    Usa tokenização para garantir chunks de tamanho consistente.
    """
    
    def __init__(self, config: ChunkingConfig = None):
        """
        Inicializa o chunker.
        
        Args:
            config: Configuração de chunking (usa defaults se None)
        """
        self.config = config or ChunkingConfig()
        
        # Tokenizador (cl100k_base é usado pelo GPT-4)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback para estimativa aproximada
            self.encoding = None
    
    def chunk_documento(
        self,
        documento: DocumentoParaChunking
    ) -> List[Dict[str, Any]]:
        """
        Quebra documento em chunks com overlap.
        
        Args:
            documento: Documento a ser quebrado
            
        Returns:
            Lista de dicts com chunks e metadados
        """
        texto = documento.texto
        
        # Conta tokens do texto completo
        total_tokens = self._count_tokens(texto)
        
        # Se documento é pequeno, retorna como chunk único
        if total_tokens <= self.config.tamanho_max:
            return [{
                "idDocumentoGlobal": documento.id,
                "idChunk": f"{documento.id}_chunk_0",
                "texto": texto,
                "metadata": {
                    **documento.metadata,
                    "posicaoChunk": 0,
                    "totalChunks": 1,
                    "tokensChunk": total_tokens
                }
            }]
        
        # Quebra em chunks
        chunks = self._split_into_chunks(texto)
        
        # Monta resultado com metadados
        resultado = []
        for i, chunk_texto in enumerate(chunks):
            chunk_dict = {
                "idDocumentoGlobal": documento.id,
                "idChunk": f"{documento.id}_chunk_{i}",
                "texto": chunk_texto,
                "metadata": {
                    **documento.metadata,
                    "posicaoChunk": i,
                    "totalChunks": len(chunks),
                    "tokensChunk": self._count_tokens(chunk_texto)
                }
            }
            resultado.append(chunk_dict)
        
        return resultado
    
    def _split_into_chunks(self, texto: str) -> List[str]:
        """
        Divide texto em chunks com overlap usando separadores hierárquicos.
        """
        chunks = []
        inicio = 0
        
        while inicio < len(texto):
            # Define fim do chunk
            fim = inicio + self._estimate_chars_for_tokens(self.config.tamanho_alvo)
            
            # Se é o último pedaço, pega até o fim
            if fim >= len(texto):
                chunk = texto[inicio:].strip()
                if chunk:
                    chunks.append(chunk)
                break
            
            # Tenta encontrar ponto de quebra natural
            ponto_quebra = self._find_break_point(
                texto,
                inicio,
                fim,
                self.config.separadores
            )
            
            # Extrai chunk
            chunk = texto[inicio:ponto_quebra].strip()
            if chunk:
                chunks.append(chunk)
            
            # Calcula próximo início com overlap
            overlap_chars = self._estimate_chars_for_tokens(self.config.overlap)
            inicio = max(inicio + 1, ponto_quebra - overlap_chars)
        
        return chunks
    
    def _find_break_point(
        self,
        texto: str,
        inicio: int,
        fim_ideal: int,
        separadores: List[str]
    ) -> int:
        """
        Encontra melhor ponto de quebra usando separadores hierárquicos.
        """
        # Janela de busca (±10% do fim ideal)
        margem = int((fim_ideal - inicio) * 0.1)
        busca_inicio = max(inicio, fim_ideal - margem)
        busca_fim = min(len(texto), fim_ideal + margem)
        
        # Tenta cada separador na ordem de preferência
        for separador in separadores:
            # Busca última ocorrência do separador na janela
            ultimas_ocorrencias = []
            pos = busca_inicio
            
            while pos < busca_fim:
                idx = texto.find(separador, pos, busca_fim)
                if idx == -1:
                    break
                ultimas_ocorrencias.append(idx)
                pos = idx + len(separador)
            
            if ultimas_ocorrencias:
                # Retorna posição mais próxima do fim ideal
                melhor = min(
                    ultimas_ocorrencias,
                    key=lambda x: abs(x - fim_ideal)
                )
                return melhor + len(separador)
        
        # Fallback: corta no fim ideal
        return min(fim_ideal, len(texto))
    
    def _count_tokens(self, texto: str) -> int:
        """Conta tokens no texto."""
        if self.encoding:
            return len(self.encoding.encode(texto))
        else:
            # Estimativa: ~4 chars por token (média para português)
            return len(texto) // 4
    
    def _estimate_chars_for_tokens(self, num_tokens: int) -> int:
        """Estima número de caracteres para N tokens."""
        # Usa média de 4 chars por token
        return num_tokens * 4


def chunk_documentos_batch(
    documentos: List[DocumentoParaChunking],
    config: ChunkingConfig = None
) -> List[Dict[str, Any]]:
    """
    Chunka múltiplos documentos em batch.
    
    Args:
        documentos: Lista de documentos para chunking
        config: Configuração de chunking
        
    Returns:
        Lista flat de todos os chunks
    """
    chunker = DocumentChunker(config)
    
    todos_chunks = []
    for doc in documentos:
        chunks_doc = chunker.chunk_documento(doc)
        todos_chunks.extend(chunks_doc)
    
    return todos_chunks


# ========================================
# FUNÇÃO AUXILIAR PARA PREPROCESSAMENTO
# ========================================

def preprocessar_texto_juridico(texto: str) -> str:
    """
    Preprocessa texto jurídico para melhorar chunking.
    
    - Remove múltiplos espaços
    - Normaliza quebras de linha
    - Remove caracteres de controle
    """
    # Remove caracteres de controle
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    
    # Normaliza quebras de linha
    texto = re.sub(r'\r\n', '\n', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    
    # Remove múltiplos espaços
    texto = re.sub(r' +', ' ', texto)
    
    # Remove espaços no início/fim de linhas
    linhas = [linha.strip() for linha in texto.split('\n')]
    texto = '\n'.join(linhas)
    
    return texto.strip()
