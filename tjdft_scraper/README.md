# TJDFT Scraper (jurisdf)

Coleta jurisprudência do TJDFT pela API pública usada pelo site https://jurisdf.tjdft.jus.br/.
Não precisa de navegador: são requisições HTTP simples (`requests`).

Tema configurado: **LGPD, sistemas de CFTV e câmeras privadas instaladas por moradores em condomínios**
(`configs/queries_cftv_lgpd.txt`).

## Uso

```bash
# da raiz do repositório
python3 tjdft_scraper/manage.py crawl                     # todas as queries do arquivo padrão
python3 tjdft_scraper/manage.py crawl --resume            # continua de onde parou
python3 tjdft_scraper/manage.py crawl --query "cftv|cftv condominio" --limit 5 --out /tmp/teste.jsonl
python3 tjdft_scraper/manage.py status                    # contagens por tema/base/área e hits por query
```

| Opção | Descrição |
|---|---|
| `--queries` | Arquivo com linhas `tema\|query` (padrão `configs/queries_cftv_lgpd.txt`) |
| `--query` | Query avulsa (`tema\|query` ou só `query`); pode repetir; ignora `--queries` |
| `--limit N` | Máximo de registros gravados nesta execução |
| `--no-full-text` | Não busca o inteiro teor (só ementa) |
| `--download-pdf` | Baixa o PDF do inteiro teor em `data/pdf/{uuid}.pdf` |
| `--keep-html` | Mantém `inteiro_teor_html` no JSONL |
| `--sinonimos true\|false` | Expansão de sinônimos do jurisdf (padrão `true`) |
| `--delay` | Intervalo mínimo entre requisições em segundos (padrão 1.0; abaixo disso a API responde 429) |
| `--resume` / `--overwrite` | Continuar ou descartar a coleta anterior (sem nenhum dos dois, não sobrescreve) |

## Como funciona

1. **Busca**: para cada query, pagina `POST /api/v1/pesquisa` (máximo 40 por página) e monta
   `data/<saida>_search_index.json` (uuid → temas, queries, dados da listagem). Checkpoint a cada query.
   Registros em segredo de justiça são ignorados.
2. **Inteiro teor**: para cada uuid ainda não gravado, busca o registro completo
   (`termosAcessorios: [{campo: "uuid"}]`, `retornaInteiroTeor: true`) e grava uma linha no JSONL.
3. **Sincronização**: registros que aparecem em várias queries têm `matched_queries`/`topics` atualizados.

Estatísticas por query ficam em `data/<saida>_stats.json`.

## Sintaxe de busca do jurisdf

- Palavras soltas são combinadas com **E** (com sinônimos e radicais), o que pode trazer muito ruído.
- `"frase exata"` entre aspas; conectivos `e`, `ou`, `não`, parênteses.
- `PROX5` (até 5 palavras de distância, qualquer ordem): funciona entre palavras simples
  (`câmera PROX5 vizinho`); com grupos entre parênteses a API retorna HTTP 500.

## Formato de saída (`data/tjdft_cftv_lgpd.jsonl`)

Compatível com `DBVECTOR/src/tools/tratamento_dados.py` e `src/schema.py:Doc`:

| Campo | Origem |
|---|---|
| `id` | `tjdft:{uuid}` (um processo pode ter várias decisões) |
| `case_number` | número do processo |
| `content` | ementa + inteiro teor |
| `court` / `tribunal` | `TJDFT` |
| `date` / `publication_date` | data de julgamento / publicação (ISO) |
| `relator`, `orgao_julgador`, `decision`, `numero_acordao` | metadados da decisão |
| `base` / `subbase` | `acordaos`, `acordaos-tr`, `decisoes-monocraticas`, `decisoes-presidencia` |
| `legal_area` | `Penal` se o órgão julgador for criminal, senão `Cível` |
| `cluster_name` / `topics` / `matched_queries` | tema principal, todos os temas e queries que encontraram o registro |
| `url` | link público da decisão no jurisdf |

A coleta **não** indexa no FAISS. Para indexar depois:

```bash
cd DBVECTOR
# depois do crawl (nunca durante): corrige registros gravados antes de mudanças na normalização
python3 ../tjdft_scraper/manage.py reclean
# --id-field id: um processo pode ter várias decisões (case_number repetido é esperado)
python -m src.tools.validate_data --input ../tjdft_scraper/data/tjdft_cftv_lgpd.jsonl --id-field id
# append_faiss em vez de build_faiss: o build carrega todos os metadados e estoura a memória
systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 \
  venv/bin/python -m src.tools.append_faiss --input ../tjdft_scraper/data/tjdft_cftv_lgpd.jsonl
```
