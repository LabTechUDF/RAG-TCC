"""
Testes para o módulo de chunking de documentos.
"""
import pytest
from src.tools.chunking import chunk_documents
from src.schema import Doc


def test_chunk_single_doc():
    """Testa chunking de um documento único"""
    docs = [
        Doc(
            id="test1",
            text="Este é um texto curto que não precisa ser dividido.",
            title="Teste 1"
        )
    ]
    
    chunks = chunk_documents(docs, chunk_size=1000, overlap=100)
    
    assert len(chunks) == 1
    assert chunks[0].id == "test1_chunk_0"
    assert chunks[0].meta['original_id'] == "test1"
    assert chunks[0].meta['chunk_index'] == 0
    assert chunks[0].meta['is_chunk'] is True


def test_chunk_long_doc():
    """Testa chunking de documento longo que requer divisão"""
    long_text = ". ".join([f"Sentença número {i}" for i in range(100)])
    
    docs = [
        Doc(
            id="long_doc",
            text=long_text,
            title="Documento Longo",
            court="STF"
        )
    ]
    
    chunks = chunk_documents(docs, chunk_size=200, overlap=50)
    
    # Deve gerar múltiplos chunks
    assert len(chunks) > 1
    
    # Todos chunks devem ter metadata correta
    for i, chunk in enumerate(chunks):
        assert chunk.id == f"long_doc_chunk_{i}"
        assert chunk.meta['original_id'] == "long_doc"
        assert chunk.meta['chunk_index'] == i
        assert chunk.meta['is_chunk'] is True
        assert 'char_start' in chunk.meta
        assert 'char_end' in chunk.meta
        
        # Metadados originais preservados
        assert chunk.title == "Documento Longo"
        assert chunk.court == "STF"


def test_chunk_preserves_metadata():
    """Testa que metadados originais são preservados nos chunks"""
    docs = [
        Doc(
            id="doc_meta",
            text="Texto " * 500,  # Texto longo
            title="Título Teste",
            court="STJ",
            code="HC",
            article="123",
            date="2024-01-01",
            meta={"custom": "value", "tags": ["tag1", "tag2"]}
        )
    ]
    
    chunks = chunk_documents(docs, chunk_size=300, overlap=50)
    
    for chunk in chunks:
        # Campos principais preservados
        assert chunk.title == "Título Teste"
        assert chunk.court == "STJ"
        assert chunk.code == "HC"
        assert chunk.article == "123"
        assert chunk.date == "2024-01-01"
        
        # Metadados customizados preservados
        assert chunk.meta['custom'] == "value"
        assert chunk.meta['tags'] == ["tag1", "tag2"]


def test_chunk_ordering():
    """Testa que chunks são retornados em ordem correta"""
    docs = [
        Doc(id="doc1", text="A" * 500, title="Doc 1"),
        Doc(id="doc2", text="B" * 500, title="Doc 2"),
        Doc(id="doc3", text="C" * 500, title="Doc 3")
    ]
    
    chunks = chunk_documents(docs, chunk_size=200, overlap=50)
    
    # Verifica ordem: todos chunks de doc1, depois doc2, depois doc3
    current_original_id = None
    last_chunk_index = -1
    
    for chunk in chunks:
        original_id = chunk.meta['original_id']
        chunk_index = chunk.meta['chunk_index']
        
        if original_id != current_original_id:
            # Novo documento
            current_original_id = original_id
            last_chunk_index = -1
        
        # Chunk index deve ser sequencial
        assert chunk_index == last_chunk_index + 1
        last_chunk_index = chunk_index


def test_chunk_sizes():
    """Testa que chunks respeitam tamanho máximo"""
    text = "palavra " * 1000
    
    docs = [Doc(id="size_test", text=text)]
    
    chunks = chunk_documents(docs, chunk_size=500, overlap=100)
    
    for chunk in chunks:
        # Chunks não devem exceder significativamente o tamanho (tolerância para separadores)
        assert len(chunk.text) <= 600  # Margem de 20%


def test_chunk_overlap():
    """Testa que há overlap entre chunks consecutivos"""
    # Texto facilmente identificável
    words = [f"palavra{i:03d}" for i in range(200)]
    text = " ".join(words)
    
    docs = [Doc(id="overlap_test", text=text)]
    
    chunks = chunk_documents(docs, chunk_size=300, overlap=100)
    
    if len(chunks) > 1:
        # Verifica overlap entre chunks consecutivos
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i]
            chunk2 = chunks[i + 1]
            
            # Deve haver palavras em comum
            words1 = set(chunk1.text.split())
            words2 = set(chunk2.text.split())
            overlap_words = words1 & words2
            
            assert len(overlap_words) > 0, "Chunks consecutivos devem ter overlap"


def test_empty_docs_list():
    """Testa comportamento com lista vazia"""
    chunks = chunk_documents([], chunk_size=1000, overlap=100)
    assert len(chunks) == 0


def test_chunk_custom_overlap_zero():
    """Testa chunking sem overlap"""
    text = "A" * 1000
    
    docs = [Doc(id="no_overlap", text=text)]
    
    chunks = chunk_documents(docs, chunk_size=200, overlap=0)
    
    assert len(chunks) > 1
    
    # Verifica que não há overlap
    for i in range(len(chunks) - 1):
        assert chunks[i].meta['char_end'] <= chunks[i + 1].meta['char_start']
