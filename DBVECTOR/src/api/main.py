"""
API FastAPI para busca RAG jurídico.
"""
import sys
from pathlib import Path

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import hmac
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.storage.factory import get_store, get_faiss_store
from src.storage.faiss_store import FAISSStore
from src import embeddings, config
from src.schema import SearchResponse, SearchResult

# Imports para RAG SEEU
from src.rag_schemas import RagQueryRequest, RagQueryResponse
from src.rag_service import RagService


# Modelos Pydantic para API
class SearchRequest(BaseModel):
    # exige string não vazia
    q: str = Field(..., min_length=1, description="Texto da consulta jurídica")
    k: int = Field(5, ge=1, le=100, description="Número de resultados (1-100)")
    id_prefix: Optional[str] = Field(None, description="Restringe a ids com esse prefixo, ex.: lei:lgpd, tjdft:")
    court: Optional[str] = Field(None, description="Restringe a um tribunal, ex.: TJDFT, STJ")


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
    query: str
    total: int
    backend: str
    results: list[SearchResultAPI]


# App FastAPI
app = FastAPI(
    title="RAG Jurídico API",
    description="API de busca vetorial para documentos jurídicos com RAG para execução penal",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Autenticação opcional por token: ativa quando API_AUTH_TOKEN está definido.
# Aceita "Authorization: Bearer <token>" ou "X-API-Key: <token>".
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json"}


@app.middleware("http")
async def require_token(request: Request, call_next):
    if API_AUTH_TOKEN and request.method != "OPTIONS" and request.url.path not in PUBLIC_PATHS:
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
        if not hmac.compare_digest(token.encode(), API_AUTH_TOKEN.encode()):
            return JSONResponse(status_code=401, content={"detail": "Token inválido ou ausente"})
    return await call_next(request)

# Store e RagService globais (inicializados no startup)
store = None
rag_service = None


@app.on_event("startup")
async def startup_event():
    """Inicializa store e RAG service no startup da aplicação."""
    global store, rag_service
    print(f"🚀 Iniciando API RAG Jurídico...")
    print(f"🔧 Backend: {config.SEARCH_BACKEND}")
    print(f"🤖 Modelo Embedding: {config.EMBEDDING_MODEL}")
    
    try:
        # Inicializa store vetorial
        store = get_store()
        doc_count = store.get_doc_count()
        print(f"📊 {doc_count} documentos/chunks disponíveis")
        
        if doc_count == 0:
            print("⚠️ Aviso: Nenhum documento indexado!")
            if config.SEARCH_BACKEND == "faiss":
                print("💡 Execute: make faiss-build")
            else:
                print("💡 Execute: make os-build")
        
        # Inicializa RAG service (se chaves LLM disponíveis)
        import os
        if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            provider = os.getenv("LLM_PROVIDER", "openai")
            print(f"🧠 Inicializando RAG Service com provider: {provider}")
            rag_service = RagService(store=store, provider=provider)
            print("✅ RAG Service pronto!")
        else:
            print("⚠️ Chaves LLM não configuradas - endpoint /api/rag/query não estará disponível")
            print("💡 Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY no .env")
        
        print("✅ API pronta!")
        
    except Exception as e:
        print(f"❌ Erro ao inicializar: {e}")
        raise


@app.get("/")
async def root():
    """Endpoint raiz com informações da API."""
    doc_count = store.get_doc_count() if store else 0
    rag_available = rag_service is not None
    
    return {
        "message": "RAG Jurídico API - Sistema SEEU",
        "version": "2.0.0",
        "backend": config.SEARCH_BACKEND,
        "embedding_model": config.EMBEDDING_MODEL,
        "documents_indexed": doc_count,
        "rag_service_available": rag_available,
        "endpoints": {
            "search": "/search (busca vetorial simples)",
            "rag_query": "/api/rag/query (RAG completo para execução penal)",
            "health": "/health",
            "docs": "/docs"
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


@app.post("/search", response_model=SearchResponseAPI)
async def search_documents(request: SearchRequest):
    """
    Busca documentos jurídicos por similaridade semântica.
    
    - **q**: Consulta em linguagem natural
    - **k**: Número de resultados a retornar (1-20)
    """
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    # Verifica se query é vazia (após strip) — garante validação adicional
    if not request.q or not request.q.strip():
        raise HTTPException(status_code=422, detail="Query não pode ser vazia")

    # Verifica se há documentos
    doc_count = store.get_doc_count()
    if doc_count == 0:
        raise HTTPException(
            status_code=404, 
            detail=f"Nenhum documento indexado. Execute pipeline de build para {config.SEARCH_BACKEND}"
        )
    
    filtered = bool(request.id_prefix or request.court)
    if filtered and not isinstance(store, FAISSStore):
        raise HTTPException(status_code=501, detail=f"Filtros id_prefix/court não suportados no backend {config.SEARCH_BACKEND}")

    try:
        # Gera embedding da query
        query_vector = embeddings.encode_single_text(request.q)

        # Busca documentos usando store global
        if filtered:
            results = store.search(query_vector, k=request.k, id_prefix=request.id_prefix, court=request.court)
        else:
            results = store.search(query_vector, k=request.k)

        # Converte para modelo API
        api_results = []
        for result in results:
            doc = result.doc
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
        
        return SearchResponseAPI(
            query=request.q,
            total=len(api_results),
            backend=config.SEARCH_BACKEND,
            results=api_results
        )
        
    except Exception as e:
        print(f"❌ Erro na busca: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.post("/api/rag/query", response_model=RagQueryResponse)
async def rag_query(request: RagQueryRequest):
    """
    Endpoint principal para consultas RAG jurídicas com foco em execução penal.
    
    Fluxo completo:
    1. Normalização jurídica da query
    2. Busca vetorial de chunks relevantes
    3. Cálculo de relevância relativa
    4. Geração de resposta estruturada via LLM
    
    - **promptUsuario**: Pergunta do usuário em linguagem natural
    - **useRag**: Se deve usar RAG (default: true)
    - **metadados**: Filtros opcionais (tribunal, ano, tipo)
    - **k**: Número de chunks a recuperar (1-50, default: 10)
    """
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG Service não disponível. Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY"
        )
    
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    # Verifica se query é vazia
    if not request.promptUsuario or not request.promptUsuario.strip():
        raise HTTPException(status_code=422, detail="promptUsuario não pode ser vazio")
    
    # Verifica se há documentos
    doc_count = store.get_doc_count()
    if doc_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum documento indexado. Execute pipeline de build para {config.SEARCH_BACKEND}"
        )
    
    try:
        # Processa consulta RAG
        resposta = rag_service.processar_consulta(request)
        return resposta
        
    except ValueError as e:
        # Erros de validação ou parsing
        print(f"❌ Erro de validação: {e}")
        raise HTTPException(status_code=422, detail=str(e))
        
    except Exception as e:
        # Erros internos
        print(f"❌ Erro ao processar RAG query: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.post("/api/rag/query-markdown")
async def rag_query_markdown(request: RagQueryRequest):
    """
    Endpoint RAG otimizado para UX jurídica - retorna Markdown puro.
    
    Diferente do /api/rag/query que retorna JSON estruturado, este endpoint
    retorna diretamente uma resposta em Markdown formatado para exibição
    imediata na interface do usuário.
    
    Ideal para operadores do direito que precisam de:
    - Leitura rápida e clara
    - Destaque visual de informações essenciais
    - Links clicáveis para jurisprudências
    - Estrutura organizada com seções específicas
    
    Fluxo:
    1. Normalização jurídica da query
    2. Busca vetorial de chunks relevantes
    3. Cálculo de relevância relativa
    4. Geração de resposta em Markdown via LLM (template UX jurídica)
    
    - **promptUsuario**: Pergunta do usuário em linguagem natural
    - **useRag**: Se deve usar RAG (default: true)
    - **metadados**: Filtros opcionais (tribunal, ano, tipo)
    - **k**: Número de chunks a recuperar (1-50, default: 10)
    
    Returns:
        String em Markdown pronta para renderização
    """
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG Service não disponível. Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY"
        )
    
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    # Verifica se query é vazia
    if not request.promptUsuario or not request.promptUsuario.strip():
        raise HTTPException(status_code=422, detail="promptUsuario não pode ser vazio")
    
    # Verifica se há documentos
    doc_count = store.get_doc_count()
    if doc_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum documento indexado. Execute pipeline de build para {config.SEARCH_BACKEND}"
        )
    
    try:
        # Processa consulta RAG com retorno em Markdown
        resposta_markdown = rag_service.query_markdown(request)
        
        # Retorna como texto plano (não JSON)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=resposta_markdown, media_type="text/markdown")
        
    except ValueError as e:
        # Erros de validação ou parsing
        print(f"❌ Erro de validação: {e}")
        raise HTTPException(status_code=422, detail=str(e))
        
    except Exception as e:
        # Erros internos
        print(f"❌ Erro ao processar RAG query (Markdown): {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.get("/doc/{doc_id:path}")
def get_document(doc_id: str):
    """Documento indexado completo (texto e metadados) pelo id, ex.: lei:cf-88:art-5, tjdft:<uuid>."""
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    if not hasattr(store, "get_by_id"):
        raise HTTPException(status_code=501, detail=f"Backend {config.SEARCH_BACKEND} não suporta busca por id")
    record = store.get_by_id(doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Documento não encontrado: {doc_id}")
    record.pop("internal_id", None)
    return record


# ---------------------------------------------------------------- STJ (dados abertos, busca local)
# Índice SQLite FTS5 montado por `stj_scraper/manage.py open-data build` (íntegras 2021+, espelhos 2022+).
REPO_ROOT = Path(__file__).resolve().parents[3]
STJ_OPEN_DATA_DB = Path(os.getenv("STJ_OPEN_DATA_DB", str(REPO_ROOT / "stj_scraper" / "data" / "open_data" / "stj_open_data.sqlite")))


class StjSearchRequest(BaseModel):
    q: str = Field(..., min_length=1, description='Termos (FTS5: "frase", OR, NOT, NEAR, prefixo*); acentos ignorados')
    scope: str = Field("all", pattern="^(all|espelhos|integras)$", description="espelhos (ementas 2022+), integras (textos 2021+) ou all")
    limit: int = Field(10, ge=1, le=50)
    tipo: Optional[str] = Field(None, description="ACÓRDÃO ou DECISÃO")
    desde: Optional[str] = Field(None, description="YYYY-MM-DD")
    ate: Optional[str] = Field(None, description="YYYY-MM-DD")
    ministro: Optional[str] = Field(None, description="Relator/ministro (parte do nome)")
    orgao: Optional[str] = Field(None, description="Órgão julgador (espelhos)")
    classe: Optional[str] = Field(None, description="Classe, ex.: REsp, AREsp")


def _stj_search_module():
    if not STJ_OPEN_DATA_DB.exists():
        raise HTTPException(status_code=503, detail=f"Índice do STJ não encontrado ({STJ_OPEN_DATA_DB}); rode open-data sync/build")
    stj_root = str(REPO_ROOT / "stj_scraper")
    if stj_root not in sys.path:
        sys.path.insert(0, stj_root)
    from stj_scraper.open_data import search as stj_search
    return stj_search


@app.post("/stj/search")
def stj_search_endpoint(request: StjSearchRequest):
    """Busca qualquer termo nos dados abertos do STJ (espelhos de acórdãos e íntegras)."""
    stj_search = _stj_search_module()
    try:
        return stj_search.search(STJ_OPEN_DATA_DB, request.q, scope=request.scope, limit=request.limit,
                                 tipo=request.tipo, desde=request.desde, ate=request.ate, ministro=request.ministro,
                                 orgao=request.orgao, classe=request.classe)
    except Exception as e:  # sintaxe FTS5 inválida, por exemplo
        raise HTTPException(status_code=422, detail=f"Consulta inválida: {e}")


@app.get("/stj/text/{seq}")
def stj_text_endpoint(seq: int):
    """Texto integral de uma íntegra do STJ pelo SeqDocumento."""
    doc = _stj_search_module().get_text(STJ_OPEN_DATA_DB, seq)
    if not doc:
        raise HTTPException(status_code=404, detail="SeqDocumento não encontrado")
    return doc


@app.get("/stj/espelho/{espelho_id}")
def stj_espelho_endpoint(espelho_id: int):
    """Espelho completo (ementa, decisão, legislação, precedentes citados...) pelo id de stj:espelho:<id>."""
    docs = _stj_search_module().get_espelhos(STJ_OPEN_DATA_DB, espelho_id=espelho_id)
    if not docs:
        raise HTTPException(status_code=404, detail="Espelho não encontrado")
    return docs[0]


@app.get("/stj/espelho")
def stj_espelho_by_processo_endpoint(processo: str):
    """Espelhos completos por processo, ex.: ?processo=REsp 1921653 (pode haver mais de um: embargos, agravos)."""
    docs = _stj_search_module().get_espelhos(STJ_OPEN_DATA_DB, processo=processo)
    if not docs:
        raise HTTPException(status_code=404, detail="Nenhum espelho para esse processo (espelhos cobrem acórdãos publicados de 2022 em diante)")
    return {"processo": processo, "total": len(docs), "espelhos": docs}


@app.get("/stj/status")
def stj_status_endpoint():
    """Contagens e períodos do índice local do STJ."""
    return _stj_search_module().status(STJ_OPEN_DATA_DB)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True
    )