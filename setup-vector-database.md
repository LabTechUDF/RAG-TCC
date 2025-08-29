# FAISS Environment Setup with pyenv + Anaconda

This guide shows how to install and configure an environment with **pyenv**, **Anaconda**, and **FAISS-CPU**.

---

## 1. Install Anaconda with pyenv
```bash
pyenv install anaconda3-2024.10-1
````

Set it locally in your project:

```bash
pyenv local anaconda3-2024.10-1
```

---

## 2. Initialize Conda

For Zsh:

```bash
conda init zsh
```

Restart your shell:

```bash
exec zsh
```

---

## 3. Create a dedicated FAISS environment

```bash
conda create -n faiss python=3.12
conda activate faiss
```

---

## 4. Install FAISS-CPU

```bash
conda install -c pytorch faiss-cpu
```

---

## 5. Test installation

```bash
python -c "import faiss; print(faiss.__version__)"
```

You should see something like:

```
1.9.0
```

✅ Done! You now have a clean FAISS-CPU environment running under pyenv + Anaconda.
