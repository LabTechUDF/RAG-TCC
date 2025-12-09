.PHONY: env-gpu env-cpu install install-dev clean shell add add-dev update format lint demo
.PHONY: faiss-build faiss-query os-up os-down os-logs os-build os-query api test test-cov data-merge
.PHONY: data-validate bench bench-compare eval eval-opensearch inspect-emb quality sanity

# Conda environment
CONDA_ENV ?= rag-juridico
PYTHON    ?= python

# Criação de ambientes Conda
env-gpu:
	conda env create -f environment.gpu.yml || conda env update -f environment.gpu.yml --prune

env-cpu:
	conda env create -f environment.cpu.yml || conda env update -f environment.cpu.yml --prune

# Instalação (Poetry - mantido para compatibilidade)
install:
	poetry install

install-dev: install
	poetry install --with dev

# Limpeza
clean:
	rm -rf data/indexes/faiss/*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Ambiente virtual (Poetry - mantido para compatibilidade)
shell:
	poetry shell

# Dependências
add:
	poetry add $(package)

add-dev:
	poetry add --group dev $(package)

update:
	poetry update

# Linting e formatação
format:
	conda run -n $(CONDA_ENV) black src/ tests/
	conda run -n $(CONDA_ENV) isort src/ tests/

lint:
	conda run -n $(CONDA_ENV) black --check src/ tests/
	conda run -n $(CONDA_ENV) isort --check-only src/ tests/
	conda run -n $(CONDA_ENV) flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503

# Testes
test:
	conda run -n $(CONDA_ENV) pytest tests/ -v

test-cov:
	conda run -n $(CONDA_ENV) pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# FAISS workflows
faiss-build:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.pipelines.build_faiss

faiss-query:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.pipelines.query_faiss

# OpenSearch workflows
os-up:
	docker-compose up -d opensearch

os-down:
	docker-compose down -v

os-logs:
	docker-compose logs -f opensearch

os-build:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.pipelines.build_opensearch

os-query:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.pipelines.query_opensearch

# API
api:
	conda run -n $(CONDA_ENV) uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Workflow completo FAISS
setup-faiss: faiss-build
	@echo "✅ Setup FAISS completo! Execute 'make api' para iniciar a API"

# Workflow completo OpenSearch  
setup-opensearch: os-up
	@echo "⏳ Aguardando OpenSearch inicializar..."
	@sleep 15
	$(MAKE) os-build
	@echo "✅ Setup OpenSearch completo! Altere SEARCH_BACKEND=opensearch no .env"

# Demo rápido
demo:
	conda run -n $(CONDA_ENV) $(PYTHON) demo.py

# Tratando os dados
data-merge:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.tools.tratamento_dados --input data/indexes/faiss --output data/merged_clean.jsonl --dedupe-by case_number

# Validação de dados
data-validate:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.tools.validate_data --input data/merged_clean.jsonl --report reports/validation/report.json

# Benchmarks
bench:
	conda run -n $(CONDA_ENV) pytest tests/bench --benchmark-only --benchmark-save=baseline

bench-compare:
	conda run -n $(CONDA_ENV) pytest tests/bench --benchmark-only --benchmark-compare

# Avaliação de recuperação
eval:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.eval.retrieval_eval --qa data/eval/qa_dev.jsonl --k 5 --backend faiss --report reports/eval/retrieval_metrics.json --csv reports/eval/retrieval_metrics.csv

eval-opensearch:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.eval.retrieval_eval --qa data/eval/qa_dev.jsonl --k 5 --backend opensearch --report reports/eval/retrieval_metrics_os.json --csv reports/eval/retrieval_metrics_os.csv

# Inspeção de embeddings
inspect-emb:
	conda run -n $(CONDA_ENV) $(PYTHON) -m src.eval.inspect_embeddings --input data/merged_clean.jsonl --mode generate --report reports/inspect/embeddings_summary.json

# Workflow completo de qualidade
quality: data-validate bench eval inspect-emb
	@echo "✅ Todas as verificações de qualidade concluídas!"

# Sanity checks
sanity:
	@echo "=== Verificação de Sanidade ==="
	@echo "GPU disponível no FAISS?"
	@conda run -n $(CONDA_ENV) $(PYTHON) -c "import faiss, os; print('USE_FAISS_GPU =', os.getenv('USE_FAISS_GPU', 'false')); print('GPU symbols =', hasattr(faiss, 'StandardGpuResources'))"