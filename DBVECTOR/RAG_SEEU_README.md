# RAG Jurídico SEEU - Sistema de Execução Penal

Sistema de Retrieval-Augmented Generation (RAG) especializado em **execução penal** e integrado ao **Sistema Eletrônico de Execução Unificado (SEEU)**.

---

## 📋 Visão Geral

Este sistema implementa um fluxo RAG completo para consultas jurídicas sobre execução penal:

1. **Normalização Jurídica** - Transforma consultas em linguagem natural para queries técnico-jurídicas
2. **Busca Vetorial** - Recupera chunks relevantes de jurisprudência usando FAISS/OpenSearch
3. **Cálculo de Relevância Relativa** - Normaliza scores usando softmax
4. **Geração de Resposta Estruturada** - LLM gera análise jurídica com teses, aplicação e referências

---

## 🏗️ Arquitetura

```
┌─────────────────┐
│  Frontend       │
│  (Nuxt)         │
└────────┬────────┘
         │
         │ POST /api/rag/query
         │ {promptUsuario, useRag, metadados, k}
         ▼
┌─────────────────────────────────────────────────┐
│  Backend RAG Orquestrador                       │
│  (FastAPI + RagService)                         │
├─────────────────────────────────────────────────┤
│                                                 │
│  ETAPA 1: Normalização Jurídica                 │
│  ├─ LLM (GPT/Claude)                           │
│  └─ Output: QueryNormalizadaOutput             │
│      {queryRAG, temas, dados execução, etc}    │
│                                                 │
│  ETAPA 2: Busca Vetorial                        │
│  ├─ Embedding da queryRAG                      │
│  ├─ FAISS/OpenSearch → TOP-K chunks            │
│  └─ Agrupamento por documento                  │
│                                                 │
│  ETAPA 3: Cálculo de Relevância                 │
│  └─ Softmax → relevância relativa em %         │
│                                                 │
│  ETAPA 4: Geração de Resposta                   │
│  ├─ Monta contexto estruturado                 │
│  ├─ LLM com template SEEU                      │
│  └─ Parse e estruturação                       │
│                                                 │
└────────┬────────────────────────────────────────┘
         │
         │ RagQueryResponse JSON
         │ {contexto_seeu, teses, jurisprudencias, etc}
         ▼
┌─────────────────┐
│  Frontend       │
│  Exibição       │
└─────────────────┘
```

---

## 🚀 Quickstart

### 1. Configuração

```bash
# Clone e entre no diretório
cd DBVECTOR

# Configure variáveis de ambiente
cp .env.example .env
nano .env
```

**Variáveis essenciais:**

```bash
# Backend de busca
SEARCH_BACKEND=faiss

# Modelo de embedding
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# LLM (configure pelo menos uma)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# OU
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

### 2. Instalação de Dependências

```bash
pip install -r requirements.txt
```

### 3. Indexação de Documentos

```bash
# Indexa documentos com FAISS
python -m src.pipelines.build_faiss

# OU com OpenSearch
python -m src.pipelines.build_opensearch
```

### 4. Iniciar API

```bash
# Desenvolvimento
python -m uvicorn src.api.main:app --reload --port 8000

# Produção
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Testar Implementação

```bash
python test_rag_implementation.py
```

---

## 📡 Endpoints da API

### `POST /api/rag/query` - RAG Completo

**Request:**

```json
{
  "promptUsuario": "Meu cliente está há 2 anos em semiaberto sem faltas graves. Pode progredir?",
  "useRag": true,
  "metadados": {
    "tribunal": "STJ",
    "anoMin": 2020,
    "anoMax": 2024,
    "tipoConsulta": "jurisprudencia"
  },
  "k": 10
}
```

**Response:**

```json
{
  "queryOriginal": "...",
  "queryNormalizada": {
    "intencao": "analise_progressao_regime",
    "tipoBeneficioOuTema": "progressao_regime",
    "dadosExecucaoPenal": {
      "regimeAtual": "semiaberto",
      "tempoCumpridoAproximado": "2 anos",
      "faltasGraves": "nenhuma",
      "tipoCrime": null,
      "outrosDadosRelevantes": null
    },
    "temaExecucao": ["progressao_regime", "requisitos_objetivos_subjetivos"],
    "palavrasChaveJuridicas": ["LEP art. 112", "requisito objetivo", "bom comportamento"],
    "queryRAG": "requisitos progressão regime semiaberto para aberto execução penal",
    "observacoes": null
  },
  "timestampConsulta": "2024-12-08T10:30:00Z",
  "contexto_seeu": "O SEEU é o sistema que gerencia...",
  "teses": [
    {
      "titulo": "Requisitos para progressão de regime",
      "descricao": "De acordo com o art. 112 da LEP...",
      "documentosSuporte": [1, 3, 5]
    }
  ],
  "aplicacao_caso": "No caso concreto, considerando que o cliente...",
  "jurisprudencias": [
    {
      "docId": 1,
      "tribunal": "STJ",
      "processo": "HC 123456/SP",
      "ano": 2023,
      "tema": "Progressão de regime",
      "relevanciaRelativa": 34.2,
      "trechoUtilizado": "O direito à progressão de regime...",
      "pdfDownloadUrl": "https://..."
    }
  ],
  "avisos_limitacoes": "Esta análise tem caráter informativo...",
  "backend": "FAISSStore",
  "totalChunksRecuperados": 10,
  "totalDocumentosUnicos": 5
}
```

### `POST /search` - Busca Vetorial Simples

Endpoint legado para busca vetorial direta (sem RAG).

---

## 🔧 Componentes Principais

### 1. **RagService** (`src/rag_service.py`)

Orquestrador principal do fluxo RAG:

- Coordena normalização → busca → LLM
- Calcula relevância relativa (softmax)
- Monta contexto estruturado por chunks
- Gera resposta no formato SEEU

### 2. **LegalQueryNormalizer** (`src/rag_normalizer.py`)

Normaliza queries para linguagem jurídica:

- Extrai intenção e dados de execução penal
- Identifica temas e palavras-chave jurídicas
- Reescreve query para busca otimizada
- Retorna JSON estruturado

### 3. **DocumentChunker** (`src/chunking.py`)

Sistema de chunking inteligente:

- Quebra documentos em chunks de 400-800 tokens
- Overlap de ~100 tokens para preservar contexto
- Quebra em pontos naturais (parágrafos, frases)
- Mantém metadados completos por chunk

### 4. **Schemas Pydantic** (`src/rag_schemas.py`)

Modelos de dados validados:

- `RagQueryRequest` / `RagQueryResponse`
- `QueryNormalizadaOutput`
- `ChunkWithScore`
- `TeseJuridica` / `JurisprudenciaReferencia`

---

## 📊 Chunking de Documentos

### Por que chunks?

Documentos jurídicos (acórdãos, decisões) são longos demais para processar inteiros. Chunking permite:

1. **Busca mais precisa** - Recupera trechos específicos relevantes
2. **Contexto gerenciável** - LLM recebe apenas partes relevantes
3. **Escalabilidade** - Processa documentos de qualquer tamanho

### Configuração de Chunking

```python
from src.rag_schemas import ChunkingConfig

config = ChunkingConfig(
    tamanho_alvo=600,      # Tamanho alvo em tokens
    tamanho_min=400,       # Mínimo aceitável
    tamanho_max=800,       # Máximo aceitável
    overlap=100,           # Overlap entre chunks
    separadores=[          # Separadores hierárquicos
        "\n\n",            # Parágrafos
        "\n",              # Linhas
        ". ",              # Frases
        " "                # Palavras (fallback)
    ]
)
```

### Exemplo de Uso

```python
from src.chunking import DocumentChunker
from src.rag_schemas import DocumentoParaChunking

doc = DocumentoParaChunking(
    id="HC123456",
    texto="Texto longo do acórdão...",
    metadata={
        "tribunal": "STJ",
        "numeroProcesso": "HC 123456/SP",
        "pdfId": "stj_hc_123456"
    }
)

chunker = DocumentChunker(config)
chunks = chunker.chunk_documento(doc)

# chunks = [
#   {
#     "idDocumentoGlobal": "HC123456",
#     "idChunk": "HC123456_chunk_0",
#     "texto": "...",
#     "metadata": {
#       "tribunal": "STJ",
#       "posicaoChunk": 0,
#       "totalChunks": 3,
#       ...
#     }
#   },
#   ...
# ]
```

---

## 🎯 Cálculo de Relevância Relativa

**Problema**: Scores brutos de similaridade (ex: cosine similarity) não são probabilidades e variam muito entre consultas.

**Solução**: Normalização softmax para relevância relativa:

```python
def calcular_relevancia_relativa(scores: List[float]) -> List[float]:
    scores_arr = np.array(scores)
    scores_arr = scores_arr - np.max(scores_arr)  # Estabilidade numérica
    exp_scores = np.exp(scores_arr)
    softmax = exp_scores / np.sum(exp_scores)
    return (softmax * 100).tolist()  # Em porcentagem
```

**Resultado**: Cada chunk tem relevância em % que soma 100% no total.

Exemplo:
- Chunk 1: 34.2% (mais relevante)
- Chunk 2: 28.5%
- Chunk 3: 18.1%
- ...

---

## 🧪 Testes

```bash
# Teste completo da implementação
python test_rag_implementation.py

# Testes unitários
pytest tests/

# Teste específico
pytest tests/test_rag_service.py -v
```

---

## 📝 Templates de Prompt

### Template do Normalizador

Ver `src/rag_normalizer.py` - `TEMPLATE_NORMALIZADOR`

**Características:**
- Extrai dados de execução penal
- Identifica intenção e temas
- Reescreve query em linguagem técnica
- Retorna JSON estruturado

### Template RAG SEEU

Ver `src/rag_service.py` - `TEMPLATE_RAG_SEEU`

**Características:**
- Contexto sobre execução penal e SEEU
- Teses jurídicas com documentos de suporte
- Aplicação ao caso concreto
- Lista de jurisprudências com trechos
- Avisos sobre limitações

---

## 🔐 Segurança e Boas Práticas

### Chaves de API

```bash
# NUNCA commite chaves no git
# Use .env (já está no .gitignore)

# Rotação de chaves recomendada a cada 90 dias
# Use secrets manager em produção (AWS Secrets, Azure Key Vault, etc.)
```

### Rate Limiting

Para produção, adicione rate limiting:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/rag/query")
@limiter.limit("10/minute")
async def rag_query(request: Request, ...):
    ...
```

### Logging e Auditoria

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_queries.log'),
        logging.StreamHandler()
    ]
)
```

---

## 🚧 Próximos Passos

### Etapa 5: Pipeline de Indexação com Chunks

- [ ] Adaptar `build_faiss.py` para usar chunking
- [ ] Preprocessar documentos antes de indexar
- [ ] Adicionar metadados completos aos chunks

### Etapa 6: Filtros de Metadados

- [ ] Implementar filtros por tribunal na busca
- [ ] Filtros por ano
- [ ] Filtros por tema

### Etapa 7: Cache e Otimizações

- [ ] Cache de embeddings
- [ ] Cache de respostas frequentes
- [ ] Batch processing de queries

### Etapa 8: Métricas e Monitoramento

- [ ] Latência por etapa (normalização, busca, LLM)
- [ ] Taxa de sucesso/erro
- [ ] Custos de API LLM
- [ ] Qualidade das respostas (feedback)

---

## 📚 Referências

- [Lei de Execução Penal (LEP)](http://www.planalto.gov.br/ccivil_03/leis/l7210.htm)
- [SEEU - Documentação Oficial](https://www.cnj.jus.br/sistemas/seeu/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss/wiki)
- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [Anthropic Claude](https://docs.anthropic.com/)

---

## 📧 Suporte

Para dúvidas ou problemas:

1. Verifique os logs: `tail -f rag_queries.log`
2. Execute testes: `python test_rag_implementation.py`
3. Consulte a documentação da API: `http://localhost:8000/docs`

---

## 📄 Licença

[Inserir licença do projeto]
