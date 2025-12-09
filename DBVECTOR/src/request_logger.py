"""
Request Logger para observabilidade das requisições RAG.
Cria arquivos de log individuais por requisição com timestamp.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Diretório de logs
LOGS_DIR = Path(__file__).parent.parent / "logs" / "requests"


def ensure_logs_dir():
    """Garante que o diretório de logs existe."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_request_logger(request_id: str = None) -> "RequestLogger":
    """Factory para criar um RequestLogger."""
    return RequestLogger(request_id)


class RequestLogger:
    """Logger para uma requisição individual."""

    def __init__(self, request_id: str = None):
        ensure_logs_dir()

        self.timestamp = datetime.now()
        self.request_id = request_id or self.timestamp.strftime("%Y%m%d_%H%M%S_%f")
        self.log_file = LOGS_DIR / f"{self.request_id}.json"

        self.data = {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "request": {},
            "history": [],
            "normalization": {},
            "retrieved_documents": [],
            "llm_prompt": "",
            "llm_response": "",
            "final_response": "",
            "metadata": {},
            "errors": [],
            "timing": {}
        }

        self._start_time = datetime.now()

    def log_request(self, prompt: str, use_rag: bool, k: int, metadados: Dict = None):
        """Registra os dados da requisição."""
        self.data["request"] = {
            "prompt": prompt,
            "use_rag": use_rag,
            "k": k,
            "metadados": metadados or {}
        }

    def log_history(self, history: List[Dict[str, str]]):
        """Registra o histórico de conversa."""
        self.data["history"] = history or []

    def log_normalization(self, query_normalizada: Dict):
        """Registra o resultado da normalização."""
        self.data["normalization"] = query_normalizada

    def log_retrieved_documents(self, documents: List[Dict]):
        """Registra os documentos recuperados."""
        self.data["retrieved_documents"] = documents

    def log_llm_prompt(self, prompt: str):
        """Registra o prompt enviado ao LLM."""
        self.data["llm_prompt"] = prompt

    def log_llm_response(self, response: str):
        """Registra a resposta do LLM."""
        self.data["llm_response"] = response

    def log_final_response(self, response: str):
        """Registra a resposta final enviada ao usuário."""
        self.data["final_response"] = response

    def log_error(self, error: str, context: str = None):
        """Registra um erro."""
        self.data["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "context": context
        })

    def log_timing(self, step: str, duration_ms: float):
        """Registra tempo de execução de um passo."""
        self.data["timing"][step] = duration_ms

    def add_metadata(self, key: str, value: Any):
        """Adiciona metadados extras."""
        self.data["metadata"][key] = value

    def save(self):
        """Salva o log em arquivo JSON."""
        try:
            # Calcula tempo total
            total_time = (datetime.now() - self._start_time).total_seconds() * 1000
            self.data["timing"]["total_ms"] = total_time
            self.data["completed_at"] = datetime.now().isoformat()

            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

            logging.info(f"Request log saved: {self.log_file}")
            return str(self.log_file)

        except Exception as e:
            logging.error(f"Error saving request log: {e}")
            return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.log_error(str(exc_val), f"{exc_type.__name__}")
        self.save()


# Função auxiliar para logging rápido
def log_rag_request(
    prompt: str,
    history: List[Dict] = None,
    documents: List[Dict] = None,
    llm_prompt: str = None,
    llm_response: str = None,
    final_response: str = None,
    metadata: Dict = None
) -> str:
    """
    Função de conveniência para logar uma requisição RAG completa.
    Retorna o caminho do arquivo de log.
    """
    logger = RequestLogger()
    logger.log_request(prompt, use_rag=True, k=10)

    if history:
        logger.log_history(history)
    if documents:
        logger.log_retrieved_documents(documents)
    if llm_prompt:
        logger.log_llm_prompt(llm_prompt)
    if llm_response:
        logger.log_llm_response(llm_response)
    if final_response:
        logger.log_final_response(final_response)
    if metadata:
        for k, v in metadata.items():
            logger.add_metadata(k, v)

    return logger.save()
