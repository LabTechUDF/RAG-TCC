"""
Telemetria e Logging para Sistema RAG Jurídico
Registra métricas de latência, qualidade e uso para auditoria
"""
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum


class QueryMode(Enum):
    """Modos de operação da query"""
    RAG = "rag"
    SIMPLE_CHAT = "simple_chat"


@dataclass
class QueryTelemetry:
    """Dados de telemetria de uma query"""
    timestamp: str
    user_id: Optional[str]
    session_id: Optional[str]
    query_text: str
    query_mode: str
    
    # Métricas de performance
    total_latency_ms: float
    retrieval_latency_ms: Optional[float]
    llm_latency_ms: Optional[float]
    
    # Resultados RAG
    top_k: int
    documents_retrieved: int
    avg_score: Optional[float]
    
    # Backend info
    backend: str
    model_used: str
    
    # Filtros aplicados
    filters_applied: Dict[str, Any]
    
    # Resultados
    answer_length: int
    sources_count: int
    
    # Qualidade (se disponível)
    user_feedback: Optional[str] = None
    error: Optional[str] = None


class TelemetryLogger:
    """
    Logger de telemetria para sistema RAG.
    
    Registra todas as interações para:
    - Auditoria e compliance
    - Análise de performance
    - Métricas de qualidade
    - Debugging e troubleshooting
    """
    
    def __init__(self, log_dir: str = "logs/telemetry"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Logger estruturado
        self.logger = self._setup_logger()
        
        # Métricas em memória para estatísticas rápidas
        self.metrics = {
            'total_queries': 0,
            'rag_queries': 0,
            'simple_queries': 0,
            'total_latency_sum': 0.0,
            'errors': 0
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Configura logger estruturado"""
        logger = logging.getLogger('rag_telemetry')
        logger.setLevel(logging.INFO)
        
        # Handler para arquivo JSONL
        log_file = self.log_dir / f"queries_{datetime.now().strftime('%Y%m%d')}.jsonl"
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        
        # Handler para console (desenvolvimento)
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(console)
        
        return logger
    
    def log_query(self, telemetry: QueryTelemetry):
        """
        Registra uma query completa com toda telemetria.
        
        Args:
            telemetry: Dados de telemetria da query
        """
        # Log estruturado em JSONL
        log_entry = asdict(telemetry)
        self.logger.info(json.dumps(log_entry))
        
        # Atualiza métricas em memória
        self.metrics['total_queries'] += 1
        self.metrics['total_latency_sum'] += telemetry.total_latency_ms
        
        if telemetry.query_mode == QueryMode.RAG.value:
            self.metrics['rag_queries'] += 1
        else:
            self.metrics['simple_queries'] += 1
        
        if telemetry.error:
            self.metrics['errors'] += 1
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas coletadas"""
        total = self.metrics['total_queries']
        return {
            'total_queries': total,
            'rag_queries': self.metrics['rag_queries'],
            'simple_queries': self.metrics['simple_queries'],
            'avg_latency_ms': (
                self.metrics['total_latency_sum'] / total if total > 0 else 0
            ),
            'error_rate': (
                self.metrics['errors'] / total if total > 0 else 0
            )
        }
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any]
    ):
        """Registra erros do sistema"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'error',
            'error_type': error_type,
            'message': error_message,
            'context': context
        }
        self.logger.error(json.dumps(error_entry))
        self.metrics['errors'] += 1


class PerformanceTimer:
    """Context manager para medição de latência"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.elapsed_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
    
    def get_elapsed_ms(self) -> float:
        """Retorna tempo decorrido em milissegundos"""
        return self.elapsed_ms if self.elapsed_ms is not None else 0.0


# Singleton global para fácil acesso
_telemetry_logger: Optional[TelemetryLogger] = None


def get_telemetry_logger() -> TelemetryLogger:
    """Retorna instância global do TelemetryLogger"""
    global _telemetry_logger
    if _telemetry_logger is None:
        _telemetry_logger = TelemetryLogger()
    return _telemetry_logger


def log_query_execution(
    query: str,
    mode: QueryMode,
    total_latency: float,
    result_count: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    retrieval_latency: Optional[float] = None,
    llm_latency: Optional[float] = None,
    backend: str = "faiss",
    model: str = "gpt-4o-mini",
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = 5,
    avg_score: Optional[float] = None,
    error: Optional[str] = None
):
    """
    Helper function para log rápido de queries.
    
    Args:
        query: Texto da query
        mode: Modo de operação (RAG ou SIMPLE_CHAT)
        total_latency: Latência total em ms
        result_count: Número de resultados retornados
        user_id: ID do usuário (opcional)
        session_id: ID da sessão (opcional)
        retrieval_latency: Latência da busca vetorial em ms
        llm_latency: Latência da LLM em ms
        backend: Backend usado (faiss/opensearch)
        model: Modelo LLM usado
        filters: Filtros aplicados
        top_k: Número de documentos solicitados
        avg_score: Score médio dos documentos recuperados
        error: Mensagem de erro se houver
    """
    logger = get_telemetry_logger()
    
    telemetry = QueryTelemetry(
        timestamp=datetime.now().isoformat(),
        user_id=user_id,
        session_id=session_id,
        query_text=query,
        query_mode=mode.value,
        total_latency_ms=total_latency,
        retrieval_latency_ms=retrieval_latency,
        llm_latency_ms=llm_latency,
        top_k=top_k,
        documents_retrieved=result_count,
        avg_score=avg_score,
        backend=backend,
        model_used=model,
        filters_applied=filters or {},
        answer_length=0,  # Será preenchido pelo handler da resposta
        sources_count=result_count,
        error=error
    )
    
    logger.log_query(telemetry)
