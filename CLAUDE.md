# RAG-TCC — guia para agentes

Corpus jurídico brasileiro (jurisprudência + legislação) com busca vetorial, busca textual e um servidor MCP
somente leitura. Documentação por parte: `rag_mcp/README.md`, `stj_scraper/OPEN_DATA.md`, `tjdft_scraper/README.md`.

## Serviços (systemd --user, linger ligado)

| Serviço | Porta | O que é |
|---|---|---|
| `rag-tcc-api.service` | 127.0.0.1:8000 | API do DBVECTOR (FAISS, somente leitura), `MemoryMax=16G` |
| `rag-tcc-mcp.service` | 127.0.0.1:8765 | Servidor MCP Streamable HTTP, `MemoryMax=2G` |

- Runners em `~/.rag-tcc-api/run_api.sh` e `run_mcp.sh`; tokens em `~/.rag-tcc-api/{token,mcp_token}` (0600).
- O MCP também é publicado em `https://mcp.dwcorp.com.br/k/<segredo>/rag/mcp` (nginx nesta máquina injeta o Bearer).
  **O ChatGPT do dono usa esse endereço.** Não reinicie os serviços sem avisar: derruba a sessão dele.
- Reiniciar a API custa ~3 min (carrega o índice). `systemctl --user restart rag-tcc-{api,mcp}.service`.

## Dados

| Fonte | Arquivo / banco | Observação |
|---|---|---|
| TJDFT coletado | `tjdft_scraper/data/*.jsonl` | 4.645 documentos; temas LGPD, CFTV, câmeras em condomínio, multa |
| Legislação | `legislacao_scraper/data/legislacao.jsonl` | 6.135 registros por artigo (CF/88, ADCT, CC, CP, CPC, CPP, CDC, ECA, LGPD, LEP, Lei 4.591/64) |
| STJ dados abertos | `stj_scraper/data/open_data/stj_open_data.sqlite` | 13,9 GB, fora do git; íntegras 2021+, espelhos 2022+ |
| Índice FAISS | `DBVECTOR/data/indexes/faiss/` | 735.194 vetores (MiniLM 384d, `IndexIDMap2(IndexFlatIP)`) |
| Exports para o agente jurídico | `~/rag-tcc-exports/juridico/` | fora do repositório |

## Como consultar

Prefira o MCP (`rag_mcp/README.md`) — envelope com proveniência e `verify_quote`. Direto na API:

```bash
TOKEN="$(cat ~/.rag-tcc-api/token)"
curl -s -X POST http://127.0.0.1:8000/search -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"q":"câmera do vizinho no condomínio","k":10,"id_prefix":"lei:"}'
curl -s http://127.0.0.1:8000/doc/lei:lgpd:art-7-p1 -H "Authorization: Bearer $TOKEN"
```

`id_prefix`/`court` filtram **dentro** do FAISS (busca exata no subconjunto); `k` vai até 100.

## Regras que já custaram caro

- **Nunca commitar `~/.agents`** (árvore compartilhada de outros times) nem tokens, nem `data/open_data/`.
- **Nunca indexar FAISS no processo da API**: `build_faiss` estoura a memória da máquina (29 GB).
  Use `python -m src.tools.append_faiss --memory-budget-gb 8`, que faz streaming por row group.
  A API roda com `FAISS_LAZY_METADATA=true` (metadados Arrow mapeados, somente leitura).
- **Não contornar o Cloudflare do SCON.** Inteiros teores anteriores a 2021 vêm do navegador do dono
  (`stj_scraper/scon_fetch.py`, com pessoa no circuito) — ver `stj-open-data-search` na memória.
- Antes de rodar o pipeline pesado, confirme a RAM livre: o alvo combinado é 8–16 GB.
- Dados coletados grandes (`*.jsonl`) hoje **são versionados**; foi apontado como problema na revisão do PR #17.

## Pendências conhecidas

- Correções da revisão do PR #17 (entre elas `ART_RE` transformando "Art. 13 - O" em 13-O, o que exige
  regerar `legislacao.jsonl` e reindexar esses registros).
- `court` só filtra documentos cujo campo está preenchido nos metadados (o corpus antigo em geral não tem).
