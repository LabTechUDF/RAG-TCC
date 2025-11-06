# GPT-5 Query Builder - Integração RAG

## 📋 Visão Geral

O **GPT-5 Query Builder** é uma camada de otimização de consultas que transforma queries de usuário em strings otimizadas para busca vetorial/híbrida. Ele é executado via a interface Nuxt antes de enviar requisições ao banco vetorial DBVECTOR.

## 🏗️ Arquitetura

```
[Usuário] 
   ↓
[Interface/index.vue]
   ↓
[useQueryBuilder] → OpenAI GPT-4o-mini → Query Otimizada
   ↓
[useVectorSearch] → DBVECTOR API → Documentos Relevantes
   ↓
[GPT-4o-mini com Contexto] → Resposta Final
   ↓
[Usuário]
```

## 🔧 Componentes

### 1. `useQueryBuilder.ts` (Composable)

Responsável por otimizar queries usando GPT-4o-mini como "query builder".

**Principais Funções:**
- `optimizeQuery(input)`: Envia query para GPT e recebe versão otimizada
- `buildSimpleQuery(query, clusters)`: Fallback simples sem IA
- `buildPrompt(input)`: Constrói o prompt para o GPT

**Entrada:**
```typescript
{
  user_query: string,        // Texto livre do usuário
  recent_history?: string,   // Histórico recente de conversação
  cluster_names?: string[]   // Clusters disponíveis no banco
}
```

**Saída:**
```typescript
{
  optimized_query: string,   // Query otimizada (6-20 palavras)
  tokens_count: number,      // Número de tokens
  used_clusters: string[]    // Clusters detectados na query
}
```

### 2. `useVectorSearch.ts` (Composable)

Integração com o backend DBVECTOR (FastAPI).

**Principais Funções:**
- `search(query, options)`: Busca documentos jurídicos
- `healthCheck()`: Verifica status do DBVECTOR
- `getAvailableClusters()`: Lista clusters disponíveis

**Opções:**
```typescript
{
  k?: number,                // Número de resultados (1-20)
  optimize?: boolean,        // Usar Query Builder? (default: true)
  recent_history?: string,
  cluster_names?: string[]
}
```

### 3. `index.vue` (Interface)

Interface principal com dois modos:

1. **RAG Mode** 🔍
   - Busca vetorial com Query Builder
   - Contextualização com documentos relevantes
   - Resposta fundamentada do GPT

2. **Chat Mode** 💬
   - Chat simples direto com GPT
   - Sem busca vetorial

## 📝 Regras do Query Builder

O GPT-5 Query Builder segue estas regras obrigatórias:

1. **Saída**: Uma única linha com a string de busca
2. **Idioma**: Mesmo da `user_query`
3. **Termos prioritários**: Artigos, leis, súmulas, datas, siglas
4. **Clusters**: Usa até 3 `cluster_names` relevantes
5. **Tamanho**: 6-20 palavras (remove stopwords)
6. **Literalidade**: Não inventa identificadores
7. **Operadores**: Simples (AND/OR) apenas se suportado
8. **Ambiguidade**: Gera melhor string possível, sem perguntar
9. **Aspas**: Apenas quando absolutamente necessário

## 🚀 Setup

### 1. Configurar Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=sk-...
OPENAI_PROJECT_ID=proj_...

# DBVECTOR API Configuration
NUXT_PUBLIC_DBVECTOR_API_URL=http://localhost:8000
```

### 2. Instalar Dependências

```bash
cd Interface
pnpm install
```

### 3. Iniciar DBVECTOR (Backend)

```bash
cd DBVECTOR
make faiss-serve
# ou
make os-serve
```

### 4. Iniciar Interface (Frontend)

```bash
cd Interface
pnpm dev
```

## 📊 Exemplo de Uso

### Query Original
```
"o que é prisão preventiva"
```

### Query Otimizada (GPT-5 Query Builder)
```
"prisão preventiva art. 312 CPP requisitos jurisprudência"
```

### Resultado
- 5 documentos jurídicos relevantes encontrados
- Resposta contextualizada com citações de artigos
- Score de similaridade para cada documento

## 🔍 Clusters Disponíveis

Artigos do Código de Processo Penal:
- art. 179
- art. 205
- art. 244
- art. 312
- art. 319-A
- art. 323
- art. 325
- art. 330
- art. 345
- art. 346

## 🎯 Casos de Uso

### 1. Pesquisa Jurídica Contextualizada
```typescript
const { search } = useVectorSearch()

const results = await search(
  "Quais são as hipóteses de prisão preventiva?",
  { k: 5, optimize: true }
)
```

### 2. Query Simples (sem otimização)
```typescript
const { search } = useVectorSearch()

const results = await search(
  "art. 312",
  { k: 10, optimize: false }
)
```

### 3. Com Histórico de Conversação
```typescript
const { optimizeQuery } = useQueryBuilder()

const optimized = await optimizeQuery({
  user_query: "E sobre medidas cautelares?",
  recent_history: "Discutimos prisão preventiva art. 312",
  cluster_names: getAvailableClusters()
})
```

## 🧪 Validações

### Query Builder
- Query mínima: 2 caracteres
- Query otimizada mínima: 2 tokens
- Fallback: usa query original se otimização falhar
- Timeout: 30s (OpenAI)

### Vector Search
- k: 1-20 resultados
- Backend: FAISS ou OpenSearch
- Erro 503: DBVECTOR indisponível
- Erro 404: Nenhum documento indexado

## 📈 Performance

- **Query Builder**: ~500ms (GPT-4o-mini)
- **Vector Search**: ~100ms (FAISS) / ~200ms (OpenSearch)
- **Total (RAG)**: ~2-3s (incluindo resposta final do GPT)

## 🐛 Troubleshooting

### "Cannot connect to DBVECTOR"
```bash
# Verifique se o DBVECTOR está rodando
curl http://localhost:8000/health
```

### "No documents indexed"
```bash
cd DBVECTOR
make faiss-build  # ou make os-build
```

### "OpenAI API Error"
- Verifique `OPENAI_API_KEY` no `.env`
- Confirme saldo/créditos disponíveis
- Verifique `OPENAI_PROJECT_ID` se usando projetos

### Query otimizada muito curta
- Normal: usa query original como fallback
- Logs: `console.log` mostra query original e otimizada

## 📚 Referências

- [FastAPI DBVECTOR](../DBVECTOR/README.md)
- [Nuxt Composables](https://nuxt.com/docs/guide/directory-structure/composables)
- [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat)

## 🔐 Segurança

- ⚠️ **NUNCA** commite arquivos `.env` com chaves reais
- 🔑 API keys são expostas ao cliente (public runtime config)
- 🛡️ Use rate limiting em produção
- 🔒 Configure CORS no DBVECTOR para domínios confiáveis

## 🎨 UI/UX

### Toggle de Modos
- **RAG Mode**: Botão azul primário
- **Chat Mode**: Botão neutro outline

### Feedback Visual
- Loading: spinner + mensagem contextual
- Documentos: card azul com score de similaridade
- Resposta: formatação markdown + botão copiar

### Quick Chats
- Exemplos pré-configurados
- Clique = execução imediata
- Ícones lucide para identificação visual

---

**Versão**: 1.0.0  
**Última Atualização**: 2025-01-05
