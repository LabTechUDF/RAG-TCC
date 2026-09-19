# STJ — dados abertos (busca de qualquer termo)

Coleta e busca local sobre os dados abertos do STJ (`dadosabertos.web.stj.jus.br`), que não ficam atrás do
Cloudflare (o SCON fica). Nada aqui tenta contornar o desafio do SCON.

| Conjunto | Conteúdo | Período | Tamanho |
|---|---|---|---|
| Íntegras de decisões terminativas e acórdãos (DJ) | metadados diários (tipo, processo, registro, ministro, teor, assuntos CNJ) + ZIP com o texto integral | 2021-01 → hoje | ~10,4 GB ZIPs + 1,7 GB metadados (~28 GB de texto) |
| Espelhos de acórdãos (10 órgãos) | ementa, decisão, legislação, jurisprudência citada, notas, termos auxiliares, tese | 2022-05 → hoje | ~0,56 GB |

Decisões anteriores a 2021 (ex.: REsp 1.365.279/SP, de 2015) **não estão** nos dados abertos.

## Uso

```bash
cd stj_scraper
# 1) baixar (incremental; repetir para atualizar). Recorte opcional por data/órgão.
python3 manage.py open-data sync                                   # tudo (~13 GB)
python3 manage.py open-data sync --since 2025-06-01 --until 2025-06-30 --what integras
python3 manage.py open-data sync --what espelhos --orgaos quarta-turma,terceira-turma

# 2) indexar no SQLite FTS5 (incremental: só arquivos novos ou alterados)
python3 manage.py open-data build

# 3) buscar
python3 manage.py open-data search '"multa condominial" notificação prévia' --scope espelhos --limit 20
python3 manage.py open-data search 'condomínio NEAR(câmera vizinho, 10)' --tipo ACÓRDÃO --desde 2023-01-01
python3 manage.py open-data search 1.365.279                        # tokens com pontuação viram frase
python3 manage.py open-data text 396858957                          # texto integral por SeqDocumento
python3 manage.py open-data status
```

Sintaxe: palavras soltas = todas precisam aparecer; `"frase"`, `OR`, `NOT`, `NEAR(a b, N)`, `prefixo*`.
Acentos e maiúsculas são ignorados.

## Onde fica

- `data/open_data/raw/` — arquivos baixados + `manifest.json` (gitignored)
- `data/open_data/stj_open_data.sqlite` — `integras_docs` + `integras_fts` (FTS5 sem conteúdo; o texto é lido do
  ZIP), `espelhos` + `espelhos_fts`, `ingested` (controle incremental)

Memória: o build processa um dia/arquivo por vez (poucos centenas de MB). Rode cargas grandes destacadas e com
limite, ex.: `systemd-run --user --scope -p MemoryMax=4G python3 manage.py open-data build`.
