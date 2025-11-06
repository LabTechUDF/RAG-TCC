# Guia Rápido: Métricas & Qualidade

Este documento resume como usar o pacote completo de validação, testes, benchmarks, avaliação e monitoramento do RAG Jurídico.

## 🎯 Quick Start

```bash
# 1. Instalar dependências (inclui pytest-benchmark)
poetry install --with dev

# 2. Executar workflow completo de qualidade
make quality
```

## 📋 Checklist de Qualidade

### Antes de Indexar Dados

- [ ] **Validar dados**: `make data-validate`
  - Verifica campos obrigatórios
  - Detecta textos curtos
  - Encontra tokens HTML residuais
  - Identifica IDs duplicados

### Durante Desenvolvimento

- [ ] **Executar testes**: `poetry run pytest -v`
  - Testes unitários e funcionais
  - Skip automático de OpenSearch se não disponível
  
- [ ] **Medir performance**: `make bench`
  - Latência de queries
  - Tempo de build de índice
  - Throughput

### Antes de Deploy

- [ ] **Avaliar recuperação**: `make eval`
  - Precision@K, Recall@K
  - MRR, nDCG@K
  - Valida thresholds

- [ ] **Inspecionar embeddings**: `make inspect-emb`
  - Detecta NaN/Inf
  - Verifica colapso
  - Encontra duplicatas densas

## 🔧 Comandos Principais

### Validação de Dados

```bash
# Básico
make data-validate

# Com parâmetros customizados
poetry run python -m src.tools.validate_data \
  --input data/merged_clean.jsonl \
  --min-chars 200 \
  --max-bad-pct 10 \
  --report reports/validation/report.json
```

**Exit codes:**
- `0`: OK, dados aprovados
- `1`: Erro de IO
- `2`: Falha por threshold

### Testes

```bash
# Todos os testes
poetry run pytest -v

# Sem OpenSearch
poetry run pytest -m "not opensearch" -v

# Com cobertura
poetry run pytest --cov=src --cov-report=html

# Apenas benchmarks
poetry run pytest tests/bench -v
```

### Benchmarks

```bash
# Executar e salvar baseline
make bench

# Comparar com baseline anterior
make bench-compare

# Ver histórico
ls .benchmarks/
```

**Métricas:**
- Latência p95 de queries (SLO: 200ms)
- Tempo de build de índice (SLO: 60s)
- Throughput (mín: 10 QPS)

### Avaliação de Recuperação

```bash
# FAISS
make eval

# OpenSearch
make eval-opensearch

# Custom
poetry run python -m src.eval.retrieval_eval \
  --qa data/eval/qa_dev.jsonl \
  --k 10 \
  --backend faiss \
  --min-p 0.6 \
  --min-ndcg 0.75
```

**Métricas:**
- **Precision@K**: % relevantes nos top-K
- **Recall@K**: % relevantes recuperados
- **MRR**: Posição do 1º relevante
- **nDCG@K**: Qualidade da ordenação

### Inspeção de Embeddings

```bash
# Gera embeddings on-the-fly
make inspect-emb

# De arquivo .npy
poetry run python -m src.eval.inspect_embeddings \
  --input embeddings.npy \
  --mode npy

# De JSONL com vetores
poetry run python -m src.eval.inspect_embeddings \
  --input data_with_vectors.jsonl \
  --mode vectors-jsonl \
  --near-dupes-threshold 0.99
```

## ⚙️ Configuração (`.env`)

```bash
# Validação de Dados
MIN_CHARS=200                    # Tamanho mínimo de texto
VALIDATION_MAX_BAD_PCT=10        # % máxima de docs problemáticos

# SLOs e Benchmarks
SLO_P95_MS=200                   # Latência p95 máxima (ms)
MAX_BUILD_TIME_S=60              # Tempo máx de build (s)

# Avaliação de Recuperação
MIN_P5=0.55                      # Precision@5 mínima
MIN_NDCG5=0.70                   # nDCG@5 mínimo

# Inspeção de Embeddings
NEAR_DUPES_MAX_PCT=1             # % máxima de near-duplicates
```

## 🚀 CI/CD

O workflow `.github/workflows/ci.yml` executa automaticamente:

### Jobs

1. **validate_data**: Valida qualidade dos dados
2. **tests**: Testes unitários/funcionais com cobertura
3. **bench**: Benchmarks de performance
4. **eval**: Avaliação de métricas de recuperação
5. **lint**: Formatação e estilo de código
6. **summary**: Resumo agregado

### Triggers

- Push em `main`, `develop`, `chore/consolidando-aplicacao`
- Pull requests para `main`
- Agendado: diariamente às 6h UTC

### Artifacts

- `validation-report`: Relatório de validação
- `benchmark-results`: Resultados de benchmarks
- `eval-results-*`: Métricas de recuperação
- Cobertura de código (Codecov)

## 📊 Estrutura de Relatórios

```
reports/
├── validation/
│   └── report.json              # Qualidade dos dados
├── eval/
│   ├── retrieval_metrics.json   # Métricas agregadas
│   └── retrieval_metrics.csv    # Detalhes por query
└── inspect/
    └── embeddings_summary.json  # Saúde dos embeddings
```

## 🎓 Exemplos de Uso

### Validar Antes de Indexar

```bash
# 1. Mesclar dados
make data-merge

# 2. Validar qualidade
make data-validate

# 3. Se aprovado, indexar
make faiss-build
```

### Medir Performance Antes de Deploy

```bash
# 1. Build índice com dados reais
make faiss-build

# 2. Executar benchmarks
make bench

# 3. Verificar se atende SLOs
cat .benchmarks/*/0001_*.json | grep "mean"
```

### Avaliar Qualidade de Recuperação

```bash
# 1. Preparar dataset Q&A
# Editar: data/eval/qa_dev.jsonl

# 2. Executar avaliação
make eval

# 3. Verificar métricas
cat reports/eval/retrieval_metrics.json

# 4. Analisar queries problemáticas
cat reports/eval/retrieval_metrics.csv
```

### Debugar Embeddings

```bash
# 1. Inspecionar vetores
make inspect-emb

# 2. Ver relatório
cat reports/inspect/embeddings_summary.json

# 3. Se houver problemas, verificar:
#    - NaNs/Infs (bug no modelo?)
#    - Colapso (normalização?)
#    - Duplicatas (dados duplicados?)
```

## 🐛 Troubleshooting

### Validação Falha

**Problema:** `bad_overall_pct > max-bad-pct`

**Soluções:**
- Aumentar `--max-bad-pct` temporariamente
- Limpar dados com `src.tools.tratamento_dados`
- Filtrar registros problemáticos

### Benchmarks Abaixo do SLO

**Problema:** Latência p95 > 200ms

**Soluções:**
- Verificar tamanho do índice
- Considerar quantização (FAISS)
- Mover para OpenSearch (cache)

### Métricas de Recuperação Baixas

**Problema:** nDCG@5 < 0.70

**Soluções:**
- Revisar dataset Q&A (ground-truth correto?)
- Testar diferentes modelos de embedding
- Considerar busca híbrida (BM25 + kNN)

### Embeddings com NaN

**Problema:** `has_nan: true`

**Soluções:**
- Verificar textos vazios/inválidos
- Atualizar sentence-transformers
- Validar dados de entrada

## 📚 Referências

- **pytest-benchmark**: https://pytest-benchmark.readthedocs.io/
- **Métricas de IR**: https://en.wikipedia.org/wiki/Evaluation_measures_(information_retrieval)
- **FAISS**: https://github.com/facebookresearch/faiss
- **OpenSearch**: https://opensearch.org/docs/latest/

## 🤝 Contribuindo

Ao adicionar features, sempre inclua:

1. Testes unitários (`tests/test_*.py`)
2. Benchmarks se aplicável (`tests/bench/`)
3. Documentação no README
4. Atualização dos thresholds (`.env.example`)

---

**💡 Dica:** Execute `make quality` antes de cada commit para garantir que tudo está funcionando corretamente!
