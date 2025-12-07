"""
API FastAPI para busca RAG jurídico.
Integrado com Query Builder e Telemetria conforme TCC.
"""
import sys
from pathlib import Path

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.storage.factory import get_store, get_faiss_store
from src.storage.faiss_store import FAISSStore
from src import embeddings, config
from src.schema import SearchResponse, SearchResult
from src.tools.query_builder import QueryBuilder, QueryContext, CanonicalQuery
from src.tools.telemetry import PerformanceTimer, log_query_execution, QueryMode, get_telemetry_logger

# LangChain RAG imports
try:
    from src.tools.query_optimizer import QueryOptimizer
    from src.api.langchain_rag import LangChainRAG, RAGResponse
    from src.api.conversation_manager import get_conversation_manager
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ LangChain não disponível: {e}")
    LANGCHAIN_AVAILABLE = False


# Modelos Pydantic para API
class SearchRequest(BaseModel):
    """Request para busca RAG com suporte a filtros e contexto"""
    q: str = Field(..., min_length=1, description="Texto da consulta jurídica")
    k: int = Field(5, ge=1, le=20, description="Número de resultados (top-k)")
    
    # Filtros opcionais
    court_filter: Optional[str] = Field(None, description="Filtro por tribunal (STF, STJ, etc)")
    article_filter: Optional[str] = Field(None, description="Filtro por artigo específico")
    date_range: Optional[tuple] = Field(None, description="Filtro por intervalo de datas")
    cluster_hints: Optional[List[str]] = Field(default_factory=list, description="Hints de clusters para otimização")
    
    # Contexto da conversa
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Histórico da conversa")
    user_id: Optional[str] = Field(None, description="ID do usuário para telemetria")
    session_id: Optional[str] = Field(None, description="ID da sessão para telemetria")


class SearchResultAPI(BaseModel):
    id: str
    title: Optional[str] = None
    text: str
    court: Optional[str] = None
    code: Optional[str] = None
    article: Optional[str] = None
    date: Optional[str] = None
    meta: Optional[dict] = None
    score: float


class SearchResponseAPI(BaseModel):
    """Response com resultados e metadados de telemetria"""
    query: str
    canonical_query: Optional[str] = None
    total: int
    backend: str
    results: list[SearchResultAPI]
    
    # Metadados de telemetria
    latency_ms: float
    retrieval_latency_ms: float
    filters_applied: Dict[str, Any]
    avg_score: Optional[float] = None
    
    # Esclarecimentos (se necessário)
    requires_clarification: bool = False
    clarification_questions: Optional[List[str]] = None


# App FastAPI
app = FastAPI(
    title="RAG Jurídico API",
    description="API de busca vetorial para documentos jurídicos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
)

# Componentes globais (inicializados no startup)
store = None
query_builder = None
query_optimizer = None
langchain_rag = None
conversation_manager = None


@app.on_event("startup")
async def startup_event():
    """Inicializa store e componentes no startup da aplicação."""
    global store, query_builder, query_optimizer, langchain_rag, conversation_manager
    print(f"🚀 Iniciando API RAG Jurídico...")
    print(f"🔧 Backend: {config.SEARCH_BACKEND}")
    print(f"🤖 Modelo: {config.EMBEDDING_MODEL}")
    
    try:
        store = get_store()
        query_builder = QueryBuilder()
        
        # Inicializa componentes LangChain se disponível
        if LANGCHAIN_AVAILABLE:
            try:
                query_optimizer = QueryOptimizer()
                langchain_rag = LangChainRAG(vector_store=store)
                conversation_manager = get_conversation_manager()
                print("✅ LangChain RAG ativado")
            except Exception as e:
                print(f"⚠️ LangChain RAG desativado: {e}")
                query_optimizer = None
                langchain_rag = None
                conversation_manager = None
        else:
            print("⚠️ LangChain não disponível - usando modo básico")
        
        doc_count = store.get_doc_count()
        print(f"📊 {doc_count} documentos disponíveis")
        
        if doc_count == 0:
            print("⚠️ Aviso: Nenhum documento indexado!")
            if config.SEARCH_BACKEND == "faiss":
                print("💡 Execute: make faiss-build")
            else:
                print("💡 Execute: make os-build")
        
        print("✅ API pronta!")
        print("📝 Telemetria ativada")
        
    except Exception as e:
        print(f"❌ Erro ao inicializar store: {e}")
        raise


@app.get("/")
async def root():
    """Endpoint raiz com informações da API."""
    doc_count = store.get_doc_count() if store else 0
    return {
        "message": "RAG Jurídico API",
        "backend": config.SEARCH_BACKEND,
        "embedding_model": config.EMBEDDING_MODEL,
        "documents_indexed": doc_count,
        "endpoints": {
            "search": "/search",
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    doc_count = store.get_doc_count()
    return {
        "status": "healthy",
        "backend": config.SEARCH_BACKEND,
        "documents": doc_count,
        "embedding_dim": config.EMBEDDING_DIM
    }


@app.get("/metrics")
async def get_metrics():
    """
    Endpoint de métricas para monitoramento.
    Retorna estatísticas de uso e performance do sistema RAG.
    """
    telemetry_logger = get_telemetry_logger()
    query_builder_stats = query_builder.get_stats() if query_builder else {}
    
    return {
        "telemetry": telemetry_logger.get_metrics_summary(),
        "query_builder": query_builder_stats,
        "system": {
            "backend": config.SEARCH_BACKEND,
            "documents_indexed": store.get_doc_count() if store else 0,
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dim": config.EMBEDDING_DIM
        }
    }


@app.post("/search", response_model=SearchResponseAPI)
async def search_documents(request: SearchRequest):
    """
    Busca documentos jurídicos por similaridade semântica com RAG otimizado.
    
    Fluxo completo conforme TCC (Figura 4.5):
    1. Recebe query do usuário
    2. Constrói query canônica com QueryBuilder
    3. Verifica necessidade de esclarecimento
    4. Busca documentos no banco vetorial
    5. Registra telemetria
    6. Retorna resultados + metadados
    
    - **q**: Consulta em linguagem natural
    - **k**: Número de resultados a retornar (top-k: 1-20)
    - **court_filter**: Filtro opcional por tribunal
    - **article_filter**: Filtro opcional por artigo
    - **cluster_hints**: Lista de clusters para otimização
    """
    if store is None or query_builder is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    # Timer para telemetria total
    with PerformanceTimer("total") as total_timer:
        # Verifica se query é vazia
        if not request.q or not request.q.strip():
            raise HTTPException(status_code=422, detail="Query não pode ser vazia")

        # Verifica se há documentos
        doc_count = store.get_doc_count()
        if doc_count == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"Nenhum documento indexado. Execute pipeline de build para {config.SEARCH_BACKEND}"
            )
        
        try:
            # 1. Constrói query canônica com QueryBuilder
            query_context = QueryContext(
                user_query=request.q,
                cluster_hints=request.cluster_hints or [],
                court_filter=request.court_filter,
                article_filter=request.article_filter,
                date_range=request.date_range,
                conversation_history=request.conversation_history or []
            )
            
            canonical = query_builder.build_canonical_query(query_context)
            
            # 2. Se requer esclarecimento, retorna early
            if canonical.requires_clarification:
                return SearchResponseAPI(
                    query=request.q,
                    canonical_query=canonical.optimized_text,
                    total=0,
                    backend=config.SEARCH_BACKEND,
                    results=[],
                    latency_ms=total_timer.get_elapsed_ms(),
                    retrieval_latency_ms=0.0,
                    filters_applied=canonical.filters,
                    requires_clarification=True,
                    clarification_questions=canonical.clarification_questions
                )
            
            # 3. Gera embedding da query otimizada
            with PerformanceTimer("retrieval") as retrieval_timer:
                query_vector = embeddings.encode_single_text(canonical.optimized_text)
                
                # 4. Busca documentos usando store global
                # TODO: Aplicar filtros (court, article, date) quando implementado no store
                results = store.search(query_vector, k=request.k)

            # 5. Converte para modelo API
            api_results = []
            scores = []
            for result in results:
                doc = result.doc
                scores.append(result.score)
                api_result = SearchResultAPI(
                    id=doc.id,
                    title=doc.title,
                    text=doc.text,
                    court=doc.court,
                    code=doc.code,
                    article=doc.article,
                    date=doc.date,
                    meta=doc.meta,
                    score=result.score
                )
                api_results.append(api_result)
            
            # Calcula score médio
            avg_score = sum(scores) / len(scores) if scores else None
            
            # 6. Registra telemetria
            log_query_execution(
                query=request.q,
                mode=QueryMode.RAG,
                total_latency=total_timer.get_elapsed_ms(),
                result_count=len(api_results),
                user_id=request.user_id,
                session_id=request.session_id,
                retrieval_latency=retrieval_timer.get_elapsed_ms(),
                backend=config.SEARCH_BACKEND,
                model=config.EMBEDDING_MODEL,
                filters=canonical.filters,
                top_k=request.k,
                avg_score=avg_score
            )
            
            return SearchResponseAPI(
                query=request.q,
                canonical_query=canonical.optimized_text,
                total=len(api_results),
                backend=config.SEARCH_BACKEND,
                results=api_results,
                latency_ms=total_timer.get_elapsed_ms(),
                retrieval_latency_ms=retrieval_timer.get_elapsed_ms(),
                filters_applied=canonical.filters,
                avg_score=avg_score
            )
            
        except Exception as e:
            print(f"❌ Erro na busca: {e}")
            
            # Log de erro na telemetria
            log_query_execution(
                query=request.q,
                mode=QueryMode.RAG,
                total_latency=total_timer.get_elapsed_ms(),
                result_count=0,
                user_id=request.user_id,
                session_id=request.session_id,
                backend=config.SEARCH_BACKEND,
                model=config.EMBEDDING_MODEL,
                error=str(e)
            )
            
            raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.post("/rag/chat")
async def rag_chat(request: SearchRequest):
    """
    Endpoint RAG completo com LangChain.
    
    Retorna resposta gerada por LLM usando documentos recuperados como contexto.
    Este endpoint integra:
    - Query optimization com LLM
    - Retrieval de documentos
    - Generation de resposta com contexto aumentado
    - Memória conversacional
    """
    if not LANGCHAIN_AVAILABLE or langchain_rag is None:
        raise HTTPException(
            status_code=501,
            detail="LangChain RAG não disponível. Configure OPENAI_API_KEY."
        )
    
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    # Timer para telemetria
    with PerformanceTimer("total") as total_timer:
        try:
            # 1. Otimiza query com LLM (se query_optimizer disponível)
            canonical_text = request.q
            filters_applied = {}
            
            if query_optimizer:
                query_context = QueryContext(
                    user_query=request.q,
                    cluster_hints=request.cluster_hints or [],
                    court_filter=request.court_filter,
                    article_filter=request.article_filter,
                    date_range=request.date_range,
                    conversation_history=request.conversation_history or []
                )
                
                canonical = query_optimizer.optimize_query(query_context)
                canonical_text = canonical.optimized_text
                filters_applied = canonical.filters
                
                # Se requer esclarecimento
                if canonical.requires_clarification:
                    return {
                        "answer": None,
                        "requires_clarification": True,
                        "clarification_questions": canonical.clarification_questions,
                        "query": request.q,
                        "canonical_query": canonical_text
                    }
            
            # 2. Executa RAG completo
            rag_response: RAGResponse = langchain_rag.run_rag(
                query=canonical_text,
                k=request.k,
                conversation_history=request.conversation_history or [],
                session_id=request.session_id,
                filters=filters_applied
            )
            
            # 3. Salva na memória conversacional se session_id fornecido
            if request.session_id and conversation_manager:
                conversation_manager.add_exchange(
                    session_id=request.session_id,
                    user_message=request.q,
                    assistant_message=rag_response.answer,
                    user_id=request.user_id
                )
            
            # 4. Log telemetria
            log_query_execution(
                query=request.q,
                mode=QueryMode.RAG,
                total_latency=rag_response.total_latency_ms,
                result_count=rag_response.documents_retrieved,
                user_id=request.user_id,
                session_id=request.session_id,
                retrieval_latency=rag_response.retrieval_latency_ms,
                backend=config.SEARCH_BACKEND,
                model=rag_response.model_used,
                filters=filters_applied,
                top_k=request.k
            )
            
            return {
                "answer": rag_response.answer,
                "sources": rag_response.sources,
                "query": request.q,
                "canonical_query": canonical_text,
                "requires_clarification": False,
                "telemetry": {
                    "total_latency_ms": rag_response.total_latency_ms,
                    "retrieval_latency_ms": rag_response.retrieval_latency_ms,
                    "llm_latency_ms": rag_response.llm_latency_ms,
                    "documents_retrieved": rag_response.documents_retrieved,
                    "model_used": rag_response.model_used
                },
                "backend": config.SEARCH_BACKEND,
                "filters_applied": filters_applied
            }
            
        except Exception as e:
            print(f"❌ Erro no RAG chat: {e}")
            raise HTTPException(status_code=500, detail=f"Erro no RAG: {str(e)}")


@app.get("/rag/sessions")
async def list_sessions(user_id: Optional[str] = None):
    """Lista sessões de conversa ativas"""
    if not conversation_manager:
        raise HTTPException(status_code=501, detail="ConversationManager não disponível")
    
    sessions = conversation_manager.list_sessions(user_id=user_id)
    return {"sessions": sessions, "total": len(sessions)}


@app.get("/rag/sessions/{session_id}")
async def get_session(session_id: str):
    """Obtém informações e histórico de uma sessão"""
    if not conversation_manager:
        raise HTTPException(status_code=501, detail="ConversationManager não disponível")
    
    info = conversation_manager.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    
    history = conversation_manager.get_history(session_id, as_messages=True)
    
    return {
        **info,
        "history": history
    }


@app.delete("/rag/sessions/{session_id}")
async def delete_session(session_id: str):
    """Remove uma sessão de conversa"""
    if not conversation_manager:
        raise HTTPException(status_code=501, detail="ConversationManager não disponível")
    
    conversation_manager.delete_session(session_id)
    return {"message": f"Sessão {session_id} removida"}


@app.get("/rag/stats")
async def rag_stats():
    """Estatísticas dos componentes RAG"""
    stats = {
        "langchain_available": LANGCHAIN_AVAILABLE,
        "backend": config.SEARCH_BACKEND,
        "embedding_model": config.EMBEDDING_MODEL
    }
    
    if query_optimizer:
        stats["query_optimizer"] = query_optimizer.get_stats()
    
    if langchain_rag:
        stats["langchain_rag"] = langchain_rag.get_stats()
    
    if conversation_manager:
        stats["conversation_manager"] = conversation_manager.get_stats()
    
    return stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True
    )