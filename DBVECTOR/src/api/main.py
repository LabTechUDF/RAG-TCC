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

# Store e QueryBuilder globais (inicializados no startup)
store = None
query_builder = None


@app.on_event("startup")
async def startup_event():
    """Inicializa store e componentes no startup da aplicação."""
    global store, query_builder
    print(f"🚀 Iniciando API RAG Jurídico...")
    print(f"🔧 Backend: {config.SEARCH_BACKEND}")
    print(f"🤖 Modelo: {config.EMBEDDING_MODEL}")
    
    try:
        store = get_store()
        query_builder = QueryBuilder()
        
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True
    )