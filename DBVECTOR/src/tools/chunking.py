"""
Chunking de documentos jurídicos usando LangChain.

Este módulo implementa estratégias de chunking otimizadas para documentos
jurídicos, preservando contexto semântico e metadados essenciais.
"""
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.schema import Doc


def chunk_documents(docs: List[Doc], chunk_size: int, overlap: int) -> List[Doc]:
    """
    Divide documentos em chunks menores usando LangChain RecursiveCharacterTextSplitter.
    
    Estratégia otimizada para texto jurídico:
    - Preserva sentenças completas quando possível
    - Mantém contexto com overlap entre chunks
    - Preserva metadados jurídicos (tribunal, artigo, data, etc.)
    - Adiciona metadados de chunking para rastreabilidade
    
    Args:
        docs: Lista de documentos Doc a serem divididos
        chunk_size: Tamanho máximo de cada chunk em caracteres
        overlap: Número de caracteres de sobreposição entre chunks
        
    Returns:
        Lista de Doc contendo chunks com metadados preservados e metadados de chunking
        
    Example:
        >>> docs = [Doc(id="doc1", text="texto longo...", title="Título")]
        >>> chunks = chunk_documents(docs, chunk_size=1000, overlap=200)
        >>> len(chunks) >= len(docs)
        True
    """
    # Configurar text splitter com separadores otimizados para texto jurídico
    # Ordem de prioridade: parágrafos > sentenças > palavras > caracteres
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=[
            "\n\n",  # Parágrafos
            "\n",    # Quebras de linha
            ". ",    # Fim de sentenças
            "; ",    # Ponto e vírgula (comum em textos jurídicos)
            ", ",    # Vírgulas
            " ",     # Espaços
            ""       # Caracteres individuais (fallback)
        ],
        is_separator_regex=False
    )
    
    chunked_docs = []
    
    for doc in docs:
        # Divide o texto do documento
        text_chunks = text_splitter.split_text(doc.text)
        
        # Se o documento não precisa ser dividido
        if len(text_chunks) == 1 and len(doc.text) <= chunk_size:
            # Marca como chunk único mas preserva original
            chunk_doc = Doc(
                id=f"{doc.id}_chunk_0",
                text=doc.text,
                title=doc.title,
                court=doc.court,
                code=doc.code,
                article=doc.article,
                date=doc.date,
                meta={
                    **(doc.meta or {}),
                    'original_id': doc.id,
                    'chunk_index': 0,
                    'char_start': 0,
                    'char_end': len(doc.text),
                    'is_chunk': True,
                    'total_chunks': 1
                }
            )
            chunked_docs.append(chunk_doc)
            continue
        
        # Processa múltiplos chunks
        char_position = 0
        for chunk_idx, chunk_text in enumerate(text_chunks):
            # Encontra posição exata do chunk no texto original
            # (considerando overlap, precisamos buscar a partir da última posição)
            chunk_start = doc.text.find(chunk_text, char_position)
            if chunk_start == -1:
                # Fallback se não encontrar (não deveria acontecer)
                chunk_start = char_position
            
            chunk_end = chunk_start + len(chunk_text)
            
            # Atualiza posição para próximo chunk
            # Subtrai overlap para buscar corretamente considerando sobreposição
            char_position = max(chunk_start + 1, chunk_end - overlap)
            
            # Cria novo Doc para o chunk
            chunk_doc = Doc(
                id=f"{doc.id}_chunk_{chunk_idx}",
                text=chunk_text,
                title=doc.title,
                court=doc.court,
                code=doc.code,
                article=doc.article,
                date=doc.date,
                meta={
                    **(doc.meta or {}),  # Preserva metadados originais
                    'original_id': doc.id,
                    'chunk_index': chunk_idx,
                    'char_start': chunk_start,
                    'char_end': chunk_end,
                    'is_chunk': True,
                    'total_chunks': len(text_chunks)
                }
            )
            
            chunked_docs.append(chunk_doc)
    
    # Ordena chunks por original_id e chunk_index para manter ordem lógica
    chunked_docs.sort(key=lambda d: (d.meta['original_id'], d.meta['chunk_index']))
    
    return chunked_docs
