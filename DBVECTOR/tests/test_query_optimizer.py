"""
Testes para QueryOptimizer com LLM.
"""
import pytest
from unittest.mock import Mock, patch
from src.tools.query_optimizer import QueryOptimizer
from src.tools.query_builder import QueryContext


class MockLLMResult:
    """Simple mock for LLM results with content attribute."""
    def __init__(self, text):
        self.content = text


def test_query_optimizer_initialization_without_api_key(monkeypatch):
    """Testa inicialização sem API key (deve usar fallback)"""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    
    optimizer = QueryOptimizer(api_key=None)
    
    # Deve ter inicializado em modo fallback
    assert optimizer.llm is None
    assert optimizer.prompt is None


def test_query_optimizer_fallback_mode(monkeypatch):
    """Testa modo fallback quando LLM não disponível"""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    
    optimizer = QueryOptimizer(api_key=None)
    
    context = QueryContext(
        user_query="prisão preventiva STF",
        court_filter="STF"
    )
    
    result = optimizer.optimize_query(context)
    
    # Deve ter usado fallback
    assert optimizer.stats['fallback_used'] > 0
    assert result.optimized_text is not None
    assert result.filters is not None


@patch('src.tools.query_optimizer.ChatOpenAI')
def test_query_optimizer_with_mock_llm(mock_llm_cls):
    """Testa otimização com LLM mockado"""
    optimizer = QueryOptimizer(api_key="fake_key")
    
    with patch.object(optimizer, 'prompt') as mock_prompt:
        mock_result = MockLLMResult('''
        {
            "optimized_text": "prisão preventiva jurisprudência Supremo Tribunal Federal",
            "requires_clarification": false,
            "clarification_questions": [],
            "filters": {
                "court": "STF",
                "article": null,
                "date_range": null
            }
        }
        ''')
        
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        context = QueryContext(
            user_query="prisão preventiva STF"
        )
        
        result = optimizer.optimize_query(context)
        
        # Verifica resultado
        assert "Supremo Tribunal Federal" in result.optimized_text
        assert result.requires_clarification is False
        assert result.filters.get('court') == 'STF'
        assert optimizer.stats['llm_calls'] > 0


@patch('src.tools.query_optimizer.ChatOpenAI')
def test_query_optimizer_clarification_needed(mock_llm_cls):
    """Testa detecção de necessidade de esclarecimento"""
    optimizer = QueryOptimizer(api_key="fake_key")
    
    with patch.object(optimizer, 'prompt') as mock_prompt:
        mock_result = MockLLMResult('''
        {
            "optimized_text": "isso",
            "requires_clarification": true,
            "clarification_questions": [
                "Você poderia especificar a que processo você se refere?",
                "Qual tribunal você deseja consultar?"
            ],
            "filters": {}
        }
        ''')
        
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        context = QueryContext(user_query="isso")
        
        result = optimizer.optimize_query(context)
        
        assert result.requires_clarification is True
        assert len(result.clarification_questions) == 2


@patch('src.tools.query_optimizer.ChatOpenAI')
def test_query_optimizer_filter_extraction(mock_llm_cls):
    """Testa extração de filtros estruturados"""
    optimizer = QueryOptimizer(api_key="fake_key")
    
    with patch.object(optimizer, 'prompt') as mock_prompt:
        mock_result = MockLLMResult('''
        {
            "optimized_text": "habeas corpus artigo 312 Código de Processo Penal",
            "requires_clarification": false,
            "clarification_questions": [],
            "filters": {
                "court": "STF",
                "article": "312",
                "date_range": null
            }
        }
        ''')
        
        mock_chain = Mock()
        mock_chain.invoke.return_value = mock_result
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        context = QueryContext(
            user_query="HC art 312 STF"
        )
        
        result = optimizer.optimize_query(context)
        
        assert result.filters.get('court') == 'STF'
        assert result.filters.get('article') == '312'


@patch('src.tools.query_optimizer.ChatOpenAI')
def test_query_optimizer_handles_llm_error(mock_llm_cls):
    """Testa tratamento de erro do LLM"""
    optimizer = QueryOptimizer(api_key="fake_key")
    
    with patch.object(optimizer, 'prompt') as mock_prompt:
        mock_chain = Mock()
        mock_chain.invoke.side_effect = Exception("API Error")
        mock_prompt.__or__ = Mock(return_value=mock_chain)
        
        context = QueryContext(user_query="test query")
        
        # Deve retornar resultado via fallback sem lançar exceção
        result = optimizer.optimize_query(context)
        
        assert result is not None
        assert optimizer.stats['errors'] > 0
        assert optimizer.stats['fallback_used'] > 0


@patch('src.tools.query_optimizer.ChatOpenAI')
def test_query_optimizer_invalid_json_response(mock_llm_cls):
    """Testa tratamento de resposta JSON inválida"""
    mock_llm = Mock()
    mock_result = Mock()
    mock_result.content = "Esta não é uma resposta JSON válida"
    
    # Mock the pipe operator (|) to return a chain that invokes correctly
    mock_chain = Mock()
    mock_chain.invoke.return_value = mock_result
    mock_llm.__or__ = Mock(return_value=mock_chain)
    
    mock_llm_cls.return_value = mock_llm
    
    optimizer = QueryOptimizer(api_key="fake_key")
    
    context = QueryContext(user_query="test")
    
    # Deve usar fallback ao falhar no parse
    result = optimizer.optimize_query(context)
    
    assert result is not None
    assert optimizer.stats['errors'] > 0


def test_query_optimizer_stats():
    """Testa coleta de estatísticas"""
    optimizer = QueryOptimizer(api_key=None)  # Modo fallback
    
    context = QueryContext(user_query="test query")
    
    optimizer.optimize_query(context)
    optimizer.optimize_query(context)
    
    stats = optimizer.get_stats()
    
    assert stats['queries_optimized'] == 2
    assert stats['fallback_used'] == 2
    assert 'llm_calls' in stats
    assert 'errors' in stats
