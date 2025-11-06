# Guia de Sanidade Operacional - RAG Jurídico

Este documento contém comandos rápidos para verificar que o sistema está funcionando corretamente após instalação ou deployment.

## 1. Verificação de Ambiente

### 1.1. Verificar Python e Conda
```bash
# Verificar que o ambiente Conda está ativo
conda info --envs

# Verificar versão do Python
python --version
# Esperado: Python 3.10.x
```

### 1.2. Verificar GPU (se aplicável)
```bash
# Verificar driver NVIDIA
nvidia-smi

# Verificar CUDA toolkit
nvcc --version

# Verificar PyTorch detecta GPU
python -c "import torch; print('CUDA disponível:', torch.cuda.is_available()); print('Devices:', torch.cuda.device_count())"
```

### 1.3. Verificar FAISS GPU
```bash
# Verificar se FAISS tem símbolos GPU
python -c "import faiss; print('FAISS GPU disponível:', hasattr(faiss, 'StandardGpuResources'))"

# Verificar configuração atual
python -c "import os; print('USE_FAISS_GPU =', os.getenv('USE_FAISS_GPU', 'false'))"

# Ou usar o comando make
make sanity
```

**Esperado (GPU):**
- `FAISS GPU disponível: True`
- Se `USE_FAISS_GPU=true`, o sistema tentará usar GPU

**Esperado (CPU):**
- `FAISS GPU disponível: False`
- Sistema usa CPU automaticamente

## 2. Validação de Dados

### 2.1. Verificar estrutura dos dados
```bash
# Listar dados disponíveis
ls -lh data/indexes/faiss/*.jsonl

# Contar documentos em um arquivo
wc -l data/indexes/faiss/stj_decisoes_monocraticas.jsonl
```

### 2.2. Executar validação
```bash
# Validar dados (se houver arquivo merged)
make data-validate

# Ver relatório
cat reports/validation/report.json
```

**Verificações:**
- [ ] `valid_docs >= 90%` dos documentos
- [ ] `avg_length > 200` caracteres
- [ ] Campos obrigatórios presentes

## 3. Build e Query FAISS

### 3.1. Build do índice
```bash
# Limpar índice anterior (opcional)
make clean

# Build novo índice
make faiss-build

# Verificar que foi criado
ls -lh data/indexes/faiss/index.faiss
ls -lh data/indexes/faiss/metadata.parquet
```

**Esperado:**
- `index.faiss` criado
- `metadata.parquet` criado
- Logs indicando quantidade de documentos indexados

### 3.2. Query manual
```bash
# Query simples via pipeline
export QUERY="prisão preventiva"
make faiss-query

# Ou diretamente
conda run -n rag-juridico python -m src.pipelines.query_faiss
```

**Esperado:**
- Lista de documentos relevantes
- Scores de similaridade
- Tempo de busca < 200ms (SLO P95)

## 4. API Health Check

### 4.1. Iniciar API
```bash
# Iniciar em background (ou em outro terminal)
make api &

# Aguardar inicialização (5-10 segundos)
sleep 10
```

### 4.2. Testar endpoints
```bash
# Health check
curl http://localhost:8000/health

# Search endpoint
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "direitos fundamentais", "k": 5}'

# Metrics (se habilitado)
curl http://localhost:8000/metrics
```

**Esperado (Health):**
```json
{
  "status": "healthy",
  "backend": "faiss",
  "doc_count": 1234
}
```

**Esperado (Search):**
- HTTP 200
- `results` contém array de documentos
- Cada resultado tem `doc` e `score`

## 5. Testes Automatizados

### 5.1. Rodar suite de testes
```bash
# Testes básicos
make test

# Com coverage
make test-cov
```

**Esperado:**
- Todos os testes passam
- Coverage >= 70%

### 5.2. Teste específico GPU
```bash
# Rodar apenas testes GPU
conda run -n rag-juridico pytest tests/test_faiss_gpu.py -v

# Smoke test rápido
python -c "from tests.test_faiss_gpu import test_gpu_availability_detection; test_gpu_availability_detection()"
```

## 6. Benchmarks

### 6.1. Latência de query
```bash
# Rodar benchmarks
make bench

# Ver resultados
ls -lh .benchmarks/
```

**SLOs:**
- P95 latência < 200ms
- Throughput > 50 queries/s

### 6.2. Build time
```bash
# Medir tempo de build
time make faiss-build
```

**SLO:**
- Build time < 60s para ~10k docs

## 7. Troubleshooting Rápido

### Problema: FAISS GPU não funciona
```bash
# 1. Verificar instalação
conda list | grep faiss
# Deve mostrar faiss-gpu

# 2. Verificar CUDA
python -c "import torch; print(torch.version.cuda)"
# Deve mostrar 12.1 (ou compatível)

# 3. Verificar driver
nvidia-smi
# Driver deve ser >= 530 para CUDA 12.1

# 4. Reinstalar ambiente
conda env remove -n rag-juridico
make env-gpu
```

### Problema: API não responde
```bash
# 1. Verificar se está rodando
ps aux | grep uvicorn

# 2. Verificar logs
# (se rodou em background, ver output)

# 3. Testar porta
netstat -tuln | grep 8000

# 4. Reiniciar
pkill -f uvicorn
make api
```

### Problema: Testes falham
```bash
# 1. Limpar cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +

# 2. Reinstalar dependências
conda env update -f environment.gpu.yml --prune

# 3. Rodar teste específico com verbose
conda run -n rag-juridico pytest tests/test_faiss_store.py::test_name -v -s
```

### Problema: Memória GPU esgotada
```bash
# 1. Verificar uso
nvidia-smi

# 2. Liberar memória
python -c "import torch; torch.cuda.empty_cache()"

# 3. Reduzir batch size ou usar CPU
export USE_FAISS_GPU=false
make faiss-build
```

## 8. Checklist Completo

Execute este checklist após cada deployment:

- [ ] `conda info --envs` mostra ambiente ativo
- [ ] `python --version` retorna 3.10.x
- [ ] `nvidia-smi` funciona (se GPU)
- [ ] `make sanity` passa
- [ ] `make faiss-build` completa sem erro
- [ ] `make api` inicia e responde
- [ ] `curl http://localhost:8000/health` retorna 200
- [ ] `curl http://localhost:8000/search` retorna resultados
- [ ] `make test` passa (todos os testes)
- [ ] `make bench` completa dentro dos SLOs

## 9. Scripts de Sanidade Automatizados

### Script completo (Linux/Mac)
```bash
#!/bin/bash
set -e

echo "=== Sanidade RAG Jurídico ==="
echo "1. Verificando ambiente..."
conda info --envs | grep rag-juridico

echo "2. Verificando FAISS GPU..."
python -c "import faiss; print('GPU:', hasattr(faiss, 'StandardGpuResources'))"

echo "3. Build rápido (10 docs)..."
# Assumindo script de build com limite
# python -m src.pipelines.build_faiss --limit 10

echo "4. Query teste..."
export QUERY="teste"
python -m src.pipelines.query_faiss

echo "5. Health API..."
# Assumindo API já está rodando
curl -s http://localhost:8000/health | python -m json.tool

echo "✅ Sanidade completa!"
```

### Script PowerShell (Windows)
```powershell
Write-Host "=== Sanidade RAG Jurídico ===" -ForegroundColor Green

Write-Host "1. Verificando ambiente..."
conda info --envs | Select-String "rag-juridico"

Write-Host "2. Verificando FAISS GPU..."
python -c "import faiss; print('GPU:', hasattr(faiss, 'StandardGpuResources'))"

Write-Host "3. Query teste..."
$env:QUERY = "teste"
python -m src.pipelines.query_faiss

Write-Host "4. Health API..."
(Invoke-WebRequest -Uri http://localhost:8000/health).Content | ConvertFrom-Json

Write-Host "✅ Sanidade completa!" -ForegroundColor Green
```

---

## Contatos e Suporte

- Documentação: `README.md`
- Deploy: `DEPLOY_CONDA.md`
- Qualidade: `QUALITY.md`
