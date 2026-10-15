# rag_mcp — MCP HTTP server (read-only) for the RAG-TCC legal corpus

A single MCP server over **Streamable HTTP** (stateless, JSON responses). ChatGPT (connectors / developer mode), Claude and any other
MCP client can use it to query everything collected in this repository. It has no write tools.

| Source | Where it comes from | Tools |
|---|---|---|
| Collected TJDFT decisions (LGPD, CFTV, cameras, condominium fines) | `tjdft_scraper/data/*.jsonl` | `tjdft_search`, `get_doc` |
| Live TJDFT (the whole court) | jurisdf public API | `tjdft_live_search`, `tjdft_live_get` |
| Official TJDFT `.doc` originals (converted) | `$RAG_EXPORTS/tjdft_fulltext_originals.jsonl` | `get_doc("tjdft:<uuid>:original")` |
| Planalto legislation, by article | `legislacao_scraper/data/legislacao.jsonl` | `get_law_article`, `list_laws` |
| STJ open data (full texts 2021+, espelhos 2022+) | `stj_scraper/data/open_data/stj_open_data.sqlite` | `stj_search`, `stj_espelhos_by_processo`, `get_doc` |
| STJ inteiro teor (SCON PDFs, downloaded by hand) | `$RAG_EXPORTS/stj_scon/` | `get_doc("stj:scon:<num_registro>")` |
| FAISS vector index (all of the above plus older material) | DBVECTOR API (`/search`, `/doc/{id}`) | `semantic_search`, `get_doc` |
| Everything | — | `search` + `fetch` (the shape ChatGPT deep research expects), `verify_quote`, `sources_status` |

Every document comes back in the same envelope:
- `id`, `court`, `processo`, `orgao`, `relator`, `data_julgamento`, `data_publicacao`, `source_url`;
- `text_kind`: `integra` | `ementa` | `espelho` | `original_doc` | `lei` | `informativo_jurisprudencia` | `jurisprudencia_em_foco` | `indexed_text`;
- `text_sha256`, computed over the **full** text, and `text_chars`;
- the requested slice: `offset`, `returned_chars`, `has_more`, `next_offset`, `text`.

An unknown id is an explicit error (`not_found: ...`). A document that exists but has no text returns `text_empty: true` with a note explaining why.

`verify_quote(doc_id, quote_text)` returns:
- `exact_match` with character offsets in the full text;
- `normalized_match`, which ignores case, accents, curly quotes and extra whitespace;
- the same `text_sha256` that `get_doc` reports.

## Running

The DBVECTOR API has to be up first (127.0.0.1:8000). The server reads its token from `~/.rag-tcc-api/token`.

```bash
cd rag_mcp
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python "mcp>=1.20,<2" httpx uvicorn requests
.venv/bin/python server.py --host 127.0.0.1 --port 8765 [--allowed-host <public-tunnel-host>]
```

- On first start it builds `cache/tjdft.sqlite` (FTS5 over the TJDFT JSONL), and rebuilds it whenever a JSONL changes.
- It uses about 100 MB of RAM.
- Put it behind an HTTPS tunnel or reverse proxy and pass the public hostname with `--allowed-host`. The server checks the Host
  header (DNS-rebinding protection) and returns 421 for unknown hosts.

## Authentication

The token lives in `~/.rag-tcc-api/mcp_token`. It is created with mode 0600 when missing, and it is separate from the API token. There are two equivalent ways to send it:

1. The header `Authorization: Bearer <token>` on `https://<host>/mcp`, for connectors with an "API key" option, Claude Code and scripts.
2. The secret URL `https://<host>/k/<token>/mcp`, for clients that can't send headers (a no-auth connector). Treat this URL like a password.

The server never writes the token to its log. `/health` is the only public route.

## Connecting

- **ChatGPT**: Settings → Connectors → Developer mode → create a connector.
  - URL: `https://<host>/k/<token>/mcp` with *No authentication*, or `https://<host>/mcp` with an API key / Bearer.
  - Without developer mode, ChatGPT only uses `search` and `fetch`.
- **Claude Code**: `claude mcp add --transport http rag-tcc https://<host>/mcp --header "Authorization: Bearer <token>"`
  (or `http://127.0.0.1:8765/mcp` on the same machine).

## Coverage limits

- The collected TJDFT corpus covers only the crawled topics; use `tjdft_live_*` for the rest of the court.
- STJ open data has no full texts before 2021 and no espelhos before 2022. SCON sits behind Cloudflare and is not queried.
- In `semantic_search`:
  - `id_prefix` and `court` filters run inside FAISS, with exact search over that subset;
  - date filters are applied to the 100 nearest neighbours;
  - `court` only matches documents whose `court` field is filled in the metadata.
