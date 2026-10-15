# Legislação Scraper (Planalto)

Baixa leis federais do Planalto, remove o texto revogado e divide cada lei por artigo,
gerando um JSONL pronto para `DBVECTOR/src/pipelines/build_faiss.py`.

Leis configuradas em `configs/leis.json`: CF/88 (+ ADCT), Código Civil, Código Penal, CPC, CPP, CDC,
ECA, LGPD, Lei 4.591/64 (Condomínios) e LEP.

## Uso

```bash
python3 legislacao_scraper/manage.py fetch                 # baixa (ou usa cache em data/raw/) e processa todas
python3 legislacao_scraper/manage.py fetch --only LGPD,CC  # só algumas; mantém as demais no JSONL
python3 legislacao_scraper/manage.py fetch --refresh       # ignora o cache e baixa de novo
python3 legislacao_scraper/manage.py stats                 # artigos e registros por lei
python3 legislacao_scraper/manage.py show CC 1277          # imprime um artigo (ex.: 5-A para "Art. 5º-A")
```

Requer `beautifulsoup4` e `lxml` (listados no `pyproject.toml` da raiz).

## Processamento

- Páginas em windows-1252 sem charset declarado; o Planalto derruba conexões cujo User-Agent
  não começa com `Mozilla/5.0`.
- Texto revogado (`<strike>`, `<s>`, `<del>`, `line-through`) é removido das versões compiladas.
- Anotações como `(Redação dada pela Lei ...)`, `(Incluído pela ...)`, `(Vide ...)` e links `Vigência` são removidos;
  artigos inteiramente revogados/vetados são descartados.
- Artigos citados entre aspas (alterações em outras leis) e numeração fora de ordem não iniciam artigo novo.
- A hierarquia (Parte/Livro/Título/Capítulo/Seção/Subseção) vai em `meta.hierarquia`, e os dois níveis mais
  específicos entram no texto (ajuda a busca, ex.: "Dos Direitos de Vizinhança").
- Artigos com mais de 1.500 caracteres são divididos em partes de ~1.200 (o embedder trunca textos longos).

## Formato de saída (`data/legislacao.jsonl`)

```json
{
  "id": "lei:cc:art-1277",
  "text": "Código Civil (Lei 10.406/2002) – Art. 1.277\nCAPÍTULO V – Dos Direitos de Vizinhança / Seção I – Do Uso Anormal da Propriedade\nO proprietário ...",
  "title": "CC, Art. 1.277",
  "code": "CC",
  "article": "1277",
  "meta": {"tipo": "legislacao", "source": "planalto", "law_name": "...", "article_label": "Art. 1.277",
           "hierarquia": ["..."], "part": 1, "parts": 1, "url": "...", "fetched_at": "..."}
}
```

## Indexar no FAISS

Use `src.tools.append_faiss`, que acrescenta os documentos ao índice existente com pouca memória.
O `build_faiss` carrega os ~724 mil metadados como objetos Python e passa de 20 GB ao salvar
(foi morto por falta de memória numa máquina de 29 GB). Faça backup antes:

```bash
cd DBVECTOR
cp -p data/indexes/faiss/index.faiss data/indexes/faiss/metadata.parquet <pasta-de-backup>/
systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 \
  venv/bin/python -m src.tools.append_faiss --input ../legislacao_scraper/data/legislacao.jsonl
```

Pico medido: ~13,4 GB, ~70 s. O script recusa ids que já estão no índice; para reindexar, restaure o backup primeiro.
