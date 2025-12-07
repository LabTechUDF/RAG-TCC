"""
Tests for the LangChain RAG module.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.api.langchain_rag import LangChainRAG, RAGResponse
from src.schema import Doc, SearchResult


class MockLLMResult:
    """Simple mock for LLM results with content attribute."""
    def __init__(self, text):
        self.content = text


@pytest.fixture
def mock_vector_store():
    """Fixture for mocked vector store."""
    vector_store = Mock()
    
    # Mock search method returns list of SearchResult
    doc1 = Doc(
        id="doc1",
        text="Documento 1 sobre prisão preventiva.",
        title="HC 123456",
        court="STF",
        article="art1",
        code="CPP",
        date="2024-01-01",
        meta={}
    )
    doc2 = Doc(
        id="doc2",
        text="Documento 2 sobre medidas cautelares.",
        title="HC 789012",
        court="STJ",
        article="art2",
        code="CPP",
        date="2024-01-02",
        meta={}
    )
    
    search_results = [
        SearchResult(doc=doc1, score=0.95),
        SearchResult(doc=doc2, score=0.90),
    ]
    
    vector_store.search.return_value = search_results
    return vector_store


@patch('src.api.langchain_rag.ChatOpenAI')
def test_langchain_rag_initialization(mock_llm_cls, mock_vector_store):
    """Test that LangChainRAG initializes correctly."""
    mock_llm = Mock()
    mock_llm_cls.return_value = mock_llm
    
    rag = LangChainRAG(
        vector_store=mock_vector_store,
        model_name="gpt-4o-mini",
        temperature=0.3,
        api_key="fake_key"
    )
    
    assert rag.vector_store is mock_vector_store
    assert rag.llm is mock_llm
    assert rag.prompt is not None
    
    # Verify ChatOpenAI was called with correct parameters
    mock_llm_cls.assert_called_once_with(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=1000,
        api_key="fake_key"
    )


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_success(mock_llm_cls, mock_vector_store):
    """Test successful RAG execution with mocked LLM."""
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    # Patch the prompt's __or__ method to return a mockable chain
    with patch.object(rag, 'prompt') as mock_prompt:
        mock_result = MockLLMResult("Esta é a resposta final baseada nos documentos.")
        
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        # Execute RAG
        result = rag.run_rag(
            query="Qual é o artigo 1?",
            k=2
        )
        
        # Verify results
        assert isinstance(result, RAGResponse)
        assert result.answer == "Esta é a resposta final baseada nos documentos."
        assert len(result.sources) == 2
        assert result.documents_retrieved == 2
        assert result.model_used == "gpt-4o-mini"
        
        # Verify vector_store.search was called
        mock_vector_store.search.assert_called_once_with("Qual é o artigo 1?", k=2)
        
        # Verify chain was invoked
        assert mock_chain.invoke.called
        call_args = mock_chain.invoke.call_args[0][0]
        assert "context" in call_args
        assert "question" in call_args
        assert call_args["question"] == "Qual é o artigo 1?"


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_with_filters(mock_llm_cls, mock_vector_store):
    """Test RAG with metadata filters."""
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    with patch.object(rag, 'prompt') as mock_prompt:
        mock_result = MockLLMResult("Resposta filtrada por metadados.")
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        # Execute RAG with filters
        result = rag.run_rag(
            query="Buscar artigo específico",
            k=2,
            filters={"court": "STF"}
        )
        
        # Verify vector_store.search was called
        mock_vector_store.search.assert_called_once_with("Buscar artigo específico", k=2)
        
        assert result.answer == "Resposta filtrada por metadados."


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_no_documents_found(mock_llm_cls, mock_vector_store):
    """Test RAG when no documents are retrieved."""
    # Setup mocks
    mock_llm = Mock()
    mock_llm_cls.return_value = mock_llm
    
    # Configure vector_store to return empty list
    mock_vector_store.search.return_value = []
    
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    # Execute RAG
    result = rag.run_rag(query="Query sem resultados", k=5)
    
    # Verify behavior when no documents found
    assert isinstance(result, RAGResponse)
    assert len(result.sources) == 0
    assert result.documents_retrieved == 0
    assert "Não foram encontrados documentos relevantes" in result.answer
    
    # LLM should NOT be invoked when no documents
    assert not mock_llm.invoke.called


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_llm_error_handling(mock_llm_cls, mock_vector_store):
    """Test error handling when LLM fails."""
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    with patch.object(rag, 'prompt') as mock_prompt:
        mock_chain = Mock()
        mock_chain.invoke.side_effect = Exception("LLM API error")
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        # Execute RAG and expect error to propagate
        with pytest.raises(Exception, match="LLM API error"):
            rag.run_rag(query="Test query", k=2)


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_vector_store_error_handling(mock_llm_cls, mock_vector_store):
    """Test error handling when vector store fails."""
    # Setup mocks
    mock_llm = Mock()
    mock_llm_cls.return_value = mock_llm
    
    # Configure vector_store to raise error
    mock_vector_store.search.side_effect = Exception("Vector store connection error")
    
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    # Execute RAG and expect error to propagate
    with pytest.raises(Exception, match="Vector store connection error"):
        rag.run_rag(query="Test query", k=2)


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_context_formatting(mock_llm_cls, mock_vector_store):
    """Test that context is formatted correctly from retrieved documents."""
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    with patch.object(rag, 'prompt') as mock_prompt:
        mock_result = MockLLMResult("Resposta com contexto formatado.")
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        # Execute RAG
        result = rag.run_rag(query="Consulta teste", k=2)
        
        # Verify chain was invoked with context
        assert mock_chain.invoke.called
        call_args = mock_chain.invoke.call_args[0][0]
        context = call_args["context"]
        
        # Context should contain document texts
        assert "Documento 1 sobre prisão preventiva" in context
        assert "Documento 2 sobre medidas cautelares" in context


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_empty_query(mock_llm_cls, mock_vector_store):
    """Test RAG with empty query string."""
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    with patch.object(rag, 'prompt') as mock_prompt:
        mock_result = MockLLMResult("Por favor, forneça uma pergunta válida.")
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        # Execute RAG with empty query
        result = rag.run_rag(query="", k=5)
        
        # Should still return valid result structure
        assert isinstance(result, RAGResponse)
        assert "answer" in result.__dict__
        assert "sources" in result.__dict__


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_custom_temperature(mock_llm_cls, mock_vector_store):
    """Test that temperature parameter is respected."""
    mock_llm = Mock()
    mock_llm_cls.return_value = mock_llm
    
    # Initialize with custom temperature
    rag = LangChainRAG(
        vector_store=mock_vector_store,
        api_key="fake_key",
        temperature=0.9
    )
    
    # Verify ChatOpenAI was initialized with correct temperature
    mock_llm_cls.assert_called_once_with(
        model="gpt-4o-mini",
        temperature=0.9,
        max_tokens=1000,
        api_key="fake_key"
    )


@patch('src.api.langchain_rag.ChatOpenAI')
def test_run_rag_stats_tracking(mock_llm_cls, mock_vector_store):
    """Test that statistics are tracked correctly."""
    rag = LangChainRAG(vector_store=mock_vector_store, api_key="fake_key")
    
    with patch.object(rag, 'prompt') as mock_prompt:
        mock_result = MockLLMResult("Resposta de teste.")
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        # Execute RAG twice
        rag.run_rag(query="Query 1", k=2)
        rag.run_rag(query="Query 2", k=3)
        
        # Check stats
        assert rag.stats['queries_processed'] == 2
        assert rag.stats['llm_calls'] == 2
        assert rag.stats['total_documents_retrieved'] == 4  # 2 + 2
        assert rag.stats['errors'] == 0
