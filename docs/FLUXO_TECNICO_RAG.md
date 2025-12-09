# Fluxo Técnico RAG - Retrieval-Augmented Generation

## 📋 Visão Geral Técnica

Este documento descreve em detalhes técnicos e lógicos o fluxo completo de funcionamento do sistema RAG (Retrieval-Augmented Generation) quando o usuário escolhe o modo de operação RAG na interface.

## 🏗️ Arquitetura do Sistema

O sistema RAG é composto por três componentes principais:

1. **Interface (Nuxt 3 + TypeScript)** - Frontend e API intermediária
2. **DBVECTOR (FastAPI + Python)** - Serviço de busca vetorial
3. **OpenAI API** - LLM para geração de respostas

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Interface  │────────▶│   DBVECTOR   │         │   OpenAI    │
│  (Nuxt 3)   │         │   (FastAPI)  │         │     API     │
│             │◀────────│              │         │             │
└──────┬──────┘         └──────────────┘         └──────▲──────┘
       │                                                 │
       └─────────────────────────────────────────────────┘
```

## 🔄 Fluxo Detalhado do RAG

### **Fase 1: Inicialização do Modo RAG**

#### 1.1 Seleção do Modo (Frontend)
**Arquivo:** `/Interface/app/pages/index.vue`

```typescript
const useRAG = ref(true) // Toggle entre RAG e chat simples
```

**Lógica:**
- Variável reativa `useRAG` controla o modo de operação
- `true` = Modo RAG (busca documentos + LLM)
- `false` = Chat Simples (direto para LLM)
- Interface oferece toggle visual para o usuário

**Estado:** O usuário seleciona "RAG" na interface

---

### **Fase 2: Submissão da Query**

#### 2.1 Captura e Validação (Frontend)
**Arquivo:** `/Interface/app/pages/index.vue` - Função `onSubmit()`

```typescript
function onSubmit() {
  if (input.value.trim()) {
    sendToOpenAI(input.value)
  }
}
```

**Lógica:**
- Captura texto do input
- Valida que não está vazio (após trim)
- Chama função `sendToOpenAI()` com a query

**Exemplo de Query:** 
```
"Quais são os direitos fundamentais previstos na Constituição?"
```

---

### **Fase 3: Busca Vetorial (Retrieval)**

#### 3.1 Verificação do Modo RAG (Frontend)
**Arquivo:** `/Interface/app/pages/index.vue` - Função `sendToOpenAI()`

```typescript
if (useRAG.value) {
  // Busca documentos no DBVECTOR
  const dbvectorResponse = await $fetch<DBVectorSearchResponse>(
    '/api/dbvector/search',
    {
      method: 'POST',
      body: { q: prompt, k: 5 }
    }
  )
}
```

**Lógica:**
- Verifica se `useRAG.value === true`
- Se sim, faz requisição HTTP POST para `/api/dbvector/search`
- Parâmetros:
  - `q`: Query do usuário (string)
  - `k`: Número de documentos a retornar (int, default=5)

---

#### 3.2 Proxy da Interface (Backend Nuxt)
**Arquivo:** `/Interface/server/api/dbvector/search.post.ts`

```typescript
export default defineEventHandler(async (event) => {
  const body = await readBody<DBVectorSearchRequest>(event)
  
  // Validação
  if (!body.q || !body.q.trim()) {
    throw createError({
      statusCode: 400,
      message: 'Query (q) is required'
    })
  }

  const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
  const searchUrl = `${dbvectorUrl}/search`
  
  const response = await $fetch<DBVectorSearchResponse>(searchUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: { q: body.q, k: body.k || 5 }
  })

  return response
})
```

**Lógica:**
1. Recebe requisição do frontend
2. Valida presença da query
3. Lê URL do DBVECTOR de `config.public.dbvectorApiUrl`
4. Faz proxy da requisição para o serviço DBVECTOR
5. Retorna resposta para o frontend

**Propósito do Proxy:**
- Centraliza configurações de URL
- Adiciona logging e tratamento de erros
- Permite futuras transformações de dados

---

#### 3.3 API DBVECTOR - Endpoint de Busca
**Arquivo:** `/DBVECTOR/src/api/main.py` - Endpoint `/search`

```python
@app.post("/search", response_model=SearchResponseAPI)
async def search_documents(request: SearchRequest):
    # Validações
    if store is None:
        raise HTTPException(status_code=503, detail="Store não inicializado")
    
    if not request.q or not request.q.strip():
        raise HTTPException(status_code=422, detail="Query não pode ser vazia")
    
    doc_count = store.get_doc_count()
    if doc_count == 0:
        raise HTTPException(status_code=404, detail="Nenhum documento indexado")
    
    # Gera embedding da query
    query_vector = embeddings.encode_single_text(request.q)
    
    # Busca documentos
    results = store.search(query_vector, k=request.k)
    
    # Converte para modelo API
    api_results = [
        SearchResultAPI(
            id=result.doc.id,
            title=result.doc.title,
            text=result.doc.text,
            court=result.doc.court,
            code=result.doc.code,
            article=result.doc.article,
            date=result.doc.date,
            meta=result.doc.meta,
            score=result.score
        )
        for result in results
    ]
    
    return SearchResponseAPI(
        query=request.q,
        total=len(api_results),
        backend=config.SEARCH_BACKEND,
        results=api_results
    )
```

**Lógica Detalhada:**

1. **Validação de Estado:**
   - Verifica se o `store` (FAISS ou OpenSearch) está inicializado
   - Verifica se há documentos indexados (`doc_count > 0`)

2. **Geração de Embedding:**
   - Chama `embeddings.encode_single_text(query)`
   - Usa modelo sentence-transformers (default: `all-MiniLM-L6-v2`)
   - Retorna vetor numpy de dimensão 384 (float32)
   - Embedding é normalizado se `NORMALIZE_EMBEDDINGS=true`

3. **Busca Vetorial:**
   - Chama `store.search(query_vector, k=5)`
   - Store pode ser FAISS (local) ou OpenSearch (distribuído)

---

#### 3.4 Geração de Embedding da Query
**Arquivo:** `/DBVECTOR/src/embeddings.py`

```python
def encode_single_text(text: str) -> np.ndarray:
    """
    Gera embedding para um único texto.
    
    Returns:
        Array numpy com shape (embedding_dim,)
    """
    embeddings = encode_texts([text])
    return embeddings[0]

def encode_texts(texts: List[str]) -> np.ndarray:
    """
    Gera embeddings para lista de textos.
    
    Returns:
        Array numpy de embeddings com shape (len(texts), embedding_dim)
        Tipo: np.float32
        Normalizado se config.NORMALIZE_EMBEDDINGS=True
    """
    model = load_model()
    
    embeddings = model.encode(
        texts,
        normalize_embeddings=config.NORMALIZE_EMBEDDINGS,
        show_progress_bar=len(texts) > 10,
        convert_to_numpy=True
    )

    arr = np.array(embeddings)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    return arr.astype(np.float32)
```

**Lógica Técnica:**

1. **Carregamento do Modelo (Singleton):**
   - Modelo é carregado uma única vez na memória
   - Usa `SentenceTransformer` da biblioteca sentence-transformers
   - Modelo padrão: `sentence-transformers/all-MiniLM-L6-v2`
   - Dimensão: 384
   - Armazenado em cache na GPU se disponível

2. **Encoding:**
   - Tokenização do texto
   - Passagem pela rede neural (BERT-based)
   - Pooling (mean pooling) para gerar vetor de dimensão fixa
   - Normalização L2 (opcional, padrão=true)
   - Conversão para numpy float32

3. **Output:**
   - Vetor numpy de shape `(384,)`
   - Tipo: `np.float32`
   - Normalizado: `||v|| = 1.0` (se configurado)

**Exemplo:**
```python
# Input: "direitos fundamentais"
# Output: array([0.123, -0.456, 0.789, ..., 0.234], dtype=float32)
# Shape: (384,)
```

---

#### 3.5 Busca no Índice FAISS
**Arquivo:** `/DBVECTOR/src/storage/faiss_store.py`

```python
def search(self, query_vector: np.ndarray, k: int = 5) -> List[SearchResult]:
    """Busca documentos similares."""
    if self._index is None or self._index.ntotal == 0:
        return []
    
    # Garante que query_vector é 2D
    if query_vector.ndim == 1:
        query_vector = query_vector.reshape(1, -1)
    
    # Busca no FAISS
    scores, internal_ids = self._index.search(query_vector, k)

    results = []
    for score, internal_id in zip(scores[0], internal_ids[0]):
        if internal_id == -1:  # ID inválido
            continue
            
        if internal_id in self.metadata:
            doc_data = self.metadata[internal_id]
            doc = Doc(
                id=doc_data['id'],
                text=doc_data['text'],
                title=doc_data['title'],
                court=doc_data['court'],
                code=doc_data['code'],
                article=doc_data['article'],
                date=doc_data['date'],
                meta=doc_data['meta']
            )
            results.append(SearchResult(doc=doc, score=float(score)))
    
    return results
```

**Lógica Técnica do FAISS:**

1. **Preparação do Vetor:**
   - Converte vetor 1D para 2D: `(384,)` → `(1, 384)`
   - FAISS requer arrays 2D (batch)

2. **Busca por Similaridade:**
   - Usa `IndexFlatIP` (Inner Product)
   - Com vetores normalizados, IP = cosine similarity
   - Retorna top-k documentos mais similares
   - Algoritmo: força bruta (exato, não aproximado)
   - Complexidade: O(n * d) onde n = docs, d = dimensão

3. **Scores:**
   - Range: [-1, 1] se normalizado (cosine)
   - Maior = mais similar
   - Threshold típico: > 0.5 para relevância

4. **Recuperação de Metadados:**
   - FAISS armazena apenas vetores
   - Metadados (title, text, court, etc.) em Parquet separado
   - Lookup por `internal_id` (hash do doc.id)

5. **Estrutura do Índice:**
   ```python
   # Estrutura em memória
   self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(384))
   # Metadados
   self.metadata = {
       internal_id: {
           'id': 'doc_123',
           'text': 'conteúdo...',
           'title': 'título',
           'court': 'STF',
           'code': 'CF',
           'article': '5º',
           'date': '2024-01-15',
           'meta': {}
       }
   }
   ```

6. **GPU Support (Opcional):**
   - Se `USE_FAISS_GPU=true` e GPU disponível
   - Índice é movido para GPU na inicialização
   - Acelera busca em grandes volumes (>100k docs)

**Exemplo de Busca:**
```python
# Input
query_vector = [0.123, -0.456, ..., 0.234]  # shape (384,)
k = 5

# FAISS Search
scores = [0.89, 0.85, 0.82, 0.78, 0.75]  # similarity scores
internal_ids = [1234, 5678, 9012, 3456, 7890]

# Output
results = [
    SearchResult(
        doc=Doc(id='doc_abc', text='...', title='...', court='STF', ...),
        score=0.89
    ),
    # ... mais 4 resultados
]
```

---

#### 3.6 Resposta da Busca
**Formato JSON retornado para Interface:**

```json
{
  "query": "Quais são os direitos fundamentais?",
  "total": 5,
  "backend": "faiss",
  "results": [
    {
      "id": "cf88_art5_inciso1",
      "title": "Constituição Federal - Artigo 5º",
      "text": "Todos são iguais perante a lei, sem distinção de qualquer natureza...",
      "court": "STF",
      "code": "CF/88",
      "article": "5º, I",
      "date": "1988-10-05",
      "meta": {
        "url": "https://...",
        "type": "constitution"
      },
      "score": 0.8945
    },
    {
      "id": "cf88_art5_inciso2",
      "title": "Constituição Federal - Artigo 5º",
      "text": "Ninguém será obrigado a fazer ou deixar de fazer alguma coisa...",
      "court": "STF",
      "code": "CF/88",
      "article": "5º, II",
      "date": "1988-10-05",
      "meta": {},
      "score": 0.8523
    }
    // ... mais 3 documentos
  ]
}
```

---

### **Fase 4: Construção do Prompt Augmented**

#### 4.1 Formatação do Contexto (Frontend)
**Arquivo:** `/Interface/app/pages/index.vue`

```typescript
if (dbvectorResponse.results && dbvectorResponse.results.length > 0) {
  // Formata os documentos encontrados como contexto
  const context = dbvectorResponse.results.map((result, index) => {
    const metadata = []
    if (result.court) metadata.push(`Tribunal: ${result.court}`)
    if (result.code) metadata.push(`Código: ${result.code}`)
    if (result.article) metadata.push(`Artigo: ${result.article}`)
    if (result.date) metadata.push(`Data: ${result.date}`)
    
    return `
[Documento ${index + 1}${result.title ? ` - ${result.title}` : ''}]
${metadata.length > 0 ? metadata.join(' | ') : ''}
Relevância: ${(result.score * 100).toFixed(1)}%

${result.text}
    `.trim()
  }).join('\n\n---\n\n')

  contextInfo = `📚 Consultados ${dbvectorResponse.results.length} documentos jurídicos (${dbvectorResponse.backend})`

  // Monta o prompt com contexto RAG
  finalPrompt = `Você é um assistente jurídico especializado. Use os seguintes documentos jurídicos como base para responder a pergunta do usuário de forma precisa e fundamentada.

DOCUMENTOS DE REFERÊNCIA:
${context}

PERGUNTA DO USUÁRIO:
${prompt}

INSTRUÇÕES:
- Baseie sua resposta nos documentos fornecidos
- Cite os documentos relevantes quando aplicável
- Se os documentos não contiverem informação suficiente, mencione isso
- Seja claro, objetivo e mantenha terminologia jurídica apropriada`
}
```

**Lógica de Construção:**

1. **Iteração sobre Resultados:**
   - Para cada documento retornado pelo DBVECTOR
   - Extrai metadados estruturados (court, code, article, date)

2. **Formatação Individual:**
   - Cabeçalho: `[Documento N - Título]`
   - Metadados: `Tribunal: STF | Código: CF/88 | Artigo: 5º`
   - Relevância: `Relevância: 89.5%` (score * 100)
   - Conteúdo: texto completo do documento

3. **Separação:**
   - Documentos separados por `\n\n---\n\n`
   - Facilita leitura pelo LLM

4. **Template do Prompt:**
   - **System Context:** Define papel (assistente jurídico)
   - **Documentos de Referência:** Contexto recuperado
   - **Pergunta do Usuário:** Query original
   - **Instruções:** Diretrizes para o LLM

**Exemplo de Prompt Construído:**

```text
Você é um assistente jurídico especializado. Use os seguintes documentos jurídicos como base para responder a pergunta do usuário de forma precisa e fundamentada.

DOCUMENTOS DE REFERÊNCIA:
[Documento 1 - Constituição Federal - Artigo 5º]
Tribunal: STF | Código: CF/88 | Artigo: 5º, I
Relevância: 89.5%

Todos são iguais perante a lei, sem distinção de qualquer natureza, garantindo-se aos brasileiros e aos estrangeiros residentes no País a inviolabilidade do direito à vida, à liberdade, à igualdade, à segurança e à propriedade...

---

[Documento 2 - Constituição Federal - Artigo 5º]
Tribunal: STF | Código: CF/88 | Artigo: 5º, II
Relevância: 85.2%

Ninguém será obrigado a fazer ou deixar de fazer alguma coisa senão em virtude de lei...

---

[... 3 documentos adicionais ...]

PERGUNTA DO USUÁRIO:
Quais são os direitos fundamentais previstos na Constituição?

INSTRUÇÕES:
- Baseie sua resposta nos documentos fornecidos
- Cite os documentos relevantes quando aplicável
- Se os documentos não contiverem informação suficiente, mencione isso
- Seja claro, objetivo e mantenha terminologia jurídica apropriada
```

---

### **Fase 5: Geração da Resposta (LLM)**

#### 5.1 Requisição para OpenAI (Frontend → Backend)
**Arquivo:** `/Interface/app/pages/index.vue`

```typescript
const result = await $fetch<OpenAIResponse>('/api/openai/chat', {
  method: 'POST',
  body: {
    prompt: finalPrompt,
    model: model.value?.replace('openai/', '') || 'gpt-4o-mini'
  }
})
```

**Parâmetros:**
- `prompt`: Prompt completo (query + contexto RAG)
- `model`: Modelo OpenAI selecionado pelo usuário
  - `gpt-4o-mini` (default, rápido, econômico)
  - `gpt-4o` (mais capaz, mais caro)
  - `gpt-5-mini` / `o1-mini` (reasoning models)

---

#### 5.2 API OpenAI Wrapper (Backend Nuxt)
**Arquivo:** `/Interface/server/api/openai/chat.post.ts`

```typescript
export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const config = useRuntimeConfig()
  
  const modelName = body.model || 'gpt-4o-mini'
  const isReasoningModel = modelName.includes('o1') || modelName.includes('gpt-5')
  
  const requestBody: any = {
    model: modelName,
    messages: [
      {
        role: 'user',
        content: body.prompt
      }
    ],
    max_completion_tokens: 10000
  }

  // Modelos de reasoning não suportam temperature
  if (!isReasoningModel) {
    requestBody.temperature = 1
  }

  const response = await $fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${config.openaiApiKey}`,
      'Content-Type': 'application/json',
      ...(config.openaiProjectId ? { 'OpenAI-Project': config.openaiProjectId } : {})
    },
    body: requestBody
  })

  return response
})
```

**Lógica Técnica:**

1. **Segurança:**
   - API key armazenada no servidor (variável ambiente)
   - Nunca exposta ao frontend
   - Backend atua como proxy seguro

2. **Configuração do Request:**
   - **model:** Modelo LLM específico
   - **messages:** Array com role + content
   - **max_completion_tokens:** Limite de tokens na resposta (10k)
   - **temperature:** Criatividade (0-2, default=1)
     - Reasoning models (o1, gpt-5) não usam temperature

3. **Headers:**
   - `Authorization`: Bearer token com API key
   - `OpenAI-Project`: ID do projeto (opcional)

4. **Endpoint:**
   - `https://api.openai.com/v1/chat/completions`
   - API oficial OpenAI Chat Completions

---

#### 5.3 Processamento pelo LLM (OpenAI)

**Processo Interno do GPT:**

1. **Tokenização:**
   - Prompt é dividido em tokens (subwords)
   - Modelo: ~750 tokens por 1000 caracteres
   - Limite contextual: 128k tokens (gpt-4o-mini)

2. **Encoding:**
   - Tokens → embeddings (dimensão 12288 para GPT-4)
   - Positional encoding adicionado

3. **Transformer Layers:**
   - Self-attention multi-head
   - Feed-forward networks
   - ~50 layers (GPT-4o-mini)

4. **Generation:**
   - Autoregressive: gera token por token
   - Sampling com temperature
   - Top-p (nucleus sampling) para diversidade

5. **Grounding:**
   - LLM "lê" os documentos fornecidos no contexto
   - Usa informações factuais para fundamentar resposta
   - Reduz alucinações (fabricação de informações)

**Exemplo de Response:**

```json
{
  "id": "chatcmpl-AbC123",
  "object": "chat.completion",
  "created": 1733688000,
  "model": "gpt-4o-mini-2024-07-18",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Com base nos documentos jurídicos consultados, os direitos fundamentais previstos na Constituição Federal de 1988 incluem:\n\n1. **Igualdade** (Art. 5º, I): Todos são iguais perante a lei...\n\n2. **Legalidade** (Art. 5º, II): Ninguém será obrigado a fazer ou deixar de fazer...\n\n[... resposta completa fundamentada nos documentos ...]"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 2543,
    "completion_tokens": 487,
    "total_tokens": 3030
  }
}
```

---

### **Fase 6: Apresentação da Resposta**

#### 6.1 Extração e Formatação (Frontend)
**Arquivo:** `/Interface/app/pages/index.vue`

```typescript
// Extrai o texto da resposta
const extractedText = result?.choices?.[0]?.message?.content || ''

// Adiciona informação de contexto
const finalResponse = contextInfo 
  ? `${contextInfo}\n\n${extractedText}`
  : extractedText

response.value = finalResponse
```

**Lógica:**

1. **Extração:**
   - Navega na estrutura JSON: `choices[0].message.content`
   - Fallback para string vazia se não existir

2. **Enriquecimento:**
   - Adiciona badge informativo: `📚 Consultados 5 documentos jurídicos (faiss)`
   - Separa badge da resposta com `\n\n`

3. **Renderização:**
   - Resposta é exibida na interface
   - Suporte para Markdown (listas, negrito, etc.)
   - Botão de copiar para clipboard

**Exemplo de Resposta Final:**

```
📚 Consultados 5 documentos jurídicos (faiss)

Com base nos documentos jurídicos consultados, os direitos fundamentais previstos na Constituição Federal de 1988 incluem:

1. **Igualdade** (Art. 5º, I): Todos são iguais perante a lei, sem distinção de qualquer natureza, garantindo-se aos brasileiros e aos estrangeiros residentes no País a inviolabilidade do direito à vida, à liberdade, à igualdade, à segurança e à propriedade.

2. **Legalidade** (Art. 5º, II): Ninguém será obrigado a fazer ou deixar de fazer alguma coisa senão em virtude de lei.

[... resposta completa ...]

Esses direitos estão fundamentados nos documentos consultados da base de conhecimento jurídica.
```

---

## 🔍 Comparação: RAG vs. Chat Simples

### **Modo RAG (useRAG = true)**

```
Usuário → Interface → DBVECTOR → Interface → OpenAI → Interface → Resposta Fundamentada
          ↓           ↓                       ↓
      Busca Docs   Retrieval             Prompt + Context
```

**Características:**
- ✅ Resposta baseada em documentos reais
- ✅ Reduz alucinações
- ✅ Cita fontes jurídicas
- ✅ Maior latência (~2-4s)
- ✅ Mais preciso e confiável

### **Chat Simples (useRAG = false)**

```
Usuário → Interface → OpenAI → Interface → Resposta Genérica
                      ↓
                  Apenas LLM
```

**Características:**
- ✅ Menor latência (~1-2s)
- ❌ Não consulta base de conhecimento
- ❌ Pode alucinar informações
- ❌ Sem fontes jurídicas
- ✅ Bom para conversas gerais

---

## 📊 Métricas e Performance

### **Latências Típicas**

| Fase | Operação | Tempo Médio |
|------|----------|-------------|
| 1 | Geração Embedding Query | 50-100ms |
| 2 | Busca FAISS (724k docs) | 100-200ms |
| 3 | Construção Prompt | 10-20ms |
| 4 | Chamada OpenAI | 1500-3000ms |
| **Total** | **Modo RAG** | **~2-4s** |
| **Total** | **Chat Simples** | **~1-2s** |

### **Recursos Computacionais**

**DBVECTOR:**
- CPU: 2-4 cores (para embedding + FAISS)
- RAM: ~4GB (índice + metadados + modelo)
- GPU (opcional): Acelera embedding e FAISS

**Interface:**
- Leve: apenas proxy HTTP
- RAM: ~200MB

**OpenAI:**
- Serverless (API externa)
- Pay-per-use

---

## 🔐 Configurações Importantes

### **Environment Variables**

**DBVECTOR (`.env`):**
```bash
# Backend de busca
SEARCH_BACKEND=faiss  # ou 'opensearch'

# Modelo de embedding
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
NORMALIZE_EMBEDDINGS=true

# FAISS
FAISS_INDEX_PATH=data/indexes/faiss
FAISS_METADATA_PATH=data/indexes/faiss/metadata.parquet
USE_FAISS_GPU=false  # true se GPU disponível
FAISS_GPU_DEVICE=0

# API
API_HOST=0.0.0.0
API_PORT=8000
```

**Interface (`.env`):**
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_PROJECT_ID=proj_...  # opcional

# DBVECTOR
NUXT_PUBLIC_DBVECTOR_API_URL=http://localhost:8000
```

---

## 🧪 Testando o Fluxo

### **1. Verificar DBVECTOR**
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"q": "direitos fundamentais", "k": 3}'
```

**Resposta Esperada:**
```json
{
  "query": "direitos fundamentais",
  "total": 3,
  "backend": "faiss",
  "results": [...]
}
```

### **2. Testar Interface RAG**
1. Acesse `http://localhost:3000`
2. Selecione modo "RAG"
3. Digite: "Quais são os direitos fundamentais?"
4. Observe logs no console (F12)

**Logs Esperados:**
```
[HomePage] Creating new chat { promptLength: 40, useRAG: true }
[HomePage] RAG mode enabled - searching DBVECTOR { query: "..." }
[DBVECTOR API] Sending request to DBVECTOR { url: "...", k: 5 }
[DBVECTOR API] DBVECTOR search successful { total: 5, backend: "faiss" }
[HomePage] DBVECTOR search completed { total: 5, resultsCount: 5 }
[OpenAI API] Sending request to OpenAI { model: "gpt-4o-mini", ... }
[OpenAI API] OpenAI request successful { contentLength: 1234 }
[HomePage] Request completed { responseLength: 1300 }
```

---

## 🐛 Troubleshooting

### **Problema: "Store não inicializado"**
**Causa:** DBVECTOR não carregou índice FAISS  
**Solução:**
```bash
cd DBVECTOR
make faiss-build
```

### **Problema: "Nenhum documento indexado"**
**Causa:** Índice FAISS vazio  
**Solução:**
```bash
# Verificar dados
ls data/merged_clean.jsonl

# Rebuild index
python -m src.pipelines.build_faiss
```

### **Problema: Resposta não fundamentada**
**Causa:** Modo RAG desativado ou erro no DBVECTOR  
**Solução:**
1. Verificar toggle na interface (deve estar em "RAG")
2. Verificar logs: deve ter "RAG mode enabled"
3. Verificar saúde do DBVECTOR: `curl http://localhost:8000/health`

### **Problema: Latência muito alta (>10s)**
**Causa:** Modelo embedding lento ou GPU não configurada  
**Solução:**
1. Considerar modelo menor: `all-MiniLM-L6-v2` (384d) vs `all-mpnet-base-v2` (768d)
2. Habilitar GPU: `USE_FAISS_GPU=true` (se disponível)
3. Reduzir `k` (menos documentos recuperados)

---

## 📚 Referências Técnicas

### **Bibliotecas Principais**

- **sentence-transformers**: Geração de embeddings
- **FAISS**: Busca vetorial eficiente (Facebook AI)
- **FastAPI**: API backend Python
- **Nuxt 3**: Framework frontend/backend
- **OpenAI API**: LLM (GPT-4o-mini)

### **Papers e Conceitos**

- **RAG:** Lewis et al., 2020 - "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
- **FAISS:** Johnson et al., 2019 - "Billion-scale similarity search with GPUs"
- **Sentence-BERT:** Reimers & Gurevych, 2019 - "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks"

---

## 🎯 Melhorias Futuras

### **Performance**
- [ ] Cache de embeddings de queries frequentes
- [ ] Pré-ranking com BM25 + re-ranking com FAISS
- [ ] Quantização de embeddings (int8) para reduzir memória

### **Qualidade**
- [ ] Reranker cross-encoder para refinar top-k
- [ ] Feedback de relevância (usuário marca respostas úteis)
- [ ] Chunking inteligente de documentos longos

### **Infraestrutura**
- [ ] Deploy com Docker Compose
- [ ] Monitoramento com Prometheus + Grafana
- [ ] Rate limiting e autenticação
- [ ] Backup incremental do índice FAISS

---

## 📝 Conclusão

O fluxo RAG implementado neste sistema combina:

1. **Busca Vetorial Eficiente:** FAISS para recuperar documentos relevantes em milissegundos
2. **Embeddings Semânticos:** Sentence-transformers para capturar significado, não apenas palavras-chave
3. **Augmented Generation:** LLM fundamentado em contexto jurídico real
4. **Arquitetura Modular:** Componentes independentes e escaláveis

**Resultado:** Respostas jurídicas precisas, fundamentadas e verificáveis, reduzindo drasticamente alucinações do LLM e aumentando confiabilidade do sistema.
