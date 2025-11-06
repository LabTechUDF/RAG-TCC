# Guia de Deploy com Conda - RAG Jurídico

Este documento descreve como fazer o deploy do sistema RAG Jurídico usando Conda em diferentes ambientes (desenvolvimento, staging, produção).

## 📋 Pré-requisitos

- **Conda** ou **Miniconda** instalado
- **Git** para clonar o repositório
- **Driver NVIDIA** (opcional, para GPU)
- **Docker** (opcional, para OpenSearch)

## 🎯 Estratégias de Deploy

### 1. Desenvolvimento Local (CPU)

Ideal para desenvolvimento e testes sem necessidade de GPU.

```bash
# Clone o repositório
git clone <repo-url>
cd rag-juridico

# Cria ambiente CPU
conda env create -f environment.cpu.yml

# Ativa ambiente
conda activate rag-juridico-cpu

# Verifica instalação
python -c "import faiss, torch; print('OK')"

# Configura variáveis
export SEARCH_BACKEND=faiss
export USE_FAISS_GPU=false

# Build e execução
make faiss-build CONDA_ENV=rag-juridico-cpu
make api CONDA_ENV=rag-juridico-cpu
```

### 2. Desenvolvimento Local (GPU)

Para desenvolvimento com aceleração GPU.

```bash
# Verifica GPU disponível
nvidia-smi

# Cria ambiente GPU
conda env create -f environment.gpu.yml

# Ativa ambiente
conda activate rag-juridico

# Verifica GPU FAISS
python -c "import faiss; print('GPU:', hasattr(faiss, 'StandardGpuResources'))"

# Configura variáveis
export SEARCH_BACKEND=faiss
export USE_FAISS_GPU=true
export FAISS_GPU_DEVICE=0

# Build e execução
make faiss-build CONDA_ENV=rag-juridico
make api CONDA_ENV=rag-juridico
```

### 3. Servidor Linux (GPU)

Deploy em servidor Linux com GPU NVIDIA.

```bash
# 1. Verificar driver NVIDIA
nvidia-smi
# Driver deve ser >= 530 para CUDA 12.1

# 2. Instalar Miniconda (se necessário)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 3. Clonar repositório
git clone <repo-url>
cd rag-juridico

# 4. Criar ambiente
conda env create -f environment.gpu.yml

# 5. Configurar variáveis (criar .env)
cat > .env << EOF
SEARCH_BACKEND=faiss
USE_FAISS_GPU=true
FAISS_GPU_DEVICE=0
API_HOST=0.0.0.0
API_PORT=8000
EOF

# 6. Build índice
conda run -n rag-juridico python -m src.pipelines.build_faiss

# 7. Executar API em background
nohup conda run -n rag-juridico uvicorn src.api.main:app \
  --host 0.0.0.0 --port 8000 > api.log 2>&1 &

# 8. Verificar saúde
curl http://localhost:8000/health
```

### 4. Windows com WSL2 (GPU)

GPU no Windows requer WSL2 com drivers CUDA para WSL.

#### Passo 1: Configurar WSL2

```powershell
# No PowerShell como Admin

# Instalar WSL2
wsl --install

# Reiniciar o PC

# Verificar versão
wsl --list --verbose
# Deve mostrar VERSION 2
```

#### Passo 2: Instalar Driver CUDA para WSL

1. **Não instale CUDA Toolkit no Windows** - apenas no WSL
2. Baixe driver NVIDIA para WSL: https://developer.nvidia.com/cuda/wsl
3. Instale o driver no Windows (não no WSL)
4. Verifique no WSL:

```bash
# Dentro do WSL
nvidia-smi
# Deve mostrar GPUs disponíveis
```

#### Passo 3: Setup no WSL

```bash
# No terminal WSL (Ubuntu)

# 1. Atualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar dependências
sudo apt install -y wget git

# 3. Instalar Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b
echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 4. Clonar projeto
git clone <repo-url>
cd rag-juridico

# 5. Criar ambiente GPU
conda env create -f environment.gpu.yml

# 6. Verificar GPU
conda activate rag-juridico
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
python -c "import faiss; print('GPU:', hasattr(faiss, 'StandardGpuResources'))"

# 7. Configurar e executar
export USE_FAISS_GPU=true
make faiss-build
make api
```

#### Passo 4: Acessar do Windows

A API rodando no WSL pode ser acessada do Windows:

```
http://localhost:8000
```

### 5. Docker (CPU)

Deploy usando Docker com Conda interno.

**Dockerfile:**

```dockerfile
FROM continuumio/miniconda3:latest

WORKDIR /app

# Copia arquivos
COPY environment.cpu.yml .
COPY . .

# Cria ambiente
RUN conda env create -f environment.cpu.yml && \
    conda clean -afy

# Ativa ambiente no shell
SHELL ["conda", "run", "-n", "rag-juridico-cpu", "/bin/bash", "-c"]

# Build índice (se necessário)
# RUN python -m src.pipelines.build_faiss

# Expõe porta
EXPOSE 8000

# Comando de inicialização
CMD ["conda", "run", "-n", "rag-juridico-cpu", \
     "uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
```

**Build e execução:**

```bash
# Build
docker build -t rag-juridico:cpu .

# Executar
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --name rag-juridico \
  rag-juridico:cpu

# Logs
docker logs -f rag-juridico

# Health check
curl http://localhost:8000/health
```

### 6. Docker (GPU)

Deploy GPU com Docker requer **nvidia-docker**.

**Pré-requisitos:**

```bash
# Instalar nvidia-docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

**Dockerfile.gpu:**

```dockerfile
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Instalar Miniconda
RUN apt-get update && \
    apt-get install -y wget && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniconda3-latest-Linux-x86_64.sh && \
    apt-get clean

ENV PATH=/opt/conda/bin:$PATH

WORKDIR /app

COPY environment.gpu.yml .
COPY . .

# Cria ambiente
RUN conda env create -f environment.gpu.yml && \
    conda clean -afy

SHELL ["conda", "run", "-n", "rag-juridico", "/bin/bash", "-c"]

ENV USE_FAISS_GPU=true
ENV FAISS_GPU_DEVICE=0

EXPOSE 8000

CMD ["conda", "run", "-n", "rag-juridico", \
     "uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
```

**Build e execução:**

```bash
# Build
docker build -f Dockerfile.gpu -t rag-juridico:gpu .

# Executar com GPU
docker run -d -p 8000:8000 \
  --gpus all \
  -v $(pwd)/data:/app/data \
  -e USE_FAISS_GPU=true \
  --name rag-juridico-gpu \
  rag-juridico:gpu

# Verificar GPU no container
docker exec rag-juridico-gpu nvidia-smi
```

## 🔧 Configurações por Ambiente

### Desenvolvimento

```bash
# .env.dev
SEARCH_BACKEND=faiss
USE_FAISS_GPU=false
API_HOST=0.0.0.0
API_PORT=8000
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Staging

```bash
# .env.staging
SEARCH_BACKEND=opensearch
OPENSEARCH_HOST=staging-opensearch.internal
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=juridico-staging
USE_FAISS_GPU=true
API_HOST=0.0.0.0
API_PORT=8000
```

### Produção

```bash
# .env.prod
SEARCH_BACKEND=opensearch
OPENSEARCH_HOST=prod-opensearch.internal
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=juridico-prod
OPENSEARCH_USE_SSL=true
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=<senha-forte>
USE_FAISS_GPU=true
FAISS_GPU_DEVICE=0
API_HOST=0.0.0.0
API_PORT=8000
```

## 📊 Monitoramento

### Health Checks

```bash
# Endpoint de saúde
curl http://localhost:8000/health

# Resposta esperada
{
  "status": "healthy",
  "backend": "faiss",
  "doc_count": 1234,
  "gpu_enabled": true
}
```

### Logs

```bash
# Com systemd
sudo journalctl -u rag-juridico -f

# Com Docker
docker logs -f rag-juridico

# Com nohup
tail -f api.log
```

### Métricas (Prometheus)

Se habilitado, métricas disponíveis em:

```
http://localhost:8000/metrics
```

## 🔄 Atualização e Rollback

### Atualização

```bash
# 1. Backup do índice atual
cp -r data/indexes/faiss data/indexes/faiss.backup

# 2. Pull nova versão
git pull origin main

# 3. Atualizar ambiente
conda env update -f environment.gpu.yml --prune

# 4. Rebuild se necessário
conda run -n rag-juridico python -m src.pipelines.build_faiss

# 5. Reiniciar API
pkill -f uvicorn
nohup conda run -n rag-juridico uvicorn src.api.main:app \
  --host 0.0.0.0 --port 8000 > api.log 2>&1 &

# 6. Verificar saúde
curl http://localhost:8000/health
```

### Rollback

```bash
# 1. Checkout versão anterior
git checkout <commit-anterior>

# 2. Restaurar índice
rm -rf data/indexes/faiss
mv data/indexes/faiss.backup data/indexes/faiss

# 3. Recriar ambiente da versão anterior
conda env update -f environment.gpu.yml --prune

# 4. Reiniciar API
pkill -f uvicorn
nohup conda run -n rag-juridico uvicorn src.api.main:app \
  --host 0.0.0.0 --port 8000 > api.log 2>&1 &
```

## 🚀 CI/CD

### GitHub Actions com Conda

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Miniconda
      uses: conda-incubator/setup-miniconda@v2
      with:
        miniconda-version: "latest"
        auto-update-conda: true
        python-version: "3.10"
    
    - name: Create environment
      run: |
        conda env create -f environment.cpu.yml
    
    - name: Run tests
      run: |
        conda run -n rag-juridico-cpu pytest -v
    
    - name: Build index
      run: |
        conda run -n rag-juridico-cpu python -m src.pipelines.build_faiss
    
    - name: Deploy to server
      run: |
        # Comando de deploy (rsync, scp, etc.)
        rsync -avz --exclude='.git' . user@server:/opt/rag-juridico/
```

## 🔒 Segurança

### Recomendações

1. **Não commite .env** com credenciais
2. **Use secrets** para variáveis sensíveis
3. **SSL/TLS** em produção
4. **Firewall** para limitar acesso
5. **Autenticação** na API (adicionar middleware)

### Exemplo com autenticação básica

```python
# src/api/main.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "senha-secreta")
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas"
        )
    return credentials.username

# Proteger endpoints
@app.post("/search", dependencies=[Depends(verify_credentials)])
async def search(request: SearchRequest):
    ...
```

## 🆘 Troubleshooting de Deploy

### Porta em uso

```bash
# Encontrar processo usando porta 8000
lsof -i :8000
# ou
netstat -tuln | grep 8000

# Matar processo
kill -9 <PID>
```

### GPU não detectada

```bash
# Verificar driver
nvidia-smi

# Verificar dentro do Conda env
conda activate rag-juridico
python -c "import torch; print(torch.cuda.is_available())"

# Se False, reinstalar pytorch com CUDA
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia
```

### Memória insuficiente

```bash
# CPU: aumentar swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# GPU: reduzir batch size ou usar CPU
export USE_FAISS_GPU=false
```

## 📚 Referências

- [Conda Docs](https://docs.conda.io/)
- [FAISS GPU](https://github.com/facebookresearch/faiss/wiki/Faiss-on-the-GPU)
- [PyTorch CUDA](https://pytorch.org/get-started/locally/)
- [WSL2 CUDA](https://docs.nvidia.com/cuda/wsl-user-guide/)
- [Docker GPU](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)

---

Para mais detalhes operacionais, consulte [SANITY.md](SANITY.md).
