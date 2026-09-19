"""
Dados abertos do STJ (dadosabertos.web.stj.jus.br): íntegras de decisões/acórdãos e espelhos de acórdãos.

Fluxo: ckan (lista arquivos) -> sync (baixa, incremental) -> build (SQLite + FTS5) -> search (qualquer termo).
Não usa o SCON, que fica atrás de um desafio do Cloudflare.
"""
