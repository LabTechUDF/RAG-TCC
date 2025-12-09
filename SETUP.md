# 🚀 SETUP - RAG TCC

**Guia completo de configuração para desenvolvedores iniciantes**

---

## 📖 Sobre o Projeto

Este é um sistema RAG (Retrieval-Augmented Generation) especializado em **execução penal** integrado ao **Sistema Eletrônico de Execução Unificado (SEEU)**. O projeto é dividido em duas partes principais:

### 🔹 **DBVECTOR** (Backend)
Sistema de busca vetorial com inteligência artificial que:
- Processa documentos jurídicos (jurisprudências)
- Gera embeddings semânticos para busca inteligente
- Fornece API REST para consultas com IA
- Usa modelos de linguagem (LLM) para gerar respostas jurídicas fundamentadas

### 🔹 **Interface** (Frontend)
Interface web moderna construída com Nuxt.js que:
- Permite fazer perguntas jurídicas em linguagem natural
- Exibe respostas formatadas com base em jurisprudências reais
- Integra com o backend DBVECTOR via API

---

## 🛠️ Pré-requisitos

### Para o Backend (DBVECTOR)
- **Python 3.10+** 
- **pip** (gerenciador de pacotes Python)
- **Git**

### Para o Frontend (Interface)
- **Node.js 18+** (recomendado: v20 LTS)
- **pnpm** (gerenciador de pacotes)
- **Git**

### Chaves de API Necessárias
Você precisará de pelo menos UMA das seguintes chaves:
- **OpenAI API Key** (recomendado - GPT-4 ou GPT-3.5)
- **Anthropic API Key** (Claude)

---

## 📥 Instalação

### 1️⃣ Clone o Repositório

```bash
git clone https://github.com/LabTechUDF/RAG-TCC.git
cd RAG-TCC
```

---

## ⚙️ Configuração do Backend (DBVECTOR)

### 1. Entre na pasta do backend

```bash
cd DBVECTOR
```

### 2. Crie um ambiente virtual Python (recomendado)

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

**Tempo estimado:** 2-5 minutos (dependendo da conexão)

### 4. Configure as variáveis de ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o arquivo .env com seu editor preferido
nano .env   # ou use vim, code, etc.
```

**Configurações OBRIGATÓRIAS no `.env`:**

```bash
# ============= CONFIGURAÇÃO MÍNIMA =============

# Backend de busca (deixe como está)
SEARCH_BACKEND=faiss

# LLM - ESCOLHA UMA OPÇÃO:

# Opção 1: OpenAI (recomendado)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini  # ou gpt-4, gpt-3.5-turbo

# Opção 2: Anthropic Claude
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### 5. Verifique se há dados indexados

```bash
# Verifique se existe o índice FAISS
ls -lh data/indexes/faiss/

# Deve existir um arquivo index.faiss
# Se NÃO existir, você precisa indexar os dados primeiro
```

### 6. (Opcional) Indexar dados

Se não houver índice criado, você precisa processar os documentos:

```bash
# Certifique-se de que há dados em data/merged_clean.jsonl
python -m src.pipelines.build_faiss
```

**Tempo estimado:** Depende do volume de dados (pode levar de minutos a horas)

### 7. Inicie o servidor backend

```bash
python -m uvicorn src.api.main:app --reload --port 8000
```

**Servidor rodando em:** `http://localhost:8000`

Para testar se está funcionando, abra no navegador:
- `http://localhost:8000/health` - Deve retornar `{"status": "ok"}`
- `http://localhost:8000/docs` - Documentação interativa da API

---

## 🎨 Configuração do Frontend (Interface)

### 1. Abra um NOVO terminal e entre na pasta do frontend

```bash
cd Interface
```

### 2. Instale o pnpm (se ainda não tiver)

```bash
npm install -g pnpm
```

### 3. Instale as dependências do frontend

```bash
pnpm install
```

**Tempo estimado:** 2-5 minutos

### 4. Configure as variáveis de ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o arquivo .env
nano .env
```

**Configurações OBRIGATÓRIAS no `.env`:**

```bash
# OpenAI API Key (mesma do backend)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Senha da sessão (qualquer string de 32+ caracteres)
NUXT_SESSION_PASSWORD=sua-senha-muito-segura-com-pelo-menos-32-caracteres-aqui

# URL do backend DBVECTOR (deixe como está se estiver rodando local)
NUXT_PUBLIC_DBVECTOR_API_URL=http://localhost:8000

# GitHub OAuth (OPCIONAL - apenas se quiser autenticação)
# NUXT_OAUTH_GITHUB_CLIENT_ID=
# NUXT_OAUTH_GITHUB_CLIENT_SECRET=

# Database (OPCIONAL - apenas se quiser histórico de conversas)
# DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### 5. (Opcional) Configure o banco de dados

Se você configurou o `DATABASE_URL`, rode as migrações:

```bash
pnpm db:migrate
```

### 6. Inicie o servidor frontend

```bash
pnpm dev
```

**Servidor rodando em:** `http://localhost:3000`

---

## ✅ Testando a Aplicação

### 1. Acesse a interface web

Abra seu navegador em: `http://localhost:3000`

### 2. Faça uma pergunta de teste

Exemplo de pergunta:
```
Quais são os requisitos para progressão de regime no caso de 
um condenado que já cumpriu 1/6 da pena em regime fechado?
```

### 3. Verificando se está funcionando

Você deve ver:
- ✅ A aplicação processa a pergunta
- ✅ Faz busca no banco vetorial
- ✅ Retorna resposta formatada com jurisprudências relevantes
- ✅ Mostra informações estruturadas (teses jurídicas, conclusões, etc.)

---

## 🐛 Solução de Problemas Comuns

### ❌ Backend não inicia

**Erro:** `ModuleNotFoundError: No module named 'xxx'`
```bash
# Certifique-se de estar no ambiente virtual
cd DBVECTOR
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Reinstale as dependências
pip install -r requirements.txt
```

### ❌ "OPENAI_API_KEY not found"

```bash
# Verifique se o .env existe e está configurado
cd DBVECTOR
cat .env | grep OPENAI_API_KEY

# Se não aparecer nada, edite o .env e adicione sua chave
nano .env
```

### ❌ "No FAISS index found"

```bash
# Você precisa criar o índice primeiro
cd DBVECTOR
python -m src.pipelines.build_faiss
```

### ❌ Frontend não conecta ao backend

```bash
# Verifique se o backend está rodando
curl http://localhost:8000/health

# Se não estiver, inicie o backend primeiro:
cd DBVECTOR
python -m uvicorn src.api.main:app --reload --port 8000
```

### ❌ "Address already in use"

```bash
# Porta 8000 ou 3000 já está em uso
# Mate o processo ou use outra porta:

# Backend em outra porta:
python -m uvicorn src.api.main:app --reload --port 8001

# Frontend em outra porta:
pnpm dev --port 3001

# Lembre-se de atualizar NUXT_PUBLIC_DBVECTOR_API_URL no .env do frontend
```

---

## 📂 Estrutura do Projeto

```
RAG-TCC/
├── DBVECTOR/                 # Backend - API e processamento
│   ├── data/                 # Dados e índices
│   │   ├── merged_clean.jsonl       # Documentos jurídicos
│   │   └── indexes/faiss/           # Índice vetorial FAISS
│   ├── src/                  # Código fonte
│   │   ├── api/              # Endpoints FastAPI
│   │   ├── pipelines/        # Indexação e consulta
│   │   ├── storage/          # Armazenamento vetorial
│   │   ├── rag_service.py    # Lógica principal do RAG
│   │   ├── rag_schemas.py    # Estruturas de dados
│   │   └── embeddings.py     # Geração de embeddings
│   ├── requirements.txt      # Dependências Python
│   └── .env                  # Configurações (criar a partir do .env.example)
│
├── Interface/                # Frontend - Interface web
│   ├── app/                  # Código da aplicação Nuxt
│   │   ├── pages/            # Páginas da aplicação
│   │   ├── components/       # Componentes Vue
│   │   └── composables/      # Lógica reutilizável
│   ├── server/               # Backend Nuxt (SSR)
│   │   └── api/              # Endpoints intermediários
│   ├── package.json          # Dependências Node.js
│   └── .env                  # Configurações (criar a partir do .env.example)
│
└── SETUP.md                  # Este arquivo
```

---

## 🔄 Fluxo de Funcionamento

```
1. Usuário faz uma pergunta no Frontend (Interface)
                    ↓
2. Frontend envia para Backend (DBVECTOR) via API
                    ↓
3. Backend processa a pergunta:
   a) Normaliza a query (extrai informações jurídicas)
   b) Gera embedding da query
   c) Busca documentos similares no FAISS
   d) Envia contexto + pergunta para o LLM (GPT-4/Claude)
   e) LLM gera resposta fundamentada nas jurisprudências
                    ↓
4. Backend retorna resposta estruturada
                    ↓
5. Frontend exibe resposta formatada para o usuário
```

---

## 🔧 Comandos Úteis

### Backend (DBVECTOR)

```bash
# Ativar ambiente virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Iniciar servidor
python -m uvicorn src.api.main:app --reload --port 8000

# Testar implementação RAG
python test_rag_implementation.py

# Reindexar documentos
python -m src.pipelines.build_faiss

# Rodar testes
pytest tests/

# Ver documentação da API
# Acesse http://localhost:8000/docs no navegador
```

### Frontend (Interface)

```bash
# Instalar dependências
pnpm install

# Iniciar em desenvolvimento
pnpm dev

# Build para produção
pnpm build

# Preview da build de produção
pnpm preview

# Rodar migrações do banco
pnpm db:migrate

# Limpar cache do Nuxt
rm -rf .nuxt node_modules/.cache
```

---

## 📚 Documentação Adicional

### Backend (DBVECTOR)
- **[README.md](DBVECTOR/README.md)** - Documentação completa do backend
- **[RAG_SEEU_README.md](DBVECTOR/RAG_SEEU_README.md)** - Sistema RAG especializado
- **[INSTALL.md](DBVECTOR/INSTALL.md)** - Instalação detalhada

### Frontend (Interface)
- **[README.md](Interface/README.md)** - Documentação do frontend
- **[RAG_INTEGRATION.md](Interface/RAG_INTEGRATION.md)** - Integração com backend

---

## 🔐 Segurança

### ⚠️ NUNCA COMMITE SUAS CHAVES DE API

Certifique-se de que os arquivos `.env` estão no `.gitignore`:

```bash
# Verifique
cat .gitignore | grep .env

# Os arquivos .env NÃO devem aparecer ao dar git status
git status
```

### 🔑 Onde conseguir chaves de API

**OpenAI:**
1. Acesse: https://platform.openai.com/api-keys
2. Crie uma conta (se não tiver)
3. Clique em "Create new secret key"
4. Copie a chave (ela só aparece uma vez!)

**Anthropic Claude:**
1. Acesse: https://console.anthropic.com/
2. Crie uma conta
3. Vá em "API Keys"
4. Crie uma nova chave

---

## 💡 Dicas para Iniciantes

### 1. Use ambientes virtuais sempre
Isso evita conflitos entre projetos Python diferentes.

### 2. Mantenha os terminais organizados
- Terminal 1: Backend (DBVECTOR)
- Terminal 2: Frontend (Interface)

### 3. Leia os logs
Se algo der errado, os erros aparecem no terminal. Leia com atenção!

### 4. Comece simples
Primeiro faça funcionar localmente, depois se preocupe com otimizações.

### 5. Use o Git
```bash
# Antes de fazer mudanças, crie uma branch
git checkout -b minha-feature

# Commit suas mudanças
git add .
git commit -m "Descrição das mudanças"

# Se algo der errado, volte atrás
git checkout main
git pull
```

---

## 🆘 Precisa de Ajuda?

1. **Verifique a documentação** dos módulos específicos (links acima)
2. **Leia os erros com atenção** - geralmente eles dizem o que está errado
3. **Consulte a seção de problemas comuns** neste guia
4. **Abra uma issue** no repositório do GitHub

---

## ✅ Checklist de Primeira Execução

- [ ] Python 3.10+ instalado
- [ ] Node.js 18+ instalado
- [ ] pnpm instalado
- [ ] Repositório clonado
- [ ] Ambiente virtual Python criado e ativado
- [ ] Dependências do backend instaladas (`pip install -r requirements.txt`)
- [ ] `.env` do backend configurado com API key
- [ ] Índice FAISS existe (ou foi criado)
- [ ] Backend rodando em `http://localhost:8000`
- [ ] Dependências do frontend instaladas (`pnpm install`)
- [ ] `.env` do frontend configurado
- [ ] Frontend rodando em `http://localhost:3000`
- [ ] Teste de pergunta funcionou

---

**🎉 Pronto! Agora você tem o sistema RAG TCC rodando localmente!**

Se tudo funcionou, você está pronto para começar a desenvolver e explorar o sistema.
