# GPT-5 Answer Composer - Documentação

## 📋 Visão Geral

O **GPT-5 Answer Composer** é o componente final do pipeline RAG que monta respostas fundamentadas com **citações** baseadas nos documentos recuperados do banco vetorial.

## 🏗️ Pipeline RAG Completo

```
[Usuário: Query Original]
        ↓
[G1: Query Builder] → Query Otimizada
        ↓
[DBVECTOR: Vector Search] → Top-K Documentos
        ↓
[G2: Answer Composer] → Resposta com Citações
        ↓
[Usuário: Resposta Final]
```

## 🔧 Componente: `useAnswerComposer.ts`

### Interface de Entrada

```typescript
interface RetrievedDocument {
  doc_id: string          // ID único do documento
  title?: string          // Título (artigo, ementa, etc)
  score: number          // Score de similaridade (0-1)
  snippet: string        // Texto relevante do documento
  source_url?: string    // URL da fonte (opcional)
  date?: string          // Data do documento (opcional)
  article?: string       // Artigo de lei (opcional)
  court?: string         // Tribunal (opcional)
}

interface AnswerComposerInput {
  user_prompt: string              // Pergunta do usuário
  recent_history?: string          // Histórico de conversação
  retrieved: RetrievedDocument[]   // Documentos recuperados
}
```

### Interface de Saída

```typescript
interface AnswerComposerOutput {
  answer: string                   // Resposta final com citações
  citations_used: string[]         // IDs citados na resposta
  coverage_level: 'high' | 'medium' | 'low' | 'none'  // Nível de cobertura
  suggestions?: string[]           // Sugestões se cobertura baixa
}
```

## 📝 Regras do Answer Composer

### 1. Uso Exclusivo de Contexto
- **Apenas** informações de `retrieved` podem ser usadas para afirmações factuais
- Se algo essencial não estiver coberto, **explicitar** o que falta
- **Nunca inventar** informações não presentes no contexto

### 2. Sistema de Citações
- Citar fontes usando `[doc_id]` ao final da frase
- Exemplo: `"A prisão preventiva requer fundamentação [STJ_2021_AgInt_12345]."`
- Usar **múltiplas citações** quando necessário
- Formato: `[doc_id]` entre colchetes

### 3. Conflitos entre Documentos
- Preferir documentos com **maior score**
- Preferir documentos **mais recentes** (se `date` disponível)
- Explicar conflitos em uma frase quando relevante

### 4. Formatação da Resposta
- Parágrafos curtos e objetivos
- Listas quando apropriado
- Linguagem técnica mas acessível
- **Não expor** raciocínio interno passo a passo

### 5. Idioma
- Responder no **mesmo idioma** do `user_prompt`

### 6. Síntese vs. Cópia
- **Parafrasear e sintetizar** (não copiar trechos longos)
- Extrair essência dos documentos

## 🎯 Níveis de Cobertura

### High (Alta) 🎯
- **3+ documentos** recuperados
- Score médio **≥ 0.7**
- Contexto suficiente para resposta completa

### Medium (Média) ⚡
- **2+ documentos** recuperados
- Score médio **≥ 0.5**
- Contexto parcial, resposta possível

### Low (Baixa) ⚠️
- **1 documento** recuperado
- Contexto limitado
- **Sugestões** para melhorar busca

### None (Nenhuma) ❌
- **0 documentos** ou irrelevantes
- **Sugestões obrigatórias** para nova busca

## 🔍 Comportamento em Cobertura Baixa

Quando `coverage_level` é `low` ou `none`, o Answer Composer:

1. Fornece um **resumo do que precisa** para responder melhor
2. Gera **3 sugestões objetivas** de refinamento
3. Ainda tenta responder com o que está disponível (se houver)

### Exemplo de Sugestões
```
💡 Sugestões para melhorar a busca:
- Especifique o artigo de lei (ex.: art. 312 CPP)
- Indique o período temporal desejado
- Inclua o tribunal de interesse (STF, STJ, etc)
```

## 📊 Exemplo Completo

### Entrada
```javascript
const input = {
  user_prompt: "Quais são os requisitos para prisão preventiva?",
  recent_history: "",
  retrieved: [
    {
      doc_id: "STJ_2021_AgInt_12345",
      title: "AgInt no REsp 12345/DF",
      score: 0.83,
      snippet: "A prisão preventiva exige fundamentação concreta dos requisitos do art. 312 do CPP...",
      date: "2021-04-12",
      article: "art. 312"
    },
    {
      doc_id: "STF_2022_HC_67890",
      title: "HC 67890/SP",
      score: 0.76,
      snippet: "Para decretação da preventiva, necessária demonstração do periculum libertatis...",
      date: "2022-06-15",
      article: "art. 312"
    }
  ]
}
```

### Saída
```javascript
{
  answer: "A prisão preventiva requer fundamentação concreta dos requisitos estabelecidos no art. 312 do CPP [STJ_2021_AgInt_12345]. É necessária a demonstração do periculum libertatis, ou seja, do perigo concreto que a liberdade do acusado representa para a ordem pública, econômica, instrução criminal ou aplicação da lei penal [STF_2022_HC_67890]. A mera alegação genérica não é suficiente, sendo imprescindível a fundamentação específica das circunstâncias do caso concreto.",
  
  citations_used: [
    "STJ_2021_AgInt_12345",
    "STF_2022_HC_67890"
  ],
  
  coverage_level: "high",
  
  suggestions: undefined
}
```

### Exibição na UI
```
🎯 Alta Cobertura | 📚 2 citações

A prisão preventiva requer fundamentação concreta dos requisitos 
estabelecidos no art. 312 do CPP [STJ_2021_AgInt_12345]. É necessária 
a demonstração do periculum libertatis, ou seja, do perigo concreto 
que a liberdade do acusado representa para a ordem pública, econômica, 
instrução criminal ou aplicação da lei penal [STF_2022_HC_67890]. 
A mera alegação genérica não é suficiente, sendo imprescindível a 
fundamentação específica das circunstâncias do caso concreto.

📖 Fontes Citadas:
[STJ_2021_AgInt_12345] [STF_2022_HC_67890]
```

## 🎨 Componentes UI

### 1. Coverage Badge
```vue
<UBadge 
  :color="coverageLevel === 'high' ? 'green' : 
          coverageLevel === 'medium' ? 'yellow' : 
          coverageLevel === 'low' ? 'orange' : 'red'"
  variant="subtle"
>
  {{ coverageLevel === 'high' ? '🎯 Alta Cobertura' : '...' }}
</UBadge>
```

### 2. Citations Counter
```vue
<UBadge color="blue" variant="subtle">
  📚 {{ citations.length }} citações
</UBadge>
```

### 3. Citations List
```vue
<div class="citations-box">
  <div>📖 Fontes Citadas:</div>
  <UBadge v-for="citation in citations" :key="citation">
    [{{ citation }}]
  </UBadge>
</div>
```

### 4. Suggestions Box
```vue
<div v-if="suggestions.length > 0" class="suggestions-box">
  <div>💡 Sugestões para melhorar a busca:</div>
  <ul>
    <li v-for="suggestion in suggestions">{{ suggestion }}</li>
  </ul>
</div>
```

## 🔄 Fluxo de Integração

### 1. No Composable
```typescript
const { composeAnswer, convertToRetrievedDocuments } = useAnswerComposer()

// Após vector search
const retrievedDocs = convertToRetrievedDocuments(searchResults)

// Gerar resposta
const answer = await composeAnswer({
  user_prompt: userQuery,
  recent_history: recentHistory,
  retrieved: retrievedDocs
})
```

### 2. Na Interface
```typescript
// Estado
const citations = ref<string[]>([])
const coverageLevel = ref<'high' | 'medium' | 'low' | 'none'>('none')
const suggestions = ref<string[]>([])

// Após composição
citations.value = answer.citations_used
coverageLevel.value = answer.coverage_level
suggestions.value = answer.suggestions || []
```

## 📈 Performance

### Métricas Típicas
- **Composição**: ~800-1200ms (GPT-4o-mini)
- **Pipeline RAG completo**:
  - Query Builder: ~500ms
  - Vector Search: ~100-200ms
  - Answer Composer: ~800-1200ms
  - **Total**: ~1.5-2s

### Otimizações
- Modelo: `gpt-4o-mini` (rápido e eficiente)
- Temperature: `0.3` (mais factual)
- Max Tokens: `1000` (respostas completas mas concisas)

## 🧪 Casos de Teste

### Teste 1: Alta Cobertura
```javascript
// 5 documentos relevantes, scores > 0.7
// Espera: resposta completa com múltiplas citações
```

### Teste 2: Cobertura Média
```javascript
// 2-3 documentos, scores 0.5-0.7
// Espera: resposta boa mas não exaustiva
```

### Teste 3: Baixa Cobertura
```javascript
// 1 documento, score < 0.5
// Espera: resposta parcial + 3 sugestões
```

### Teste 4: Sem Cobertura
```javascript
// 0 documentos ou irrelevantes
// Espera: explicação + 3 sugestões obrigatórias
```

### Teste 5: Conflito entre Documentos
```javascript
// Documentos com informações conflitantes
// Espera: preferir mais recente/maior score + explicar conflito
```

## 🐛 Troubleshooting

### Problema: Citações não aparecem
**Causa**: Formato incorreto ou GPT não seguiu instruções
**Solução**: Verificar `extractCitations()` e prompt do sistema

### Problema: Coverage sempre "none"
**Causa**: Threshold muito alto em `assessCoverage()`
**Solução**: Ajustar limites de score/quantidade

### Problema: Resposta inventa informações
**Causa**: Temperature muito alta ou prompt inadequado
**Solução**: Reduzir temperature, reforçar instruções no prompt

### Problema: Sugestões não são geradas
**Causa**: Pattern regex não encontra sugestões na resposta
**Solução**: Verificar `extractSuggestions()` e formato da resposta do GPT

## 📚 Referências

- [Query Builder](./QUERY_BUILDER.md) - G1 do pipeline
- [Vector Search](./app/composables/useVectorSearch.ts) - Busca no DBVECTOR
- [Answer Composer Code](./app/composables/useAnswerComposer.ts) - Implementação

## 🔐 Melhores Práticas

### 1. Histórico de Conversação
- Incluir últimas 2-3 mensagens quando disponível
- Formato: texto plano concatenado

### 2. Tamanho de Snippets
- Manter entre 200-400 caracteres
- Suficiente para contexto, não excessivo

### 3. Número de Documentos
- Ideal: 3-7 documentos (top-k)
- Muito poucos: cobertura baixa
- Muitos demais: prompt muito longo

### 4. Ordenação
- Ordenar por score descendente antes de enviar
- Documentos mais relevantes primeiro

### 5. Metadados
- Incluir `date` quando disponível (para resolver conflitos)
- Incluir `article`, `court` para contexto adicional

---

**Versão**: 1.0.0  
**Data**: 2025-01-05  
**Status**: ✅ Implementado e integrado
