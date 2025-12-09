# Integração RAG - Interface + DBVECTOR

## 📋 Visão Geral

A Interface agora está totalmente integrada com o DBVECTOR para fornecer respostas baseadas em Retrieval-Augmented Generation (RAG) usando a base de conhecimento jurídica.

## 🔄 Fluxo RAG

Quando o **modo RAG está ativado**:

1. **Usuário** envia uma pergunta
2. **Interface** consulta o DBVECTOR (`/api/dbvector/search`)
3. **DBVECTOR** retorna documentos jurídicos relevantes (busca vetorial)
4. **Interface** monta um prompt enriquecido com contexto dos documentos
5. **OpenAI** processa o prompt com contexto e gera resposta fundamentada
6. **Interface** exibe a resposta com indicação dos documentos consultados

Quando o **modo Chat Simples está ativado**:
- A pergunta vai direto para OpenAI sem consultar a base de conhecimento

## 🚀 Como Usar

### 1. Certifique-se que o DBVECTOR está rodando

```bash
# No diretório DBVECTOR
cd /home/tupan/git/RAG-TCC/DBVECTOR
python -m uvicorn src.api.main:app --reload --port 8000
```

Verifique se está funcionando:
```bash
curl http://localhost:8000/health
```

### 2. Configure a Interface

Certifique-se que o arquivo `.env` tem:
```bash
NUXT_PUBLIC_DBVECTOR_API_URL=http://localhost:8000
OPENAI_API_KEY=sua-chave-aqui
```

### 3. Inicie a Interface

```bash
cd /home/tupan/git/RAG-TCC/Interface
pnpm run dev
```

### 4. Use a aplicação

1. Acesse http://localhost:3000
2. Selecione **"RAG"** no seletor de modo
3. Digite sua pergunta jurídica
4. A resposta será baseada nos documentos da base de conhecimento

## 🔍 Endpoints Criados

### `/api/dbvector/search` (POST)
Busca documentos no DBVECTOR

**Request:**
```json
{
  "q": "direitos fundamentais na constituição",
  "k": 5
}
```

**Response:**
```json
{
  "query": "direitos fundamentais na constituição",
  "total": 5,
  "backend": "faiss",
  "results": [
    {
      "id": "doc_123",
      "title": "Título do documento",
      "text": "Conteúdo...",
      "court": "STF",
      "code": "CF",
      "article": "5º",
      "score": 0.95
    }
  ]
}
```

### `/api/dbvector/health` (GET)
Verifica status do DBVECTOR

**Response:**
```json
{
  "status": "healthy",
  "backend": "faiss",
  "documents": 724492,
  "embedding_dim": 384
}
```

## 📊 Informações Técnicas

- **Modelo de Embeddings**: `neuralmind/bert-base-portuguese-cased`
- **Backend**: FAISS (busca vetorial em GPU/CPU)
- **Documentos Indexados**: ~724k documentos jurídicos
- **Dimensão dos Embeddings**: 384
- **Top-K padrão**: 5 documentos mais relevantes

## 🎯 Exemplo de Uso

**Pergunta:** "Quais são os direitos fundamentais garantidos pela constituição?"

**Fluxo com RAG:**
1. Interface busca 5 documentos relevantes no DBVECTOR
2. Monta prompt: "Com base nestes documentos: [documentos]... responda: [pergunta]"
3. OpenAI gera resposta fundamentada nos documentos
4. Usuário vê: "📚 Consultados 5 documentos jurídicos (faiss)" + resposta

**Fluxo sem RAG:**
1. Pergunta vai direto para OpenAI
2. Resposta é baseada no conhecimento geral do modelo

## 🐛 Troubleshooting

### DBVECTOR não está respondendo
```bash
# Verifique se está rodando
curl http://localhost:8000/health

# Se não estiver, inicie:
cd /home/tupan/git/RAG-TCC/DBVECTOR
python -m uvicorn src.api.main:app --reload --port 8000
```

### Erro "No documents found"
- Verifique se o índice FAISS foi construído:
```bash
cd /home/tupan/git/RAG-TCC/DBVECTOR
make faiss-build
```

### Erro de CORS
- O proxy da Interface deve resolver isso automaticamente
- Se persistir, verifique se a URL do DBVECTOR está correta no `.env`

## 📝 Logs

A aplicação registra todas as etapas:
- Modo selecionado (RAG vs Chat Simples)
- Consulta ao DBVECTOR
- Documentos encontrados
- Prompt construído
- Resposta da OpenAI

Verifique os logs no console do navegador (F12) e nos terminais dos servidores.
