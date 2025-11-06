# 🚀 Setup Rápido - RAG Pipeline Completo (G1 + G2)

## Pré-requisitos

- Node.js 18+ instalado
- pnpm instalado (`npm install -g pnpm`)
- Python 3.10+ (para DBVECTOR)
- OpenAI API Key

## Pipeline RAG

Este projeto implementa um pipeline RAG completo com dois componentes GPT:

1. **G1 - Query Builder** (`useQueryBuilder`): Otimiza queries para busca vetorial
2. **G2 - Answer Composer** (`useAnswerComposer`): Gera respostas com citações

```
Query Original → [G1] → Query Otimizada → [DBVECTOR] → Documentos 
→ [G2] → Resposta com Citações → Usuário
```

## Passos de Instalação

### 1. Configurar DBVECTOR (Backend)

```bash
cd DBVECTOR

# Criar ambiente virtual (se ainda não tiver)
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Edite .env se necessário

# Construir índice FAISS
python -m src.pipelines.build_faiss
# OU para OpenSearch:
# python -m src.pipelines.build_opensearch

# Iniciar API
uvicorn src.api.main:app --reload --port 8000
```

Verifique que está funcionando:
```bash
curl http://localhost:8000/health
```

### 2. Configurar Interface (Frontend)

```bash
cd Interface

# Instalar dependências
pnpm install

# Configurar variáveis de ambiente
cp .env.example .env

# Edite .env e adicione suas chaves:
# OPENAI_API_KEY=sk-...
# OPENAI_PROJECT_ID=proj_...
# NUXT_PUBLIC_DBVECTOR_API_URL=http://localhost:8000
```

### 3. Iniciar Interface

```bash
cd Interface
pnpm dev
```

Acesse: http://localhost:3000

## ✅ Verificação

### Teste 1: DBVECTOR está rodando?

```bash
curl http://localhost:8000/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "backend": "faiss",
  "documents": 1234,
  "embedding_dim": 768
}
```

### Teste 2: Interface está conectando?

1. Abra http://localhost:3000
2. Selecione modo **RAG (Busca Vetorial)**
3. Digite: "o que é prisão preventiva"
4. Deve exibir documentos relevantes e resposta

### Teste 3: Query Builder está funcionando?

Verifique o console do navegador (F12):
```javascript
Query otimizada: {
  original: "o que é prisão preventiva",
  optimized: "prisão preventiva art. 312 requisitos",
  tokens: 5,
  clusters: ["art. 312"]
}
```

### Teste 4: Answer Composer está funcionando?

Verifique na interface:
- ✅ Badge de cobertura: "🎯 Alta Cobertura"
- ✅ Contador de citações: "📚 2 citações"
- ✅ Citações entre colchetes na resposta: `[STJ_2021_AgInt_12345]`
- ✅ Lista de fontes citadas no final

## 🐛 Troubleshooting

### Erro: "Cannot connect to DBVECTOR"

**Solução:**
```bash
cd DBVECTOR
# Certifique-se que está rodando:
uvicorn src.api.main:app --reload --port 8000
```

### Erro: "No documents indexed"

**Solução:**
```bash
cd DBVECTOR
python -m src.pipelines.build_faiss
```

### Erro: "OpenAI API Error"

**Solução:**
1. Verifique `OPENAI_API_KEY` no `.env`
2. Confirme que tem créditos disponíveis
3. Teste com: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`

### Erros TypeScript no VSCode

**Normal!** Os erros de `useRuntimeConfig`, `$fetch`, etc. desaparecem quando o dev server roda.

**Solução:**
```bash
cd Interface
pnpm dev
# Aguarde a geração dos tipos em .nuxt/
```

Se persistir:
```bash
rm -rf .nuxt
pnpm dev
```

## 📊 Estrutura de Arquivos

```
Interface/
├── app/
│   ├── composables/
│   │   ├── useQueryBuilder.ts          ← G1: Query Builder
│   │   ├── useAnswerComposer.ts        ← G2: Answer Composer (NOVO!)
│   │   ├── useVectorSearch.ts          ← Integração DBVECTOR
│   │   └── examples.query-builder.ts   ← Exemplos de uso
│   └── pages/
│       └── index.vue                    ← Interface principal (atualizada)
├── .env                                 ← Suas chaves (não commitar!)
├── .env.example                         ← Template
├── nuxt.config.ts                       ← Configuração Nuxt
├── QUERY_BUILDER.md                     ← Doc G1
├── ANSWER_COMPOSER.md                   ← Doc G2 (NOVO!)
└── SETUP.md                             ← Este arquivo
```

## 🎯 Próximos Passos

1. **Testar com dados reais**: Adicione mais documentos ao DBVECTOR
2. **Ajustar prompt**: Edite `buildPrompt()` em `useQueryBuilder.ts`
3. **Personalizar clusters**: Modifique `getAvailableClusters()` em `useVectorSearch.ts`
4. **Melhorar UI**: Customize `index.vue` conforme necessário

## 📚 Documentação Adicional

- [QUERY_BUILDER.md](./QUERY_BUILDER.md) - G1: Query Builder
- [ANSWER_COMPOSER.md](./ANSWER_COMPOSER.md) - G2: Answer Composer
- [examples.query-builder.ts](./app/composables/examples.query-builder.ts) - Exemplos de código
- [DBVECTOR README](../DBVECTOR/README.md) - Documentação do backend

## 🆘 Suporte

Em caso de problemas:

1. Verifique logs do DBVECTOR: `tail -f logs/api.log`
2. Verifique console do navegador (F12)
3. Teste endpoints individualmente:
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # Busca manual
   curl -X POST http://localhost:8000/search \
     -H "Content-Type: application/json" \
     -d '{"q": "prisão preventiva", "k": 5}'
   ```

---

✅ **Setup completo!** A integração RAG com Query Builder está pronta para uso.
