# 🎯 RAG Pipeline - Resumo Executivo

## Visão Geral

Sistema RAG (Retrieval-Augmented Generation) completo para consultas jurídicas com **dois componentes GPT especializados**.

## 🏗️ Arquitetura

```
┌─────────────┐
│   Usuário   │
└──────┬──────┘
       │ Query Original
       ↓
┌─────────────────────────────┐
│ G1: Query Builder (GPT)     │  ← Otimiza query para busca vetorial
│ - Remove stopwords          │
│ - Adiciona termos jurídicos │
│ - Seleciona clusters        │
└──────────┬──────────────────┘
           │ Query Otimizada
           ↓
┌─────────────────────────────┐
│ DBVECTOR API (FastAPI)      │  ← Busca vetorial/híbrida
│ - FAISS / OpenSearch        │
│ - Embeddings (bge-m3)       │
│ - Top-K documentos          │
└──────────┬──────────────────┘
           │ Documentos Relevantes
           ↓
┌─────────────────────────────┐
│ G2: Answer Composer (GPT)   │  ← Gera resposta com citações
│ - Usa apenas contexto       │
│ - Cita fontes [doc_id]      │
│ - Avalia cobertura          │
└──────────┬──────────────────┘
           │ Resposta Final
           ↓
┌─────────────┐
│   Usuário   │
└─────────────┘
```

## 📦 Componentes

### G1: Query Builder (`useQueryBuilder.ts`)
**Objetivo**: Transformar query natural em query otimizada para busca vetorial

**Antes**: `"o que é prisão preventiva e quando pode ser decretada"`  
**Depois**: `"prisão preventiva art. 312 requisitos decreto garantia ordem pública"`

**Características**:
- ✅ Remove stopwords
- ✅ Prioriza termos jurídicos (artigos, leis, súmulas)
- ✅ Inclui até 3 clusters relevantes
- ✅ 6-20 palavras finais
- ✅ Mesmo idioma da query original

### G2: Answer Composer (`useAnswerComposer.ts`)
**Objetivo**: Gerar resposta fundamentada com citações baseadas nos documentos recuperados

**Entrada**: Query + Documentos recuperados  
**Saída**: Resposta com citações `[doc_id]` + Métricas de cobertura

**Características**:
- ✅ Usa **apenas** contexto fornecido (sem inventar)
- ✅ Cita fontes ao final de cada frase relevante
- ✅ Resolve conflitos (preferindo maior score/mais recente)
- ✅ Avalia cobertura (high/medium/low/none)
- ✅ Gera sugestões quando cobertura baixa

## 🎯 Resultados

### Exemplo Completo

**Input do Usuário**:
```
"Quais são os requisitos para prisão preventiva?"
```

**G1: Query Otimizada**:
```
"prisão preventiva art. 312 requisitos decreto fumus commissi delicti periculum libertatis"
```

**DBVECTOR: Documentos Encontrados**:
```
5 documentos (scores: 0.85, 0.78, 0.76, 0.71, 0.68)
- STJ_2021_AgInt_12345 (art. 312)
- STF_2022_HC_67890 (art. 312)
- ...
```

**G2: Resposta Final**:
```
A prisão preventiva exige a demonstração dos requisitos do art. 312 do CPP: 
fumus commissi delicti (indícios suficientes de autoria e materialidade) e 
periculum libertatis (perigo concreto à ordem pública, econômica, instrução 
criminal ou aplicação da lei penal) [STJ_2021_AgInt_12345].

A jurisprudência é pacífica no sentido de que a mera alegação genérica não 
é suficiente, sendo necessária fundamentação concreta das circunstâncias do 
caso [STF_2022_HC_67890]. A decisão deve ser devidamente motivada, sob pena 
de nulidade.

📖 Fontes Citadas: [STJ_2021_AgInt_12345] [STF_2022_HC_67890]
🎯 Cobertura: Alta | 📚 2 citações
```

## 📊 Performance

| Etapa | Tempo Médio | Otimização |
|-------|-------------|------------|
| G1: Query Builder | ~500ms | GPT-4o-mini, temp 0.3 |
| Vector Search | ~100-200ms | FAISS GPU ou OpenSearch |
| G2: Answer Composer | ~800-1200ms | GPT-4o-mini, temp 0.3 |
| **Total** | **~1.5-2s** | **Pipeline otimizado** |

## 🎨 Interface

### Modo RAG (Padrão)
- 🔍 Query Builder ativa
- 📚 Busca vetorial no DBVECTOR
- 📖 Resposta com citações
- 🎯 Badge de cobertura
- 💡 Sugestões se cobertura baixa

### Modo Chat (Alternativo)
- 💬 Chat direto com GPT
- Sem busca vetorial
- Sem citações
- Respostas baseadas em conhecimento geral

## 🔧 Tecnologias

### Frontend (Nuxt 3)
- **Framework**: Nuxt 3 + Vue 3
- **UI**: Nuxt UI (Tailwind CSS)
- **Language**: TypeScript
- **State**: Vue Composition API

### Backend (FastAPI)
- **Framework**: FastAPI + Uvicorn
- **Embeddings**: BGE-M3 (multilingual)
- **Vector Store**: FAISS (GPU) ou OpenSearch
- **Dimension**: 768

### AI/LLM
- **Model**: GPT-4o-mini (OpenAI)
- **Query Builder**: temp 0.3, max_tokens 100
- **Answer Composer**: temp 0.3, max_tokens 1000

## 📁 Estrutura de Arquivos

```
Interface/
├── app/
│   ├── composables/
│   │   ├── useQueryBuilder.ts       # G1
│   │   ├── useAnswerComposer.ts     # G2
│   │   ├── useVectorSearch.ts       # DBVECTOR client
│   │   └── examples.query-builder.ts
│   └── pages/
│       └── index.vue                 # Interface principal
├── QUERY_BUILDER.md                  # Doc G1
├── ANSWER_COMPOSER.md                # Doc G2
├── INTEGRATION.md                    # Guia integração
└── SETUP.md                          # Guia instalação

DBVECTOR/
├── src/
│   ├── api/
│   │   └── main.py                   # FastAPI endpoints
│   ├── storage/
│   │   ├── faiss_store.py           # FAISS implementation
│   │   └── opensearch_store.py      # OpenSearch implementation
│   └── embeddings.py                 # BGE-M3 embeddings
└── data/
    └── indexes/                      # Índices vetoriais
```

## 🚀 Quick Start

```bash
# 1. DBVECTOR (Backend)
cd DBVECTOR
pip install -r requirements.txt
python -m src.pipelines.build_faiss
uvicorn src.api.main:app --reload --port 8000

# 2. Interface (Frontend)
cd Interface
pnpm install
# Configure .env com OPENAI_API_KEY
pnpm dev

# 3. Acesse
http://localhost:3000
```

## ✅ Validação

### Teste 1: Pipeline Completo
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"q": "prisão preventiva", "k": 5}'
```

### Teste 2: Query Builder
```javascript
// No console do navegador (F12)
// Deve mostrar query otimizada
```

### Teste 3: Answer Composer
```javascript
// Interface deve mostrar:
// - Badge de cobertura (🎯/⚡/⚠️/❌)
// - Contador de citações (📚 N citações)
// - Lista de fontes citadas
```

## 📈 Métricas de Qualidade

### Cobertura
- **Alta (🎯)**: 3+ docs, score ≥ 0.7 → Resposta completa
- **Média (⚡)**: 2+ docs, score ≥ 0.5 → Resposta boa
- **Baixa (⚠️)**: 1 doc → Resposta parcial + sugestões
- **Nenhuma (❌)**: 0 docs → Explicação + 3 sugestões

### Citações
- **Ideal**: 2-5 citações por resposta
- **Formato**: `[doc_id]` ao final da frase
- **Validação**: Todos os doc_ids devem existir em `retrieved`

## 🎓 Casos de Uso

### 1. Pesquisa Jurídica
**Query**: "Quando cabe prisão preventiva?"  
**Resultado**: Resposta fundamentada + 3-5 citações + cobertura alta

### 2. Análise de Jurisprudência
**Query**: "STF sobre liberdade provisória"  
**Resultado**: Síntese de julgados + citações de decisões específicas

### 3. Consulta de Artigos
**Query**: "art. 312 CPP"  
**Resultado**: Explicação do artigo + jurisprudência + citações

### 4. Comparação de Normas
**Query**: "Diferença entre prisão preventiva e temporária"  
**Resultado**: Comparação baseada em documentos + citações de ambos

## 🔒 Segurança

- ✅ API keys em `.env` (nunca no código)
- ✅ Validação de input (length, caracteres)
- ✅ Rate limiting (10 req/min por usuário)
- ✅ CORS configurado no DBVECTOR
- ✅ Sanitização de queries

## 📚 Documentação

| Documento | Descrição |
|-----------|-----------|
| [QUERY_BUILDER.md](./QUERY_BUILDER.md) | G1: Query Builder completo |
| [ANSWER_COMPOSER.md](./ANSWER_COMPOSER.md) | G2: Answer Composer completo |
| [INTEGRATION.md](./INTEGRATION.md) | Guia de integração |
| [SETUP.md](./SETUP.md) | Instalação e configuração |
| [examples.query-builder.ts](./app/composables/examples.query-builder.ts) | 10 exemplos práticos |

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/nova-feature`
3. Commit: `git commit -m 'Add nova feature'`
4. Push: `git push origin feature/nova-feature`
5. Pull Request

## 📝 Licença

Ver arquivo [LICENSE](../LICENSE)

---

**Projeto**: RAG-TCC  
**Instituição**: LabTechUDF  
**Versão**: 1.0.0  
**Status**: ✅ Produção  
**Data**: 2025-01-05
