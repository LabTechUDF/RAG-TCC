# 🚀 Quick Start - Conda GPU/CPU

Guia rápido para começar com o sistema RAG Jurídico usando Conda.

## Escolha seu Ambiente

### 🎮 GPU (Aceleração com CUDA)

**Pré-requisitos:**
- Driver NVIDIA >= 530 (Linux) ou >= 531 (Windows)
- `nvidia-smi` funcionando

**Setup:**
```bash
# 1. Criar ambiente
make env-gpu

# 2. Ativar
conda activate rag-juridico

# 3. Verificar GPU
make sanity
# Deve mostrar: GPU symbols = True

# 4. Habilitar GPU
# Windows PowerShell:
$env:USE_FAISS_GPU="true"

# Linux/Mac:
export USE_FAISS_GPU=true

# 5. Teste rápido (opcional)
python test_gpu_quick.py

# 6. Build e executar
make faiss-build
make api
```

**Acessar:** http://localhost:8000/docs

---

### 💻 CPU (Sem GPU)

**Setup:**
```bash
# 1. Criar ambiente
make env-cpu

# 2. Ativar
conda activate rag-juridico-cpu

# 3. Build e executar
make faiss-build CONDA_ENV=rag-juridico-cpu
make api CONDA_ENV=rag-juridico-cpu
```

**Acessar:** http://localhost:8000/docs

---

## 🧪 Testar

```bash
# Health check
curl http://localhost:8000/health

# Busca
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"q": "direitos fundamentais", "k": 3}'

# Suite de testes
make test

# Verificação completa
make sanity
```

---

## 🆘 Problemas?

### GPU não funciona
```bash
# Verificar driver
nvidia-smi

# Verificar dentro do ambiente
python -c "import faiss; print(hasattr(faiss, 'StandardGpuResources'))"

# Se False, reinstalar
conda env remove -n rag-juridico
make env-gpu
```

### API não responde
```bash
# Verificar se está rodando
ps aux | grep uvicorn  # Linux/Mac
Get-Process | Select-String uvicorn  # Windows

# Reiniciar
pkill -f uvicorn  # Linux/Mac
Stop-Process -Name "python"  # Windows
make api
```

### Ambiente lento
```bash
# Usar mamba (mais rápido que conda)
conda install -n base -c conda-forge mamba
mamba env create -f environment.gpu.yml
```

---

## 📚 Documentação Completa

- **[README.md](README.md)** - Documentação completa
- **[DEPLOY_CONDA.md](DEPLOY_CONDA.md)** - Guias de deploy
- **[SANITY.md](SANITY.md)** - Verificações operacionais
- **[MIGRATION_CONDA_GPU.md](MIGRATION_CONDA_GPU.md)** - Resumo da migração

---

## 🎯 Próximos Passos

1. ✅ **Setup completo** (você está aqui)
2. 📊 **Carregar dados reais** - veja README.md seção "Como Plugar JSONs Reais"
3. 🔍 **Avaliar qualidade** - `make quality`
4. 🚀 **Deploy em produção** - veja DEPLOY_CONDA.md

---

**Dúvidas?** Consulte o troubleshooting em [README.md](README.md#-troubleshooting) ou [SANITY.md](SANITY.md).
