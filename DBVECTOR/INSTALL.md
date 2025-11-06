# Instalar Poetry primeiro:
# Windows: (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
# Linux/Mac: curl -sSL https://install.python-poetry.org | python3 -

# Se Poetry funcionar:
poetry install

# Se Poetry falhar no Windows (problemas de compilação), use pip como fallback:
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

# Depois continue normalmente:
# cp .env.example .env
# python -m src.pipelines.build_faiss
# python -m src.pipelines.query_faiss
# uvicorn src.api.main:app --reload