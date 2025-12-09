---
name: rag-tcc-corpus
description: Query the RAG-TCC Brazilian legal corpus — TJDFT case law, Planalto legislation by article, STJ open data (full texts 2021+, espelhos 2022+) and the FAISS vector index — through the read-only MCP server on 127.0.0.1:8765 or the DBVECTOR API on 127.0.0.1:8000. Use when asked to find case law, statutes or court decisions about LGPD, CFTV/cameras, condominiums, or to verify a legal quote or fetch a decision's full text.
allowed-tools:
  - bash_tool
---

# RAG-TCC corpus

## Overview

Two read-only entry points to the same data. Prefer MCP: every document carries provenance and a sha256
over the full text, so quotes can be verified.

- **MCP** (`http://127.0.0.1:8765/mcp`, Streamable HTTP, 13 tools) — register with
  `claude mcp add --transport http rag-tcc http://127.0.0.1:8765/mcp --header "Authorization: Bearer $(cat ~/.rag-tcc-api/mcp_token)"`.
- **HTTP API** (`http://127.0.0.1:8000`) — `Authorization: Bearer $(cat ~/.rag-tcc-api/token)`.

Check first: `curl -s http://127.0.0.1:8765/health` and `curl -s http://127.0.0.1:8000/health`.
If either is down, say so — **do not restart them**; the owner's ChatGPT connects to the same MCP service
through `https://mcp.dwcorp.com.br`, and a restart drops their session.

## Choosing a tool

| Need | Tool |
|---|---|
| Concept, no exact words ("câmera do vizinho viola privacidade") | `semantic_search` (`id_prefix`, `court` filter inside FAISS; `k` ≤ 50) |
| Exact terms, with a total count | `tjdft_search` (collected TJDFT) · `stj_search` (STJ open data) |
| A statute article | `get_law_article(code, article)` — `CC`/`1.277`, `CF/88`/`5`, `LGPD`/`7`; `list_laws` for what exists |
| Full text of a known document | `get_doc(id, offset, limit)` — long texts come in slices |
| TJDFT beyond the crawled topics | `tjdft_live_search` / `tjdft_live_get` (public jurisdf API, ~1 req/s) |
| Every espelho of a case | `stj_espelhos_by_processo("REsp 1921653")` |
| Is this quote real? | `verify_quote(doc_id, quote_text)` |
| What is covered | `sources_status` |

`search` and `fetch` also exist, in the shape ChatGPT deep research expects.

## Document ids

`tjdft:<uuid>` · `tjdft:<uuid>:original` (text of the official .doc) · `lei:<slug>:art-<n>[-p<k>]` ·
`stj:espelho:<id>` · `stj:integra:<seq>` · `stj:scon:<num_registro>` · anything else = vector index.

Long articles are split: `lei:lgpd:art-7` does not exist, `lei:lgpd:art-7-p1..p3` do. `get_law_article`
handles that for you.

## Rules when citing

1. Quote only from text returned by `get_doc`/`fetch`, never from a snippet.
2. Run `verify_quote` before presenting a quotation; report `exact_match` and the offsets.
3. Give `source_url` and say which `text_kind` it is — an `ementa` or `espelho` is not the full decision.
4. Coverage gaps to state plainly instead of guessing around: collected TJDFT covers only the crawled
   topics (use `tjdft_live_*` otherwise); STJ open data has no full texts before 2021, no espelhos before
   2022; SCON is behind Cloudflare and is never queried.

## API fallback

```bash
TOKEN="$(cat ~/.rag-tcc-api/token)"
curl -s -X POST http://127.0.0.1:8000/search -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"q":"multa condominial câmera","k":10,"id_prefix":"tjdft:"}'
curl -s "http://127.0.0.1:8000/doc/tjdft:<uuid>" -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://127.0.0.1:8000/stj/search -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"q":"condomínio câmera","scope":"integras","limit":5}'
```

Never put either token on the bus, in a commit, or in a log line.
