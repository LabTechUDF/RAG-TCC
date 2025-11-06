# RAG Ops Logger - Documentação

## 📋 Visão Geral

O **RAG Ops Logger** é um sistema de logging estruturado que monitora e valida o pipeline RAG completo (G1 → DBVECTOR → G2), gerando logs legíveis e NDJSON para análise operacional.

## 🎯 Objetivo

Permitir verificação rápida se o pipeline executou corretamente através de:
- ✅ Status resumido (OK/WARN/ERROR)
- 📊 Métricas detalhadas de cada componente
- ⚡ Validações automáticas com checks
- 📝 Formato dual: legível + JSON

## 🏗️ Arquitetura do Log

### Estrutura de Dados

```typescript
interface RAGLogEntry {
  request_id: string           // Identificador único
  timestamp: string            // ISO 8601
  user_query: string           // Query original
  lang: string                 // Idioma (ex: "pt-BR")
  
  g1: {
    model: string              // "gpt-4o-mini"
    optimized_query: string    // Query otimizada
    tokens_count: number       // Número de tokens
    used_clusters: string[]    // Clusters utilizados
    latency_ms: number         // Latência em ms
  }
  
  vdb: {
    backend: string            // "faiss"|"opensearch"|"hybrid"
    k: number                  // Top-K solicitado
    total: number              // Documentos encontrados
    avg_score: number          // Score médio (0-1)
    top_score: number          // Score máximo (0-1)
    doc_ids: string[]          // IDs dos documentos
    latency_ms: number         // Latência em ms
  }
  
  g2: {
    model: string              // "gpt-4o-mini"
    coverage: string           // "high"|"medium"|"low"|"none"
    citations_used: string[]   // IDs citados
    suggestions_count: number  // Número de sugestões
    answer_chars: number       // Tamanho da resposta
    latency_ms: number         // Latência em ms
  }
  
  pipeline_total_ms: number    // Latência total
  error?: string               // Mensagem de erro (opcional)
}
```

## 📏 Regras de Avaliação

### Status: OK ✅

Todos os critérios devem ser atendidos:
- `optimized_query` não vazia
- `tokens_count` entre 6-20
- `used_clusters.length` ≤ 3
- `vdb.total` ≥ 1
- `vdb.avg_score` ≥ 0.50
- `coverage` é "high" ou "medium"
- `citations_used.length` ≥ 1
- `error` vazio

### Status: WARN ⚠️

Qualquer condição abaixo (sem ser ERROR):
- `tokens_count` < 6 ou > 20
- `vdb.avg_score` < 0.50
- `coverage` = "low"
- `citations_used.length` = 0 com `vdb.total` ≥ 1
- `suggestions_count` > 0
- Latências:
  - `g1.latency_ms` > 800ms
  - `vdb.latency_ms` > 400ms
  - `g2.latency_ms` > 1500ms
  - `pipeline_total_ms` > 2500ms

### Status: ERROR ❌

Qualquer condição abaixo:
- `error` não vazio
- `vdb.total` = 0
- `optimized_query` vazio
- `citations_used` contém IDs não presentes em `vdb.doc_ids`
- `answer_chars` = 0

## 📊 Formato de Saída

### Parte 1: Log Legível (Multiline)

```
RAG ▶︎ request_id=req_1234567890_abc123 │ 2025-01-05T10:30:45.123Z │ lang=pt-BR
• STATUS: OK
• G1  QueryBuilder
  - model=gpt-4o-mini │ tokens=8 │ clusters=["art. 312"]
  - query="prisão preventiva art. 312 requisitos decreto garantia ordem pública"
  - latency=456ms
• VDB VectorSearch
  - backend=faiss │ k=5 │ total=5
  - avg_score=0.782 │ top_score=0.856
  - doc_ids=["STJ_2021_12345","STF_2022_67890",...]
  - latency=128ms
• G2  AnswerComposer
  - model=gpt-4o-mini │ coverage=high │ citations=["STJ_2021_12345","STF_2022_67890"]
  - suggestions=0 │ answer_chars=423
  - latency=987ms
• CHECKS:
  ✅ G1: tokens [ok] (8 ∈ 6–20)
  ✅ G1: clusters [ok] (1 ≤ 3)
  ✅ G1: latency [ok] (456ms ≤ 800ms)
  ✅ VDB: docs [ok] (5 ≥ 1)
  ✅ VDB: avg_score [ok] (0.782 ≥ 0.50)
  ✅ VDB: latency [ok] (128ms ≤ 400ms)
  ✅ G2: coverage [ok] (high)
  ✅ G2: citations [ok] (2 ≥ 1)
  ✅ G2: latency [ok] (987ms ≤ 1500ms)
  ✅ PIPELINE: total [ok] (1571ms ≤ 2500ms)
• ERROR: -
• TOTAL: 1571ms
```

### Parte 2: JSON (NDJSON - última linha)

```json
{"request_id":"req_1234567890_abc123","timestamp":"2025-01-05T10:30:45.123Z","status":"OK","lang":"pt-BR","user_query":"Quais são os requisitos para prisão preventiva?","g1":{"model":"gpt-4o-mini","optimized_query":"prisão preventiva art. 312 requisitos decreto garantia ordem pública","tokens_count":8,"used_clusters":["art. 312"],"latency_ms":456},"vdb":{"backend":"faiss","k":5,"total":5,"avg_score":0.782,"top_score":0.856,"doc_ids":["STJ_2021_12345","STF_2022_67890","STJ_2020_11111","STF_2021_22222","STJ_2019_33333"],"latency_ms":128},"g2":{"model":"gpt-4o-mini","coverage":"high","citations_used":["STJ_2021_12345","STF_2022_67890"],"suggestions_count":0,"answer_chars":423,"latency_ms":987},"latency_total_ms":1571,"checks":["OK:G1:tokens [ok] (8 ∈ 6–20)","OK:G1:clusters [ok] (1 ≤ 3)","OK:G1:latency [ok] (456ms ≤ 800ms)","OK:VDB:docs [ok] (5 ≥ 1)","OK:VDB:avg_score [ok] (0.782 ≥ 0.50)","OK:VDB:latency [ok] (128ms ≤ 400ms)","OK:G2:coverage [ok] (high)","OK:G2:citations [ok] (2 ≥ 1)","OK:G2:latency [ok] (987ms ≤ 1500ms)","OK:PIPELINE:total [ok] (1571ms ≤ 2500ms)"],"error":""}
```

## 🔧 Uso

### 1. Importar Composable

```typescript
import { useRagLogger } from '~/composables/useRagLogger'

const { generateRequestId, logToConsole, generateLog } = useRagLogger()
```

### 2. No Pipeline RAG

```typescript
async function sendToRAG(query: string) {
  const requestId = generateRequestId()
  const pipelineStart = Date.now()
  
  try {
    // G1: Query Builder
    const g1Start = Date.now()
    const optimized = await optimizeQuery({ user_query: query })
    const g1End = Date.now()
    
    // VDB: Vector Search
    const vdbStart = Date.now()
    const searchResults = await vectorSearch(optimized.optimized_query, { k: 5 })
    const vdbEnd = Date.now()
    
    // G2: Answer Composer
    const g2Start = Date.now()
    const answer = await composeAnswer({
      user_prompt: query,
      retrieved: convertToRetrievedDocuments(searchResults.results)
    })
    const g2End = Date.now()
    
    const pipelineEnd = Date.now()
    
    // Montar log entry
    const logEntry: RAGLogEntry = {
      request_id: requestId,
      timestamp: new Date().toISOString(),
      user_query: query,
      lang: 'pt-BR',
      g1: {
        model: 'gpt-4o-mini',
        optimized_query: optimized.optimized_query,
        tokens_count: optimized.tokens_count,
        used_clusters: optimized.used_clusters,
        latency_ms: g1End - g1Start
      },
      vdb: {
        backend: 'faiss',
        k: 5,
        total: searchResults.total,
        avg_score: calculateAvgScore(searchResults.results),
        top_score: calculateTopScore(searchResults.results),
        doc_ids: searchResults.results.map(r => r.id),
        latency_ms: vdbEnd - vdbStart
      },
      g2: {
        model: 'gpt-4o-mini',
        coverage: answer.coverage_level,
        citations_used: answer.citations_used,
        suggestions_count: answer.suggestions?.length || 0,
        answer_chars: answer.answer.length,
        latency_ms: g2End - g2Start
      },
      pipeline_total_ms: pipelineEnd - pipelineStart,
      error: ''
    }
    
    // Log para console
    logToConsole(logEntry)
    
  } catch (error) {
    // Log de erro
    // ...
  }
}
```

### 3. Visualização no Console

```javascript
// Logs aparecem automaticamente no console do navegador (F12)
// - console.log() para OK
// - console.warn() para WARN
// - console.error() para ERROR
```

### 4. Exportar Logs

```typescript
// Para arquivo ou endpoint
const logString = generateLog(logEntry)

// Enviar para backend de logging
await $fetch('/api/logs', {
  method: 'POST',
  body: { log: logString }
})
```

## 📈 Casos de Uso

### Caso 1: Pipeline OK ✅

**Entrada**: Query válida, documentos encontrados, resposta com citações

**Log**:
```
• STATUS: OK
• CHECKS:
  ✅ Todos os checks passaram
• ERROR: -
• TOTAL: 1571ms
```

### Caso 2: Cobertura Baixa ⚠️

**Entrada**: Poucos documentos ou scores baixos

**Log**:
```
• STATUS: WARN
• VDB: avg_score=0.42 │ total=2
• G2: coverage=low │ suggestions=3
• CHECKS:
  ⚠️  VDB: avg_score [warn] (0.420 < 0.50)
  ⚠️  G2: coverage [warn] (low)
  ⚠️  G2: suggestions [warn] (3 sugestões geradas)
```

### Caso 3: Sem Documentos ❌

**Entrada**: VDB não encontrou documentos

**Log**:
```
• STATUS: ERROR
• VDB: total=0
• G2: coverage=none
• CHECKS:
  ❌ VDB: docs [error] (0 = 0)
  ❌ G2: coverage [error] (none)
• ERROR: Nenhum documento encontrado no banco vetorial
```

### Caso 4: Citações Inválidas ❌

**Entrada**: G2 citou documento inexistente

**Log**:
```
• STATUS: ERROR
• G2: citations=["DOC_FAKE_123"]
• VDB: doc_ids=["STJ_2021_12345","STF_2022_67890"]
• CHECKS:
  ❌ G2: citations [error] (IDs inválidos: DOC_FAKE_123)
• ERROR: Citations referenciam IDs não retornados pelo VDB
```

### Caso 5: Latência Alta ⚠️

**Entrada**: Pipeline lento

**Log**:
```
• STATUS: WARN
• G1: latency=1234ms
• G2: latency=2100ms
• TOTAL: 3456ms
• CHECKS:
  ⚠️  G1: latency [warn] (1234ms > 800ms)
  ⚠️  G2: latency [warn] (2100ms > 1500ms)
  ⚠️  PIPELINE: total [warn] (3456ms > 2500ms)
```

## 🎨 Visualização na UI

### Dev Mode Only (import.meta.dev)

```vue
<div v-if="lastLog && import.meta.dev" class="log-viewer">
  <div class="header">
    <span>🖥️ RAG Ops Log (dev only)</span>
    <button @click="copyLog">Copy</button>
  </div>
  <pre>{{ lastLog }}</pre>
</div>
```

### Características:
- ✅ Aparece apenas em desenvolvimento
- ✅ Terminal-style com fundo escuro
- ✅ Font monoespaçada
- ✅ Scroll horizontal/vertical
- ✅ Botão para copiar log
- ✅ Atualiza a cada execução do pipeline

## 📊 Análise de Logs

### Parsing NDJSON

```bash
# Extrair apenas JSONs (última linha de cada log)
grep '{"request_id"' logs.txt > logs.ndjson

# Análise com jq
cat logs.ndjson | jq '.status' | sort | uniq -c
#  42 "OK"
#  15 "WARN"
#   3 "ERROR"

# Latências médias
cat logs.ndjson | jq '.pipeline_total_ms' | awk '{sum+=$1; count++} END {print sum/count}'
# 1847.5

# Coverage distribution
cat logs.ndjson | jq '.g2.coverage' | sort | uniq -c
#  38 "high"
#  18 "medium"
#   4 "low"
```

### Dashboard (Exemplo com SQL)

```sql
-- Assumindo logs inseridos em banco de dados

-- Taxa de sucesso
SELECT 
  status,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM rag_logs
GROUP BY status;

-- Latências por componente
SELECT 
  AVG(g1_latency_ms) as avg_g1,
  AVG(vdb_latency_ms) as avg_vdb,
  AVG(g2_latency_ms) as avg_g2,
  AVG(pipeline_total_ms) as avg_total
FROM rag_logs
WHERE status = 'OK';

-- Documentos por coverage level
SELECT 
  g2_coverage,
  AVG(vdb_total) as avg_docs,
  AVG(vdb_avg_score) as avg_score
FROM rag_logs
GROUP BY g2_coverage
ORDER BY avg_score DESC;
```

## 🔐 Considerações de Segurança

### ⚠️ Dados Sensíveis

O logger **trunca automaticamente**:
- `user_query` > 120 chars
- `optimized_query` > 120 chars
- Todos os erros > 80 chars

### 🔒 Nunca Loga

- Conteúdo completo de snippets
- API keys ou tokens
- Dados pessoais de usuários
- IPs ou informações de rede

### 📝 Boas Práticas

```typescript
// ✅ Correto
logEntry.user_query = truncate(query, 120)

// ❌ Incorreto
logEntry.user_query = query  // Pode ser muito longo
```

## 🐛 Troubleshooting

### Problema: Logs não aparecem

**Causa**: Logger não inicializado  
**Solução**: Verificar import do composable

```typescript
const { logToConsole } = useRagLogger()
```

### Problema: Status sempre WARN

**Causa**: Thresholds muito restritivos  
**Solução**: Ajustar limites em `assessStatus()`

### Problema: Checks incorretos

**Causa**: Métricas mal capturadas  
**Solução**: Verificar timestamps e cálculos

```typescript
// Correto
const g1Start = Date.now()
await operation()
const g1End = Date.now()
const latency = g1End - g1Start

// Incorreto
const g1Start = Date.now()
const g1End = Date.now()  // Antes da operação!
await operation()
```

### Problema: JSON inválido na última linha

**Causa**: Strings não escapadas  
**Solução**: Logger já faz escape automático via `JSON.stringify()`

## 📚 Referências

- [Query Builder](./QUERY_BUILDER.md) - G1
- [Answer Composer](./ANSWER_COMPOSER.md) - G2
- [Integration Guide](./INTEGRATION.md) - Pipeline completo
- [NDJSON Format](http://ndjson.org/) - Formato de log

## 🎓 Exemplos Completos

Ver arquivo: [`examples.rag-logger.ts`](./app/composables/examples.rag-logger.ts) (a criar)

---

**Versão**: 1.0.0  
**Data**: 2025-01-05  
**Status**: ✅ Implementado
