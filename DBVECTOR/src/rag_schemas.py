"""
Schemas para o sistema RAG jurídico SEEU.
Define estruturas de dados para normalização de queries, chunks e respostas.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ========================================
# SCHEMAS PARA NORMALIZAÇÃO JURÍDICA
# ========================================

class DadosExecucaoPenal(BaseModel):
    """Dados extraídos sobre execução penal do prompt do usuário."""
    regimeAtual: Optional[str] = Field(None, description="Regime prisional atual (fechado, semiaberto, aberto)")
    tempoCumpridoAproximado: Optional[str] = Field(None, description="Tempo de pena cumprido")
    faltasGraves: Optional[str] = Field(None, description="Informações sobre faltas graves")
    tipoCrime: Optional[str] = Field(None, description="Tipo de crime ou delito")
    outrosDadosRelevantes: Optional[str] = Field(None, description="Outros dados relevantes da execução")


class QueryNormalizadaOutput(BaseModel):
    """Saída estruturada do normalizador jurídico."""
    intencao: str = Field(..., description="Intenção principal da consulta")
    tipoBeneficioOuTema: str = Field(..., description="Benefício ou tema jurídico identificado")
    dadosExecucaoPenal: DadosExecucaoPenal = Field(default_factory=DadosExecucaoPenal)
    temaExecucao: List[str] = Field(default_factory=list, description="Temas de execução penal relacionados")
    palavrasChaveJuridicas: List[str] = Field(default_factory=list, description="Termos jurídicos chave")
    queryRAG: str = Field(..., description="Query reescrita para busca vetorial")
    observacoes: Optional[str] = Field(None, description="Observações sobre ambiguidades ou limitações")


# ========================================
# SCHEMAS PARA REQUEST/RESPONSE DA API
# ========================================

class MetadadosConsulta(BaseModel):
    """Metadados opcionais para filtrar a busca."""
    tribunal: Optional[str] = Field(None, description="Tribunal específico (STJ, STF, TJSP, etc.)")
    anoMin: Optional[int] = Field(None, description="Ano mínimo das decisões")
    anoMax: Optional[int] = Field(None, description="Ano máximo das decisões")
    tipoConsulta: Optional[str] = Field(
        "jurisprudencia",
        description="Tipo de consulta: jurisprudencia, legislacao, doutrina, misto"
    )


class RagQueryRequest(BaseModel):
    """Request para o endpoint /api/rag/query."""
    promptUsuario: str = Field(..., min_length=1, description="Pergunta do usuário")
    useRag: bool = Field(True, description="Se deve usar RAG ou resposta direta")
    metadados: Optional[MetadadosConsulta] = Field(default_factory=MetadadosConsulta)
    k: int = Field(10, ge=1, le=50, description="Número de chunks a recuperar")


# ========================================
# SCHEMAS PARA CHUNKS E DOCUMENTOS
# ========================================

class ChunkMetadata(BaseModel):
    """Metadados de um chunk de documento."""
    idDocumentoGlobal: str = Field(..., description="ID único do documento original")
    idChunk: str = Field(..., description="ID único do chunk")
    tribunal: Optional[str] = None
    numeroProcesso: Optional[str] = None
    orgaoJulgador: Optional[str] = None
    relator: Optional[str] = None
    dataJulgamento: Optional[str] = None
    tema: Optional[str] = None
    fonte: Optional[str] = None
    posicaoChunk: Optional[int] = Field(None, description="Posição do chunk no documento")
    totalChunks: Optional[int] = Field(None, description="Total de chunks do documento")


class ChunkWithScore(BaseModel):
    """Chunk recuperado com score de similaridade."""
    texto: str
    metadata: ChunkMetadata
    score: float = Field(..., description="Score bruto de similaridade")
    relevanciaRelativa: Optional[float] = Field(None, description="Relevância relativa normalizada (%)")


# ========================================
# SCHEMAS PARA RESPOSTA SEEU
# ========================================

class TeseJuridica(BaseModel):
    """Uma tese jurídica identificada pelo LLM."""
    titulo: str = Field(..., description="Título conciso da tese")
    descricao: str = Field(..., description="Explicação detalhada da tese")
    documentosSuporte: List[int] = Field(
        default_factory=list,
        description="IDs dos documentos que suportam esta tese"
    )


class JurisprudenciaReferencia(BaseModel):
    """Jurisprudência citada na resposta."""
    docId: int = Field(..., description="ID sequencial do documento no contexto")
    tribunal: Optional[str] = None
    processo: Optional[str] = None
    ano: Optional[int] = None
    tema: Optional[str] = None
    relevanciaRelativa: float = Field(..., description="Relevância relativa em %")
    trechoUtilizado: str = Field(..., description="Trecho concreto usado na análise")


class RagQueryResponse(BaseModel):
    """Resposta estruturada do endpoint /api/rag/query."""
    
    # Metadados da consulta
    queryOriginal: str
    queryNormalizada: Optional[QueryNormalizadaOutput] = None
    timestampConsulta: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Conteúdo da resposta SEEU
    contexto_seeu: str = Field(..., description="Contexto sobre execução penal e SEEU")
    teses: List[TeseJuridica] = Field(default_factory=list)
    aplicacao_caso: str = Field(..., description="Aplicação ao caso concreto")
    jurisprudencias: List[JurisprudenciaReferencia] = Field(default_factory=list)
    avisos_limitacoes: str = Field(
        ...,
        description="Avisos sobre limitações e caráter informativo"
    )
    
    # Metadados técnicos
    backend: str = Field(..., description="Backend usado (faiss, opensearch)")
    totalChunksRecuperados: int = Field(0)
    totalDocumentosUnicos: int = Field(0)


# ========================================
# SCHEMAS AUXILIARES PARA CHUNKING
# ========================================

class ChunkingConfig(BaseModel):
    """Configuração para chunking de documentos."""
    tamanho_alvo: int = Field(600, description="Tamanho alvo do chunk em tokens")
    tamanho_min: int = Field(400, description="Tamanho mínimo aceitável")
    tamanho_max: int = Field(800, description="Tamanho máximo aceitável")
    overlap: int = Field(100, description="Overlap entre chunks em tokens")
    separadores: List[str] = Field(
        default_factory=lambda: ["\n\n", "\n", ". ", " "],
        description="Separadores para quebra de texto"
    )


class DocumentoParaChunking(BaseModel):
    """Documento original a ser quebrado em chunks."""
    id: str
    texto: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
