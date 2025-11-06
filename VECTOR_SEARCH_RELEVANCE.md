# 🎯 Sistema de Relevância Vetorial - Documentação Técnica

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Score de Relevância](#score-de-relevância)
4. [Fluxo de Dados Completo](#fluxo-de-dados-completo)
5. [Implementação Técnica](#implementação-técnica)
6. [Metadados Jurídicos](#metadados-jurídicos)
7. [Interpretação de Resultados](#interpretação-de-resultados)
8. [Otimizações e Performance](#otimizações-e-performance)
9. [Troubleshooting](#troubleshooting)

---

## 🌟 Visão Geral

O sistema de relevância vetorial é o **coração da busca semântica** no RAG Jurídico. Ele transforma consultas em linguagem natural em vetores matemáticos e encontra documentos juridicamente relevantes através de **similaridade semântica**, não apenas por palavras-chave.

### Componentes Principais

```
┌─────────────────┐
│   Query Texto   │
│ "art. 319 CPP"  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐      ┌──────────────────┐
│   Embedding     │──────▶│  FAISS Index     │
│  Model (768D)   │      │  (Vetores L2)    │
└─────────────────┘      └────────┬─────────┘
                                  │
                                  ↓
                         ┌────────────────┐
                         │ Top-K Docs +   │
                         │ Scores (0-1)   │
                         └────────────────┘
```

### Tecnologias Utilizadas

- **Modelo de Embeddings**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Dimensionalidade**: 768 dimensões
- **Biblioteca de Busca**: FAISS (Facebook AI Similarity Search)
- **Métrica de Similaridade**: Produto Interno (Inner Product) ≈ Cosseno
- **Backend API**: FastAPI (Python 3.12+)
- **Frontend**: Nuxt 3 + TypeScript

---

## 🏗️ Arquitetura do Sistema

### Camadas da Aplicação

#### **1. Frontend (Interface Nuxt 3)**
```typescript
// Interface/app/composables/useVectorSearch.ts
interface SearchDocument {
  id: string
  title?: string
  text: string
  court?: string
  code?: string
  article?: string
  date?: string
  case_number?: string  // Número do processo
  relator?: string      // Ministro relator
  source?: string       // Tribunal (STF, STJ, etc)
  meta?: Record<string, any>
  score: number         // ⭐ Score de relevância (0-1)
}
```

#### **2. Backend (DBVECTOR API - FastAPI)**
```python
# DBVECTOR/src/api/main.py
class SearchResultAPI(BaseModel):
    id: str
    title: Optional[str] = None
    text: str
    court: Optional[str] = None
    code: Optional[str] = None
    article: Optional[str] = None
    date: Optional[str] = None
    case_number: Optional[str] = None
    relator: Optional[str] = None
    source: Optional[str] = None
    meta: Optional[dict] = None
    score: float  # ⭐ Score de relevância
```

#### **3. Storage Layer (FAISS Store)**
```python
# DBVECTOR/src/storage/faiss_store.py
class FAISSStore(VectorStore):
    def search(self, query_vector, k=5) -> List[SearchResult]:
        # Busca vetorial + score de similaridade
        scores, internal_ids = self._index.search(query_vector, k)
        # scores: array([0.856, 0.782, 0.654, ...])
```

---

## 📊 Score de Relevância

### O que é o Score?

O **score de relevância** é um valor numérico entre **-1 e 1** (na prática, **0 a 1** para textos similares) que representa o **quão semanticamente próximo** um documento está da consulta do usuário.

### Como é Calculado?

#### **Passo 1: Vetorização (Embeddings)**

Tanto a query quanto os documentos são transformados em vetores de 768 dimensões:

```python
# Query do usuário
query = "Explique medidas cautelares art. 319 CPP"

# Vetorização usando sentence-transformers
query_vector = encoder.encode(query)
# Resultado: numpy.array([0.123, -0.456, 0.789, ..., 0.321])
#           shape=(768,)

# Documento no banco
doc_text = "Art. 319. São medidas cautelares diversas da prisão..."
doc_vector = encoder.encode(doc_text)
# Resultado: numpy.array([0.145, -0.423, 0.801, ..., 0.298])
#           shape=(768,)
```

#### **Passo 2: Produto Interno (Dot Product)**

O FAISS calcula o **produto interno** entre os vetores:

```python
score = np.dot(query_vector, doc_vector)

# Matematicamente:
# score = Σ(query[i] × doc[i]) para i ∈ [0, 767]
# score = query[0]×doc[0] + query[1]×doc[1] + ... + query[767]×doc[767]
```

#### **Passo 3: Normalização (Implícita)**

Como os embeddings do `sentence-transformers` são **normalizados L2** (norma euclidiana = 1), o produto interno equivale à **similaridade de cosseno**:

```python
# Para vetores normalizados ||v|| = 1:
cosine_similarity(a, b) = dot_product(a, b)

# Geometricamente:
# cos(θ) onde θ é o ângulo entre os vetores
# cos(0°) = 1.0  → Vetores idênticos
# cos(45°) = 0.7 → Vetores similares
# cos(90°) = 0.0 → Vetores ortogonais (sem relação)
```

### Fórmula Completa

```
Score = dot_product(query_embedding, doc_embedding)
      = Σ(q[i] × d[i])  para i ∈ [0, 767]
      = ||q|| × ||d|| × cos(θ)
      = 1 × 1 × cos(θ)    (vetores normalizados)
      = cos(θ)
      ∈ [-1, 1]           (teoricamente)
      ∈ [0, 1]            (na prática para textos em português)
```

### Configuração no FAISS

```python
# DBVECTOR/src/storage/faiss_store.py
# IndexFlatIP = Index Flat Inner Product
base_index = faiss.IndexFlatIP(dimension=768)

# Equivalente a:
# - Busca exaustiva (Flat) sem compressão
# - Métrica de similaridade: Produto Interno (IP)
# - Sem quantização ou clustering
```

---

## 🔄 Fluxo de Dados Completo

### Fluxo End-to-End

```
┌──────────────────────────────────────────────────────────┐
│ 1. USUÁRIO DIGITA QUERY                                  │
│    "Explique medidas cautelares art. 319"                │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 2. FRONTEND (useVectorSearch.ts)                         │
│    - Valida query (min 2 chars)                          │
│    - Chama G1 Query Builder (opcional)                   │
│    - Otimiza: "prisão preventiva art. 319 requisitos"    │
└────────────────────┬─────────────────────────────────────┘
                     │ HTTP POST /search
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 3. BACKEND API (main.py)                                 │
│    POST /search { q: "...", k: 5 }                       │
│    - Valida request                                      │
│    - Gera embedding da query (768D)                      │
└────────────────────┬─────────────────────────────────────┘
                     │ embeddings.encode_single_text()
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 4. EMBEDDING MODEL                                       │
│    paraphrase-multilingual-MiniLM-L12-v2                 │
│    Input:  "prisão preventiva art. 319 requisitos"       │
│    Output: array([0.123, -0.456, ..., 0.789])            │
│            shape=(768,)                                  │
└────────────────────┬─────────────────────────────────────┘
                     │ query_vector
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 5. FAISS STORE (faiss_store.py)                          │
│    store.search(query_vector, k=5)                       │
│    - Carrega índice FAISS                                │
│    - Busca top-k vetores mais próximos                   │
│    - Calcula scores (produto interno)                    │
└────────────────────┬─────────────────────────────────────┘
                     │ scores, internal_ids
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 6. RECONSTRUÇÃO DE DOCUMENTOS                            │
│    Para cada internal_id:                                │
│    - Recupera metadata[internal_id]                      │
│    - Extrai: id, title, text, case_number, relator, etc  │
│    - Cria Doc + SearchResult(doc, score)                 │
└────────────────────┬─────────────────────────────────────┘
                     │ List[SearchResult]
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 7. BACKEND RESPONSE                                      │
│    SearchResponseAPI {                                   │
│      query: "...",                                       │
│      total: 5,                                           │
│      backend: "faiss",                                   │
│      results: [                                          │
│        { id: "HC_187657", score: 0.856, ... },           │
│        { id: "HC_169805", score: 0.782, ... },           │
│        ...                                               │
│      ]                                                   │
│    }                                                     │
└────────────────────┬─────────────────────────────────────┘
                     │ JSON Response
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 8. FRONTEND PROCESSING                                   │
│    vectorResults.value = searchResponse.results          │
│    - Ordena por score (maior → menor)                    │
│    - Exibe documentos relevantes                         │
│    - Calcula avg_score, top_score                        │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 9. G2 ANSWER COMPOSER                                    │
│    - Usa top-k documentos como contexto                  │
│    - Gera resposta fundamentada                          │
│    - Cita fontes: [HC_187657]                            │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────┐
│ 10. ENRIQUECIMENTO DE CITAÇÕES (enrichedCitations)       │
│     - Mapeia citation IDs → documentos completos         │
│     - Extrai: case_number, relator, source, score        │
│     - Exibe em cards visuais                             │
└──────────────────────────────────────────────────────────┘
```

### Exemplo Real com Dados

#### **Input**
```typescript
query: "Explique medidas cautelares art. 319"
k: 5
```

#### **Embedding Gerado**
```python
query_vector: array([
  0.0234, -0.1234,  0.4567, -0.0789,  0.2345,
  0.1111, -0.3333,  0.5555, -0.2222,  0.4444,
  ...  # 768 dimensões total
  0.0987, -0.2345,  0.6789, -0.1234,  0.3456
])
```

#### **FAISS Search**
```python
scores, ids = index.search(query_vector, k=5)

scores: array([0.856, 0.782, 0.654, 0.589, 0.512])
ids:    array([42315, 89234, 12456, 56789, 23451])
```

#### **Documentos Retornados**
```json
{
  "query": "Explique medidas cautelares art. 319",
  "total": 5,
  "backend": "faiss",
  "results": [
    {
      "id": "HC_187657",
      "title": "HC 187657 / GO - GOIÁS",
      "score": 0.856,
      "case_number": "0096679-75.2020.1.00.0000",
      "relator": "CÁRMEN LÚCIA",
      "source": "STF - art_244",
      "date": "05/08/2020",
      "text": "...prisão preventiva art. 319 medidas cautelares..."
    },
    {
      "id": "HC_169805",
      "title": "HC 169805 / PR - PARANÁ",
      "score": 0.782,
      "case_number": "0020283-91.2019.1.00.0000",
      "relator": "CELSO DE MELLO",
      "source": "STF - art_244",
      "date": "07/10/2020",
      "text": "...código penal militar art. 290 prisão preventiva..."
    }
    // ... mais 3 documentos
  ]
}
```

---

## 💻 Implementação Técnica

### Backend: Indexação de Documentos

```python
# DBVECTOR/src/storage/faiss_store.py

def index(self, docs: List[Doc]) -> None:
    """Indexa documentos no FAISS."""
    
    # 1. Gera embeddings para todos os textos
    texts = [doc.text for doc in docs]
    vectors = embeddings.encode_texts(texts)  # shape=(N, 768)
    
    # 2. Cria índice FAISS
    if self._index is None:
        dimension = vectors.shape[1]  # 768
        base_index = faiss.IndexFlatIP(dimension)  # Inner Product
        self._index = faiss.IndexIDMap2(base_index)  # Com IDs customizados
    
    # 3. Armazena metadados (incluindo campos jurídicos)
    internal_ids = []
    for doc in docs:
        internal_id = self._doc_to_internal_id(doc.id)  # Hash do ID
        internal_ids.append(internal_id)
        
        meta = doc.meta or {}
        self.metadata[internal_id] = {
            'id': doc.id,
            'title': doc.title,
            'text': doc.text,
            'court': doc.court,
            'code': doc.code,
            'article': doc.article,
            'date': doc.date,
            'case_number': meta.get('case_number'),  # ⭐ Metadado jurídico
            'relator': meta.get('relator'),          # ⭐ Metadado jurídico
            'source': meta.get('source'),            # ⭐ Metadado jurídico
            'meta': doc.meta
        }
    
    # 4. Adiciona vetores ao índice
    self._index.add_with_ids(
        vectors, 
        np.array(internal_ids, dtype=np.int64)
    )
    
    # 5. Persiste no disco
    self._save_index()
```

### Backend: Busca de Documentos

```python
def search(self, query_vector: np.ndarray, k: int = 5) -> List[SearchResult]:
    """Busca documentos similares."""
    
    # 1. Garante formato 2D: (1, 768)
    if query_vector.ndim == 1:
        query_vector = query_vector.reshape(1, -1)
    
    # 2. Busca no FAISS (retorna scores e IDs)
    scores, internal_ids = self._index.search(query_vector, k)
    
    # 3. Reconstrói documentos a partir dos metadados
    results = []
    for score, internal_id in zip(scores[0], internal_ids[0]):
        if internal_id == -1:  # ID inválido (não encontrado)
            continue
        
        if internal_id in self.metadata:
            doc_data = self.metadata[internal_id]
            
            # Cria objeto Doc
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
            
            # Garante que metadados jurídicos estão no meta
            if not doc.meta:
                doc.meta = {}
            if 'case_number' not in doc.meta and doc_data.get('case_number'):
                doc.meta['case_number'] = doc_data['case_number']
            if 'relator' not in doc.meta and doc_data.get('relator'):
                doc.meta['relator'] = doc_data['relator']
            if 'source' not in doc.meta and doc_data.get('source'):
                doc.meta['source'] = doc_data['source']
            
            # Adiciona resultado com score
            results.append(SearchResult(doc=doc, score=float(score)))
    
    return results
```

### Backend: API Endpoint

```python
# DBVECTOR/src/api/main.py

@app.post("/search", response_model=SearchResponseAPI)
async def search_documents(request: SearchRequest):
    """Busca documentos jurídicos por similaridade semântica."""
    
    # 1. Gera embedding da query
    query_vector = embeddings.encode_single_text(request.q)
    
    # 2. Busca no store
    results = store.search(query_vector, k=request.k)
    
    # 3. Converte para modelo API (extrai metadados do meta)
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
            case_number=meta.get('case_number'),  # ⭐ Extrai do meta
            relator=meta.get('relator'),          # ⭐ Extrai do meta
            source=meta.get('source'),            # ⭐ Extrai do meta
            meta=doc.meta,
            score=result.score  # ⭐ Score de relevância
        )
        api_results.append(api_result)
    
    return SearchResponseAPI(
        query=request.q,
        total=len(api_results),
        backend=config.SEARCH_BACKEND,
        results=api_results
    )
```

### Frontend: Busca Vetorial

```typescript
// Interface/app/composables/useVectorSearch.ts

async function search(
  query: string,
  options: SearchOptions = {}
): Promise<SearchResponse> {
  
  const { k = 5, optimize = true } = options
  
  // 1. Otimiza query com G1 Query Builder (opcional)
  let finalQuery = query
  if (optimize) {
    const optimized = await optimizeQuery({ user_query: query })
    finalQuery = optimized.optimized_query
  }
  
  // 2. Chama API DBVECTOR
  const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
  const response = await $fetch<SearchResponse>(`${dbvectorUrl}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: { q: finalQuery, k }
  })
  
  // 3. Retorna documentos com scores
  return response
}
```

### Frontend: Enriquecimento de Citações

```typescript
// Interface/app/pages/index.vue

// Computed property: mapeia IDs de citações → documentos completos
const enrichedCitations = computed(() => {
  if (!citations.value || citations.value.length === 0) {
    return []
  }
  
  return citations.value
    .map(citationId => {
      // Busca documento nos resultados vetoriais (case-insensitive)
      const doc = vectorResults.value.find(
        result => result.id.toLowerCase() === citationId.toLowerCase()
      )
      
      if (!doc) {
        return {
          id: citationId,
          title: 'Documento não encontrado',
          notFound: true
        }
      }
      
      // Retorna documento enriquecido com TODOS os metadados
      return {
        id: doc.id,
        title: doc.title || 'Documento Jurídico',
        case_number: doc.case_number,  // ⭐ Número do processo
        relator: doc.relator,          // ⭐ Ministro relator
        source: doc.source,            // ⭐ Tribunal (STF, STJ)
        date: doc.date,
        court: doc.court,
        article: doc.article,
        text: doc.text,
        score: doc.score,              // ⭐ Relevância (0-1)
        notFound: false
      }
    })
    .filter(doc => !doc.notFound)  // Remove não encontrados
})
```

---

## 📑 Metadados Jurídicos

### Origem dos Dados

Os metadados jurídicos são extraídos dos arquivos **JSONL** gerados pelos scrapers (STF, STJ, TRF4):

```json
{
  "cluster_name": "art_244",
  "cluster_description": "abandono material artigo 244 (art. 244 do Código Penal)",
  "article_reference": "CP art. 244",
  "source": "STF - art_244",
  "title": "HC 187657",
  "case_number": "despacho1123501",
  "content": "HC 187657 / GO - GOIÁS...",
  "url": "https://jurisprudencia.stf.jus.br/pages/search/despacho1123501/false",
  "tribunal": "STF",
  "legal_area": "Penal",
  "classe_processual_unificada": null,
  "relator": "CÁRMEN LÚCIA",
  "publication_date": "05/08/2020",
  "decision_date": "27/07/2020",
  "numero_unico": "0096679-75.2020.1.00.0000"
}
```

### Mapeamento de Campos

| Campo JSONL | Campo API | Descrição | Exemplo |
|-------------|-----------|-----------|---------|
| `case_number` | `case_number` | ID do caso/despacho | `despacho1123501` |
| `relator` | `relator` | Ministro/Desembargador | `CÁRMEN LÚCIA` |
| `source` | `source` | Tribunal + cluster | `STF - art_244` |
| `numero_unico` | `meta.numero_unico` | CNJ | `0096679-75.2020.1.00.0000` |
| `publication_date` | `date` | Data de publicação | `05/08/2020` |
| `title` | `title` | Tipo + número | `HC 187657` |
| `tribunal` | `court` | Tribunal | `STF` |
| `content` | `text` | Texto completo | `HC 187657 / GO - GOIÁS...` |

### Fluxo de Metadados

```
┌─────────────────────┐
│ Scraper (STF, STJ)  │
│ - Coleta decisões   │
│ - Extrai metadados  │
└──────────┬──────────┘
           │ JSONL
           ↓
┌─────────────────────┐
│ Tratamento de Dados │
│ - Limpa HTML        │
│ - Valida campos     │
│ - Remove duplicatas │
└──────────┬──────────┘
           │ merged_clean.jsonl
           ↓
┌─────────────────────┐
│ Pipeline de Build   │
│ - Cria Doc objects  │
│ - Gera embeddings   │
│ - Indexa no FAISS   │
└──────────┬──────────┘
           │ index.faiss + metadata.parquet
           ↓
┌─────────────────────┐
│ FAISS Store         │
│ self.metadata = {   │
│   42315: {          │
│     'id': 'HC_...'  │
│     'case_number'   │
│     'relator'       │
│     'source'        │
│     ...             │
│   }                 │
│ }                   │
└──────────┬──────────┘
           │ search()
           ↓
┌─────────────────────┐
│ API Response        │
│ SearchResultAPI {   │
│   case_number ✓     │
│   relator ✓         │
│   source ✓          │
│   score ✓           │
│ }                   │
└──────────┬──────────┘
           │ HTTP JSON
           ↓
┌─────────────────────┐
│ Frontend UI         │
│ enrichedCitations   │
│ - Mapeia citações   │
│ - Exibe metadados   │
│ - Mostra score      │
└─────────────────────┘
```

---

## 📈 Interpretação de Resultados

### Tabela de Interpretação de Scores

| Score Range | Badge | Interpretação | Significado Prático |
|-------------|-------|---------------|---------------------|
| **0.85 - 1.0** | 🎯 **Alta** | Documento **altamente relevante** | Responde diretamente à query; use com confiança |
| **0.70 - 0.84** | ⚡ **Boa** | Documento **relevante** | Boa correspondência semântica; útil para resposta |
| **0.50 - 0.69** | ⚠️ **Média** | Documento **relacionado** | Contexto tangencial; verificar antes de usar |
| **0.30 - 0.49** | 🔶 **Baixa** | Documento **fracamente relacionado** | Pode gerar alucinações; evitar citar |
| **< 0.30** | ❌ **Irrelevante** | Documento **sem relação** | Não usar; sem relevância semântica |

### Exemplos Reais

#### **Query: "Explique medidas cautelares art. 319 CPP"**

| Documento | Score | Por que? |
|-----------|-------|----------|
| **HC 187657** (prisão preventiva art. 319) | **0.856** | ✅ Menciona explicitamente "art. 319 CPP", "medidas cautelares", "prisão preventiva" |
| **HC 169805** (posse de entorpecente militar) | **0.623** | ⚠️ Fala de "medidas cautelares" genéricas, mas contexto diferente (direito militar) |
| **HC 123456** (abandono material art. 244) | **0.412** | ⚠️ Tema completamente diferente, apenas conexão tangencial em "medidas" |

### Análise Semântica

#### **Alta Relevância (0.856)**
```
Query:     "medidas cautelares art. 319 CPP"
Documento: "...art. 319 do Código de Processo Penal estabelece as 
            medidas cautelares diversas da prisão preventiva, como 
            comparecimento periódico, proibição de frequentar lugares..."

Similaridade Alta porque:
✓ Termos exatos: "art. 319", "medidas cautelares"
✓ Contexto jurídico alinhado (CPP)
✓ Embeddings próximos no espaço vetorial
✓ Coseno próximo de 1.0
```

#### **Média Relevância (0.623)**
```
Query:     "medidas cautelares art. 319 CPP"
Documento: "...no Código Penal Militar, as medidas cautelares seguem 
            regime específico, conforme art. 290 do CPM..."

Similaridade Média porque:
✓ Termo comum: "medidas cautelares"
✗ Contexto diferente: militar vs. comum
✗ Artigo diferente: 290 vs. 319
~ Embeddings relativamente próximos
~ Coseno ~0.6
```

#### **Baixa Relevância (0.412)**
```
Query:     "medidas cautelares art. 319 CPP"
Documento: "...crime de abandono material, previsto no art. 244 do 
            Código Penal, não comporta prisão preventiva..."

Similaridade Baixa porque:
~ Termos relacionados: "prisão", "Código Penal"
✗ Tema completamente diferente
✗ Sem menção a medidas cautelares
✗ Embeddings distantes
✗ Coseno ~0.4
```

### Métricas Agregadas

O sistema também calcula métricas agregadas para avaliar a qualidade da busca:

```typescript
// Calculado no frontend (index.vue)
const scores = searchResponse.results.map(r => r.score || 0)
const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length
const topScore = Math.max(...scores)

// Exemplo:
// scores = [0.856, 0.782, 0.654, 0.589, 0.512]
// avgScore = 0.679  → Qualidade MÉDIA da busca
// topScore = 0.856  → Melhor resultado
```

#### **Avaliação de Qualidade da Busca**

| Avg Score | Top Score | Avaliação | Ação Recomendada |
|-----------|-----------|-----------|------------------|
| **≥ 0.70** | **≥ 0.85** | 🎯 **Excelente** | Resposta confiável; alta cobertura |
| **0.50-0.69** | **0.70-0.84** | ⚡ **Boa** | Resposta útil; cobertura média |
| **0.30-0.49** | **0.50-0.69** | ⚠️ **Fraca** | Verificar contexto; sugerir refinamento |
| **< 0.30** | **< 0.50** | ❌ **Inadequada** | Reformular query; documentos irrelevantes |

### Coverage Level (G2 Answer Composer)

O **G2** usa os scores implicitamente para determinar o nível de cobertura:

```typescript
// Lógica simplificada
if (avgScore >= 0.70 && citations.length >= 2) {
  coverage = 'high'      // 🎯 Alta cobertura
} else if (avgScore >= 0.50 && citations.length >= 1) {
  coverage = 'medium'    // ⚡ Média cobertura
} else if (avgScore >= 0.30) {
  coverage = 'low'       // ⚠️ Baixa cobertura (gera sugestões)
} else {
  coverage = 'none'      // ❌ Sem cobertura (rejeita resposta)
}
```

---

## ⚡ Otimizações e Performance

### Índice FAISS

#### **IndexFlatIP vs. IndexIVFFlat**

```python
# Atual: IndexFlatIP (busca exaustiva)
base_index = faiss.IndexFlatIP(768)
# - Busca em todos os N documentos
# - Complexidade: O(N × D) onde D=768
# - Preciso mas lento para N > 100k

# Alternativa: IndexIVFFlat (com clustering)
quantizer = faiss.IndexFlatIP(768)
index = faiss.IndexIVFFlat(quantizer, 768, n_clusters=100)
# - Divide em clusters (Voronoi cells)
# - Busca apenas em clusters próximos
# - Complexidade: O(k × D) onde k << N
# - Mais rápido, pequena perda de precisão
```

#### **GPU Acceleration**

```python
# Configurável via environment variable
USE_FAISS_GPU = True
FAISS_GPU_DEVICE = 0

def maybe_to_gpu(index):
    if USE_FAISS_GPU and faiss.StandardGpuResources:
        res = faiss.StandardGpuResources()
        gpu_index = faiss.index_cpu_to_gpu(res, FAISS_GPU_DEVICE, index)
        # Speedup: ~10-50x dependendo do hardware
        return gpu_index
    return index
```

### Embedding Model

#### **Modelo Atual**
```
paraphrase-multilingual-MiniLM-L12-v2
- Dimensões: 768
- Parâmetros: ~22M
- Velocidade: ~1000 sentenças/s (CPU)
- Linguagens: 50+ (incluindo português)
- Tamanho: ~420MB
```

#### **Alternativas**

| Modelo | Dimensões | Velocidade | Qualidade | Uso Recomendado |
|--------|-----------|------------|-----------|-----------------|
| `all-MiniLM-L6-v2` | 384 | ⚡⚡⚡ Rápido | ⭐⭐⭐ Bom | Produção (inglês) |
| `paraphrase-multilingual-MiniLM-L12-v2` | 768 | ⚡⚡ Médio | ⭐⭐⭐⭐ Ótimo | **Atual** (multilingual) |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | ⚡ Lento | ⭐⭐⭐⭐⭐ Excelente | Alta precisão |
| `LaBSE` | 768 | ⚡ Lento | ⭐⭐⭐⭐⭐ Excelente | Cross-lingual |

### Caching

```python
# Implementação futura
from functools import lru_cache

@lru_cache(maxsize=1000)
def encode_single_text_cached(text: str) -> np.ndarray:
    """Cacheia embeddings de queries frequentes."""
    return encoder.encode(text)

# Benefícios:
# - Queries repetidas: 0ms (cache hit)
# - Reduz carga no modelo
# - Melhora latência do G1
```

### Batch Processing

```python
# Indexação em batch (mais eficiente)
def index(self, docs: List[Doc]) -> None:
    # Processa em batches de 32
    batch_size = 32
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i+batch_size]
        texts = [doc.text for doc in batch]
        vectors = embeddings.encode_texts(texts)  # Batch encoding
        # ... adiciona ao índice
```

### Performance Benchmarks

| Operação | Latência | Throughput | Nota |
|----------|----------|------------|------|
| **Encode Query** (768D) | ~50ms | 20 queries/s | CPU (single thread) |
| **FAISS Search** (k=5, N=10k) | ~5ms | 200 searches/s | CPU (IndexFlatIP) |
| **FAISS Search** (k=5, N=10k) | ~0.5ms | 2000 searches/s | GPU (IndexFlatIP) |
| **API Roundtrip** | ~100-200ms | - | Inclui rede + serialização |
| **Pipeline RAG Total** | ~1.5-2s | - | G1 + VDB + G2 |

---

## 🔧 Troubleshooting

### Problemas Comuns

#### **1. Scores Muito Baixos (< 0.30)**

**Sintomas:**
```json
{
  "results": [
    { "id": "doc1", "score": 0.234 },
    { "id": "doc2", "score": 0.198 },
    { "id": "doc3", "score": 0.176 }
  ]
}
```

**Causas:**
- Query muito genérica ou ambígua
- Documentos no banco não cobrem o tema
- Embeddings não normalizados
- Modelo de embedding inadequado

**Soluções:**
```bash
# 1. Refinar query com G1 Query Builder
optimize = true

# 2. Adicionar mais documentos ao banco
make scrape-stf QUERY="art. 319"
make faiss-build

# 3. Verificar normalização dos embeddings
# embeddings.py: 
# encoder.encode(..., normalize_embeddings=True)

# 4. Testar modelo alternativo
EMBEDDING_MODEL="paraphrase-multilingual-mpnet-base-v2"
```

#### **2. Resultados Inconsistentes (Variação de Scores)**

**Sintomas:**
- Mesma query retorna scores diferentes em buscas consecutivas
- Ordem dos resultados muda

**Causas:**
- Índice FAISS não determinístico (IVF com `nprobe < nclusters`)
- Embeddings não reproduzíveis (seed não fixado)

**Soluções:**
```python
# 1. Usar IndexFlat (determinístico)
base_index = faiss.IndexFlatIP(768)  # ✓ Sempre mesmo resultado

# 2. Fixar seed do modelo
import torch
torch.manual_seed(42)
np.random.seed(42)

# 3. Aumentar nprobe (se usar IVF)
index.nprobe = 10  # Busca em mais clusters
```

#### **3. Erro "Store não inicializado"**

**Sintomas:**
```
HTTPException 503: Store não inicializado
```

**Causas:**
- FAISS index não existe em `data/indexes/faiss/index.faiss`
- Metadados corrompidos

**Soluções:**
```bash
# 1. Verificar arquivos
ls -lh DBVECTOR/data/indexes/faiss/
# Deve ter: index.faiss + metadata.parquet

# 2. Recriar índice
cd DBVECTOR
make faiss-build

# 3. Verificar logs da API
make api
# Procure por: "✅ Índice carregado! N documentos"
```

#### **4. Metadados Ausentes (case_number, relator, source = null)**

**Sintomas:**
```json
{
  "id": "HC_187657",
  "case_number": null,
  "relator": null,
  "source": null
}
```

**Causas:**
- Campos não estão no JSONL original
- Pipeline de build não extrai metadados
- Índice criado antes da atualização

**Soluções:**
```bash
# 1. Verificar JSONL
head -n 1 stf_scraper/data/stf_jurisprudencia/art_244/*.jsonl | jq .
# Deve ter: case_number, relator, source

# 2. Re-indexar documentos
cd DBVECTOR
rm -rf data/indexes/faiss/*
make faiss-build  # Recria índice com metadados

# 3. Validar na API
curl http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"q": "art. 319", "k": 1}' | jq '.results[0]'
```

#### **5. Latência Alta (> 2.5s)**

**Sintomas:**
- Pipeline RAG demorando > 2.5s
- Timeout errors

**Causas:**
- Modelo de embedding lento (CPU)
- Índice FAISS muito grande sem otimização
- G1/G2 esperando resposta do GPT

**Soluções:**
```bash
# 1. Habilitar GPU FAISS
export USE_FAISS_GPU=true
export FAISS_GPU_DEVICE=0

# 2. Usar modelo mais rápido
export EMBEDDING_MODEL="all-MiniLM-L6-v2"

# 3. Reduzir k (menos documentos)
k=3  # ao invés de 5

# 4. Otimizar prompts G1/G2
# - Reduzir max_tokens
# - Usar temperature=0 (mais rápido)
```

### Debug Mode

#### **Habilitar Logging Detalhado**

```python
# DBVECTOR/src/config.py
LOGLEVEL = "DEBUG"

# Ou via environment variable
export LOGLEVEL=DEBUG
make api
```

#### **Inspecionar Embeddings**

```python
# Scripts de debug
from src import embeddings

# Testar embedding
query = "art. 319 CPP"
vector = embeddings.encode_single_text(query)
print(f"Shape: {vector.shape}")           # (768,)
print(f"Norm: {np.linalg.norm(vector)}")  # ~1.0 (normalizado)
print(f"Sample: {vector[:10]}")           # Primeiros 10 valores
```

#### **Validar Índice FAISS**

```python
from src.storage.factory import get_faiss_store

store = get_faiss_store()
print(f"Documentos: {store.get_doc_count()}")
print(f"Metadados: {len(store.metadata)}")

# Busca teste
query_vector = embeddings.encode_single_text("teste")
results = store.search(query_vector, k=1)
print(results[0].doc.id, results[0].score)
```

---

## 📚 Referências Técnicas

### Artigos e Documentação

1. **FAISS - Facebook AI Similarity Search**
   - Paper: [Efficient Similarity Search and Clustering of Dense Vectors](https://arxiv.org/abs/1702.08734)
   - Docs: https://faiss.ai/

2. **Sentence-Transformers**
   - Paper: [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084)
   - Docs: https://www.sbert.net/

3. **Cosine Similarity & Inner Product**
   - [Understanding Cosine Similarity](https://en.wikipedia.org/wiki/Cosine_similarity)
   - [Dot Product vs Cosine Similarity](https://stackoverflow.com/questions/18424228/cosine-similarity-versus-dot-product-as-distance-metrics)

### Modelos de Embedding Recomendados

| Modelo | HuggingFace ID | Melhor para |
|--------|----------------|-------------|
| Atual (multilingual) | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Português + multilingual |
| Alta qualidade PT/EN | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | Produção (precisão) |
| Rápido (apenas EN) | `sentence-transformers/all-MiniLM-L6-v2` | Prototipagem rápida |
| Cross-lingual | `sentence-transformers/LaBSE` | Queries em múltiplos idiomas |

### Ferramentas Úteis

- **FAISS Benchmarks**: https://github.com/facebookresearch/faiss/wiki/Indexing-1G-vectors
- **Embedding Explorer**: https://projector.tensorflow.org/
- **Vector DB Comparison**: https://benchmark.vectorview.ai/

---

## 🎓 Conceitos Avançados

### Por que Produto Interno ≈ Cosseno?

```python
# Vetores normalizados (norma L2 = 1)
||a|| = 1
||b|| = 1

# Produto interno:
dot(a, b) = Σ(a[i] × b[i])

# Cosseno:
cos(θ) = dot(a, b) / (||a|| × ||b||)
       = dot(a, b) / (1 × 1)
       = dot(a, b)

# Portanto: Para vetores normalizados, dot = cos
```

### Espaço Vetorial de Embeddings

```
      a (query)
       ↑ 
     θ | \
       |  \ b (doc relevante, θ pequeno, cos alto)
       |   \
       |    \
       |     \
──────┼──────●─────────→ (eixo 1)
       |      \
       |       \ c (doc irrelevante, θ grande, cos baixo)
       |        \
      ↓          ●
```

### Trade-offs de Precisão vs. Velocidade

```
IndexFlat          ─────────●───────────────► 
(Atual)            Lento                  Preciso

IndexIVFFlat       ────────────●──────────►
                   Médio             Bom

IndexIVFPQ         ──────●──────────────────►
(Comprimido)       Rápido        Aproximado
```

---

## 📊 Métricas de Monitoramento

### KPIs Recomendados

| Métrica | Target | Alerta | Crítico |
|---------|--------|--------|---------|
| **Avg Score** | > 0.70 | < 0.50 | < 0.30 |
| **Top Score** | > 0.85 | < 0.70 | < 0.50 |
| **VDB Latency** | < 100ms | > 400ms | > 1000ms |
| **Documents Found** | ≥ 3 | < 3 | 0 |
| **Pipeline Total** | < 2s | > 2.5s | > 5s |

### RAG Ops Logger Integration

```typescript
// Já implementado em useRagLogger.ts
const logEntry = {
  vdb: {
    avg_score: avgScore,  // ⭐ Monitora qualidade
    top_score: topScore,  // ⭐ Melhor resultado
    latency_ms: vdbLatency
  }
}

// Validações automáticas
if (avgScore < 0.50) {
  status = 'WARN'  // ⚠️ Alerta de qualidade baixa
}
```

---

## 🚀 Próximos Passos

### Melhorias Planejadas

1. **Hybrid Search** (BM25 + Vector)
   ```python
   # Combinar busca lexical + semântica
   bm25_results = bm25_search(query, k=10)
   vector_results = faiss_search(query_vector, k=10)
   combined = rerank(bm25_results, vector_results, weights=[0.3, 0.7])
   ```

2. **Reranking com Cross-Encoder**
   ```python
   # Reordena top-k com modelo mais preciso
   initial = faiss_search(query_vector, k=20)
   reranked = cross_encoder.rank(query, [r.text for r in initial])
   final = reranked[:5]  # Top-5 rerankeados
   ```

3. **Clustering Dinâmico**
   ```python
   # Agrupa documentos similares
   kmeans = faiss.Kmeans(768, n_clusters=50)
   kmeans.train(all_vectors)
   # Permite busca por cluster
   ```

4. **A/B Testing de Modelos**
   ```python
   # Compara modelos de embedding
   models = ['MiniLM', 'MPNet', 'LaBSE']
   for model in models:
       scores = evaluate(model, test_queries)
       print(f"{model}: avg_score={scores.mean()}")
   ```

---

**Projeto**: RAG-TCC  
**Instituição**: LabTechUDF  
**Branch**: release/MVP  
**Versão**: 1.0.0  
**Autor**: Sistema RAG Jurídico  
**Data**: 2025-01-05

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique logs: `DBVECTOR/logs/` e console do navegador
2. Valide índice: `make faiss-inspect`
3. Re-indexe se necessário: `make faiss-build`
4. Consulte documentação RAG: `RAG_PIPELINE_FINAL.md`

🎉 **Sistema de Relevância Vetorial Totalmente Documentado!**
