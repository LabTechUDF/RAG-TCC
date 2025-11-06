"""
API FastAPI para busca RAG jurídico.
"""
import sys
from pathlib import Path

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.storage.factory import get_store, get_faiss_store
from src.storage.faiss_store import FAISSStore
from src import embeddings, config
from src.schema import SearchResponse, SearchResult


# Modelos Pydantic para API
class SearchRequest(BaseModel):
    # exige string não vazia
    q: str = Field(..., min_length=1, description="Texto da consulta jurídica")
    k: int = Field(5, ge=1, le=20, description="Número de resultados (1-20)")


class SearchResultAPI(BaseModel):
    id: str
    title: Optional[str] = None
    text: str
    court: Optional[str] = None
    code: Optional[str] = None
    article: Optional[str] = None
    date: Optional[str] = None
    
    # Metadados jurídicos adicionais
    case_number: Optional[str] = Field(None, description="Número do processo/caso")
    relator: Optional[str] = Field(None, description="Relator do caso")
    source: Optional[str] = Field(None, description="Fonte do documento (STF, STJ, etc)")
    
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
    description="API de busca vetorial para documentos jurídicos",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
)

# Configuração CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store global (inicializado no startup)
store = None


@app.on_event("startup")
async def startup_event():
    """Inicializa store no startup da aplicação."""
    global store
    print(f"🚀 Iniciando API RAG Jurídico...")
    print(f"🔧 Backend: {config.SEARCH_BACKEND}")
    print(f"🤖 Modelo: {config.EMBEDDING_MODEL}")
    
    try:
        store = get_store()
        doc_count = store.get_doc_count()
        print(f"📊 {doc_count} documentos disponíveis")
        
        if doc_count == 0:
            print("⚠️ Aviso: Nenhum documento indexado!")
            if config.SEARCH_BACKEND == "faiss":
                print("💡 Execute: make faiss-build")
            else:
                print("💡 Execute: make os-build")
        
        print("✅ API pronta!")
        
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
    
    try:
        # Gera embedding da query
        query_vector = embeddings.encode_single_text(request.q)
        
        # Busca documentos usando store global
        results = store.search(query_vector, k=request.k)

        # Converte para modelo API
        api_results = []
        for result in results:
            doc = result.doc
            meta = doc.meta or {}
            api_result = SearchResultAPI(
                id=doc.id,
                title=doc.title,
                text=doc.text,
                court=doc.court,
                code=doc.code,
                article=doc.article,
                date=doc.date,
                case_number=meta.get('case_number'),
                relator=meta.get('relator'),
                source=meta.get('source'),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True
    )