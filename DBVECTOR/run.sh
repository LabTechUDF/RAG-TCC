#!/bin/bash

# Script de execução rápida para desenvolvimento local
# Execute: bash run.sh ou ./run.sh

set -e

echo "🚀 RAG Jurídico - Setup rápido com Poetry"
echo "========================================="

# Verifica se Python está disponível
if ! command -v python &> /dev/null; then
    echo "❌ Python não encontrado. Instale Python 3.10+ primeiro."
    exit 1
fi

# Verifica se Poetry está instalado
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry não encontrado. Instalando..."
    curl -sSL https://install.python-poetry.org | python3 -
    echo "✅ Poetry instalado! Reinicie o terminal ou execute:"
    echo "   export PATH=\"$HOME/.local/bin:\$PATH\""
    exit 1
fi

# Cria .env se não existir
if [ ! -f .env ]; then
    echo "� Criando arquivo .env..."
    cp .env.example .env
    echo "✅ Arquivo .env criado! Edite se necessário."
fi

echo "📦 Instalando dependências com Poetry..."
poetry install

echo "🏗️ Criando índice FAISS com dados dummy..."
poetry run python -m src.pipelines.build_faiss

echo "🧪 Executando testes rápidos..."
poetry run pytest tests/test_embeddings.py tests/test_faiss_store.py -v

echo "🔍 Testando busca..."
poetry run python -m src.pipelines.query_faiss

echo ""
echo "✅ Setup completo!"
echo ""
echo "Para iniciar a API:"
echo "  make api"
echo "  # ou:"
echo "  poetry run uvicorn src.api.main:app --reload --port 8000"
echo ""
echo "Para ativar ambiente virtual:"
echo "  poetry shell"
echo ""
echo "Para testar a API:"
echo "  curl -X POST http://localhost:8000/search \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"q\": \"direitos fundamentais\", \"k\": 3}'"
echo ""
echo "📚 Documentação: http://localhost:8000/docs"