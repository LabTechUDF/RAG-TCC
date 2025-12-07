"""
RAG Chain com LangChain para respostas jurídicas.

Este módulo implementa o fluxo completo de RAG usando LangChain:
1. Retrieval: busca documentos relevantes no FAISS
2. Augmentation: monta contexto com documentos recuperados
3. Generation: gera resposta usando LLM com contexto aumentado
"""
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

from src.schema import Doc, SearchResult
from src.storage.base import VectorStore


# Prompt jurídico otimizado para RAG
RAG_SYSTEM_PROMPT = """Você é um assistente jurídico especializado em legislação e jurisprudência brasileira.

Sua função é responder perguntas sobre direito usando APENAS as informações dos documentos fornecidos abaixo.

REGRAS IMPORTANTES:
1. Use SOMENTE informações presentes nos documentos fornecidos
2. Se a informação não estiver nos documentos, diga claramente que não encontrou informações suficientes
3. Cite os documentos relevantes ao responder (ex: "Conforme STF HC 123.456...")
4. Seja objetivo, claro e use linguagem jurídica apropriada mas acessível
5. Se houver decisões conflitantes, mencione ambas e explique o contexto
6. Priorize jurisprudência mais recente quando relevante
7. Organize respostas com estrutura clara (tópicos quando apropriado)

DOCUMENTOS RELEVANTES:
{context}

PERGUNTA DO USUÁRIO:
{question}

RESPOSTA:"""


@dataclass
class RAGResponse:
    """Resposta do sistema RAG com metadados"""
    answer: str
    sources: List[Dict[str, Any]]
    retrieval_latency_ms: float
    llm_latency_ms: float
    total_latency_ms: float
    documents_retrieved: int
    model_used: str


class LangChainRAG:
    """
    Sistema RAG completo usando LangChain.
    
    Integra:
    - Retrieval: FAISSStore ou outro VectorStore
    - LLM: OpenAI (ou compatível)
    - Memória conversacional: via conversation_history
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 1000,
        api_key: Optional[str] = None
    ):
        """
        Inicializa RAG chain.
        
        Args:
            vector_store: Store de vetores para retrieval
            model_name: Modelo OpenAI a usar
            temperature: Temperatura para geração (0.0-1.0)
            max_tokens: Máximo de tokens na resposta
            api_key: API key OpenAI (usa OPENAI_API_KEY se None)
        """
        self.vector_store = vector_store
        self.model_name = model_name
        self.max_tokens = max_tokens
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            raise ValueError(
                "OPENAI_API_KEY não configurada. "
                "Configure a variável de ambiente ou passe api_key no construtor."
            )
        
        # Inicializa LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self.api_key
        )
        
        # Cria prompt template
        self.prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=RAG_SYSTEM_PROMPT
        )
        
        self.stats = {
            'queries_processed': 0,
            'total_documents_retrieved': 0,
            'llm_calls': 0,
            'errors': 0
        }
    
    def run_rag(
        self,
        query: str,
        k: int = 5,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> RAGResponse:
        """
        Executa fluxo completo de RAG.
        
        Args:
            query: Pergunta do usuário
            k: Número de documentos a recuperar
            conversation_history: Histórico da conversa
            session_id: ID da sessão
            filters: Filtros para retrieval (court, article, etc.)
            
        Returns:
            RAGResponse com resposta e metadados
        """
        total_start = time.time()
        self.stats['queries_processed'] += 1
        
        try:
            # 1. RETRIEVAL - busca documentos relevantes
            retrieval_start = time.time()
            search_results = self._retrieve_documents(query, k, filters)
            retrieval_latency = (time.time() - retrieval_start) * 1000
            
            self.stats['total_documents_retrieved'] += len(search_results)
            
            if not search_results:
                # Sem documentos relevantes
                return RAGResponse(
                    answer="Não foram encontrados documentos relevantes para responder sua pergunta. Por favor, reformule ou forneça mais detalhes.",
                    sources=[],
                    retrieval_latency_ms=retrieval_latency,
                    llm_latency_ms=0,
                    total_latency_ms=(time.time() - total_start) * 1000,
                    documents_retrieved=0,
                    model_used=self.model_name
                )
            
            # 2. AUGMENTATION - monta contexto
            context = self._format_context(search_results, conversation_history)
            
            # 3. GENERATION - gera resposta com LLM usando LCEL
            llm_start = time.time()
            self.stats['llm_calls'] += 1
            
            chain = self.prompt | self.llm
            result = chain.invoke({
                "context": context,
                "question": query
            })
            
            answer = result.content if hasattr(result, 'content') else str(result)
            answer = answer.strip()
            llm_latency = (time.time() - llm_start) * 1000
            
            # 4. Prepara sources para resposta
            sources = self._format_sources(search_results)
            
            total_latency = (time.time() - total_start) * 1000
            
            return RAGResponse(
                answer=answer,
                sources=sources,
                retrieval_latency_ms=retrieval_latency,
                llm_latency_ms=llm_latency,
                total_latency_ms=total_latency,
                documents_retrieved=len(search_results),
                model_used=self.model_name
            )
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"❌ Erro no RAG: {e}")
            raise
    
    def _retrieve_documents(
        self,
        query: str,
        k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        Recupera documentos do vector store.
        
        Aplica filtros se disponíveis (court, article, date_range).
        """
        # TODO: Implementar filtragem avançada no FAISSStore
        # Por enquanto, usa busca simples por similaridade
        results = self.vector_store.search(query, k=k)
        
        # Filtragem pós-retrieval (não ideal, mas funciona)
        if filters:
            filtered_results = []
            for result in results:
                doc = result.doc
                
                # Filtro por tribunal
                if "court" in filters:
                    if doc.court != filters["court"]:
                        continue
                
                # Filtro por artigo
                if "article" in filters:
                    if doc.article != filters["article"]:
                        continue
                
                filtered_results.append(result)
            
            return filtered_results[:k]
        
        return results
    
    def _format_context(
        self,
        search_results: List[SearchResult],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> str:
        """
        Formata documentos recuperados em contexto para o LLM.
        
        Inclui metadados relevantes (tribunal, artigo, data) de forma estruturada.
        """
        context_parts = []
        
        # Adiciona histórico recente se disponível
        if conversation_history:
            last_exchanges = conversation_history[-2:]  # Últimas 2 interações
            if last_exchanges:
                context_parts.append("=== CONTEXTO DA CONVERSA ===")
                for exchange in last_exchanges:
                    if "user" in exchange:
                        context_parts.append(f"Usuário perguntou: {exchange['user']}")
                    if "assistant" in exchange:
                        context_parts.append(f"Assistente respondeu: {exchange['assistant'][:150]}...")
                context_parts.append("")
        
        # Adiciona documentos recuperados
        context_parts.append("=== DOCUMENTOS JURÍDICOS RELEVANTES ===\n")
        
        for i, result in enumerate(search_results, 1):
            doc = result.doc
            
            # Monta metadados
            metadata_parts = []
            if doc.court:
                metadata_parts.append(f"Tribunal: {doc.court}")
            if doc.code:
                metadata_parts.append(f"Código: {doc.code}")
            if doc.article:
                metadata_parts.append(f"Artigo: {doc.article}")
            if doc.date:
                metadata_parts.append(f"Data: {doc.date}")
            if doc.title:
                metadata_parts.append(f"Título: {doc.title}")
            
            metadata_str = " | ".join(metadata_parts)
            score_str = f"Relevância: {result.score:.3f}"
            
            context_parts.append(f"--- DOCUMENTO {i} ---")
            context_parts.append(f"[{metadata_str}]")
            context_parts.append(f"[{score_str}]")
            context_parts.append(f"\n{doc.text}\n")
        
        return "\n".join(context_parts)
    
    def _format_sources(self, search_results: List[SearchResult]) -> List[Dict[str, Any]]:
        """Formata sources para resposta da API"""
        sources = []
        
        for result in search_results:
            doc = result.doc
            source = {
                "id": doc.id,
                "title": doc.title or "Sem título",
                "court": doc.court,
                "code": doc.code,
                "article": doc.article,
                "date": doc.date,
                "score": result.score,
                "text": doc.text[:300] + "..." if len(doc.text) > 300 else doc.text
            }
            sources.append(source)
        
        return sources
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de uso"""
        return self.stats.copy()
