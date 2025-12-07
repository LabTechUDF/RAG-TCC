"""
Gerenciador de memória conversacional para RAG.

Este módulo implementa gerenciamento de histórico de conversas
usando LangChain Memory components.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage


@dataclass
class ConversationSession:
    """Representa uma sessão de conversa"""
    session_id: str
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    memory: ConversationBufferMemory = field(default_factory=lambda: ConversationBufferMemory(
        return_messages=True,
        memory_key="chat_history"
    ))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationManager:
    """
    Gerencia múltiplas sessões de conversa em memória.
    
    Features:
    - Armazenamento de histórico por session_id
    - Integração com LangChain Memory
    - Limpeza automática de sessões antigas (opcional)
    - Export/import de histórico
    
    Limitações:
    - Armazenamento em memória (perdido ao reiniciar)
    - Para produção, considere Redis ou banco de dados
    """
    
    def __init__(
        self,
        max_sessions: int = 1000,
        max_history_per_session: int = 50
    ):
        """
        Inicializa gerenciador de conversas.
        
        Args:
            max_sessions: Número máximo de sessões simultâneas
            max_history_per_session: Máximo de mensagens por sessão
        """
        self.sessions: Dict[str, ConversationSession] = {}
        self.max_sessions = max_sessions
        self.max_history_per_session = max_history_per_session
    
    def get_or_create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> ConversationSession:
        """
        Obtém sessão existente ou cria nova.
        
        Args:
            session_id: ID único da sessão
            user_id: ID do usuário (opcional)
            
        Returns:
            ConversationSession
        """
        if session_id not in self.sessions:
            # Limpa sessões antigas se necessário
            if len(self.sessions) >= self.max_sessions:
                self._cleanup_old_sessions()
            
            # Cria nova sessão
            self.sessions[session_id] = ConversationSession(
                session_id=session_id,
                user_id=user_id
            )
        
        # Atualiza timestamp de atividade
        self.sessions[session_id].last_activity = datetime.now()
        
        return self.sessions[session_id]
    
    def add_exchange(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        user_id: Optional[str] = None
    ):
        """
        Adiciona troca de mensagens ao histórico.
        
        Args:
            session_id: ID da sessão
            user_message: Mensagem do usuário
            assistant_message: Resposta do assistente
            user_id: ID do usuário (opcional)
        """
        session = self.get_or_create_session(session_id, user_id)
        
        # Adiciona à memória do LangChain
        session.memory.save_context(
            {"input": user_message},
            {"output": assistant_message}
        )
        
        # Limita tamanho do histórico
        self._trim_session_history(session)
    
    def get_history(
        self,
        session_id: str,
        as_messages: bool = False
    ) -> List[Dict[str, str]]:
        """
        Recupera histórico de uma sessão.
        
        Args:
            session_id: ID da sessão
            as_messages: Se True, retorna como lista de dicts {user: ..., assistant: ...}
            
        Returns:
            Lista de mensagens do histórico
        """
        if session_id not in self.sessions:
            return []
        
        session = self.sessions[session_id]
        
        # Obtém mensagens da memória
        memory_vars = session.memory.load_memory_variables({})
        messages = memory_vars.get("chat_history", [])
        
        if as_messages:
            # Converte para formato dict simplificado
            formatted = []
            for i in range(0, len(messages), 2):
                if i + 1 < len(messages):
                    formatted.append({
                        "user": messages[i].content if hasattr(messages[i], 'content') else str(messages[i]),
                        "assistant": messages[i + 1].content if hasattr(messages[i + 1], 'content') else str(messages[i + 1])
                    })
            return formatted
        
        return messages
    
    def clear_session(self, session_id: str):
        """Limpa histórico de uma sessão"""
        if session_id in self.sessions:
            self.sessions[session_id].memory.clear()
    
    def delete_session(self, session_id: str):
        """Remove sessão completamente"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações sobre uma sessão"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        history = self.get_history(session_id, as_messages=True)
        
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(history),
            "metadata": session.metadata
        }
    
    def list_sessions(
        self,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista todas as sessões ativas.
        
        Args:
            user_id: Filtrar por usuário (opcional)
            
        Returns:
            Lista de informações de sessões
        """
        sessions_info = []
        
        for session in self.sessions.values():
            # Filtra por user_id se fornecido
            if user_id is not None and session.user_id != user_id:
                continue
            
            info = self.get_session_info(session.session_id)
            if info:
                sessions_info.append(info)
        
        # Ordena por atividade mais recente
        sessions_info.sort(key=lambda s: s["last_activity"], reverse=True)
        
        return sessions_info
    
    def export_session(self, session_id: str) -> Optional[str]:
        """
        Exporta sessão como JSON.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            String JSON com histórico e metadados
        """
        info = self.get_session_info(session_id)
        if not info:
            return None
        
        history = self.get_history(session_id, as_messages=True)
        
        export_data = {
            **info,
            "history": history
        }
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    
    def import_session(self, json_data: str) -> str:
        """
        Importa sessão de JSON.
        
        Args:
            json_data: String JSON com dados da sessão
            
        Returns:
            session_id da sessão importada
        """
        data = json.loads(json_data)
        
        session_id = data["session_id"]
        user_id = data.get("user_id")
        history = data.get("history", [])
        
        # Cria sessão
        session = self.get_or_create_session(session_id, user_id)
        
        # Restaura histórico
        for exchange in history:
            session.memory.save_context(
                {"input": exchange["user"]},
                {"output": exchange["assistant"]}
            )
        
        # Restaura metadata
        session.metadata = data.get("metadata", {})
        
        return session_id
    
    def _trim_session_history(self, session: ConversationSession):
        """Limita tamanho do histórico de uma sessão"""
        memory_vars = session.memory.load_memory_variables({})
        messages = memory_vars.get("chat_history", [])
        
        # Se excedeu limite, remove mensagens mais antigas
        if len(messages) > self.max_history_per_session:
            # Calcula quantas mensagens remover (sempre pares)
            to_remove = len(messages) - self.max_history_per_session
            to_remove = to_remove + (to_remove % 2)  # Garante número par
            
            # Recria memória com mensagens recentes
            session.memory.clear()
            for i in range(to_remove, len(messages), 2):
                if i + 1 < len(messages):
                    session.memory.save_context(
                        {"input": messages[i].content if hasattr(messages[i], 'content') else str(messages[i])},
                        {"output": messages[i + 1].content if hasattr(messages[i + 1], 'content') else str(messages[i + 1])}
                    )
    
    def _cleanup_old_sessions(self, max_age_hours: int = 24):
        """
        Remove sessões inativas.
        
        Args:
            max_age_hours: Sessões inativas por mais de N horas serão removidas
        """
        now = datetime.now()
        to_delete = []
        
        for session_id, session in self.sessions.items():
            age_hours = (now - session.last_activity).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_delete.append(session_id)
        
        for session_id in to_delete:
            del self.sessions[session_id]
        
        if to_delete:
            print(f"🧹 Limpeza: {len(to_delete)} sessões antigas removidas")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do gerenciador"""
        total_messages = sum(
            len(self.get_history(sid, as_messages=True))
            for sid in self.sessions.keys()
        )
        
        return {
            "active_sessions": len(self.sessions),
            "total_messages": total_messages,
            "max_sessions": self.max_sessions,
            "max_history_per_session": self.max_history_per_session
        }


# Instância global (singleton simples)
_global_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Obtém instância global do ConversationManager"""
    global _global_conversation_manager
    
    if _global_conversation_manager is None:
        _global_conversation_manager = ConversationManager()
    
    return _global_conversation_manager
