"""
Servidor MCP (Streamable HTTP) somente leitura sobre o corpus jurídico do RAG-TCC.

Fontes:
- TJDFT coletado (tjdft_scraper/data/*.jsonl) e originais .doc convertidos (exports);
- TJDFT ao vivo (API pública do jurisdf: busca e registro completo);
- legislação do Planalto por artigo (legislacao_scraper/data/legislacao.jsonl);
- STJ dados abertos (SQLite FTS5: íntegras 2021+, espelhos 2022+) e inteiros teores do SCON baixados manualmente;
- índice vetorial FAISS (via API do DBVECTOR em 127.0.0.1:8000: /search e /doc/{id}).

Todo documento sai no mesmo envelope: id, court, processo, orgao, relator, data_julgamento, data_publicacao,
source_url, text_kind, text_sha256 (do texto completo) e o trecho pedido (offset/limit).

Autenticação (uma das duas):
- header "Authorization: Bearer <token>" em /mcp;
- URL secreta /k/<token>/mcp (para clientes que não enviam headers, como conectores sem OAuth).
O token fica em ~/.rag-tcc-api/mcp_token (criado com permissão 0600 se não existir).

    .venv/bin/python server.py --host 127.0.0.1 --port 8765 [--allowed-host exemplo.trycloudflare.com]
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import unicodedata
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import anyio
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EXPORTS = Path(os.getenv("RAG_EXPORTS", "/home/tupan/rag-tcc-exports/juridico"))
API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000")
API_TOKEN_FILE = Path(os.getenv("RAG_API_TOKEN_FILE", "~/.rag-tcc-api/token")).expanduser()
MCP_TOKEN_FILE = Path(os.getenv("RAG_MCP_TOKEN_FILE", "~/.rag-tcc-api/mcp_token")).expanduser()
STJ_DB = Path(os.getenv("STJ_OPEN_DATA_DB", str(REPO / "stj_scraper" / "data" / "open_data" / "stj_open_data.sqlite")))
TJDFT_FILES = [REPO / "tjdft_scraper" / "data" / "tjdft_cftv_lgpd.jsonl", REPO / "tjdft_scraper" / "data" / "tjdft_condo_multa.jsonl"]
LEI_FILE = REPO / "legislacao_scraper" / "data" / "legislacao.jsonl"
TJDFT_ORIGINALS = EXPORTS / "tjdft_fulltext_originals.jsonl"
SCON_EXPORT = EXPORTS / "stj_scon" / "stj_scon_inteiro_teor.jsonl"
CACHE_DIR = HERE / "cache"
COUNT_CAP = 10000
DEFAULT_LIMIT = 20000

for extra in (REPO / "stj_scraper", REPO / "tjdft_scraper"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
from stj_scraper.open_data import search as stj  # noqa: E402
from tjdft_scraper.client import TjdftClient  # noqa: E402
from tjdft_scraper.normalize import clean_text, iso_date, record_url  # noqa: E402


class NotFound(ValueError):
    pass


# ---------------------------------------------------------------- envelope e utilidades
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def envelope(doc: dict, offset: int = 0, limit: Optional[int] = DEFAULT_LIMIT) -> dict:
    """Recorta o texto e acrescenta sha256/tamanho do texto completo."""
    text = doc.get("text") or ""
    offset = max(0, min(int(offset or 0), len(text)))
    part = text[offset:offset + limit] if limit else text[offset:]
    end = offset + len(part)
    out = {k: doc.get(k) for k in ("id", "title", "court", "processo", "orgao", "relator", "data_julgamento",
                                   "data_publicacao", "source_url", "text_kind")}
    out.update({
        "text_sha256": sha256(text), "text_chars": len(text), "text_empty": not text,
        "offset": offset, "returned_chars": len(part), "has_more": end < len(text), "next_offset": end if end < len(text) else None,
        "text": part, "metadata": doc.get("metadata") or {},
    })
    if not text:
        out["metadata"] = {**out["metadata"], "note": doc.get("empty_note") or "documento existe, mas não há texto disponível"}
    return out


def scon_search_url(processo: Optional[str]) -> Optional[str]:
    return f"https://scon.stj.jus.br/SCON/pesquisar.jsp?b=ACOR&livre={quote(processo)}" if processo else None


def scon_inteiro_teor_url(num_registro: Optional[str], data_publicacao: Optional[str]) -> Optional[str]:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", data_publicacao or "")
    if not num_registro or not m:
        return None
    return (f"https://scon.stj.jus.br/SCON/GetInteiroTeorDoAcordao?num_registro={num_registro}"
            f"&dt_publicacao={m.group(3)}/{m.group(2)}/{m.group(1)}")


QUOTE_MAP = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "})


def fold_with_map(text: str) -> tuple[str, list[int]]:
    """Minúsculas, sem acento, aspas/travessões uniformes e espaços colapsados; guarda o índice original de cada caractere."""
    out, index_map, prev_space = [], [], True
    for i, ch in enumerate(text):
        for part in unicodedata.normalize("NFKD", ch.translate(QUOTE_MAP).casefold()):
            if unicodedata.combining(part):
                continue
            if part.isspace():
                if prev_space:
                    continue
                part, prev_space = " ", True
            else:
                prev_space = False
            out.append(part)
            index_map.append(i)
    return "".join(out), index_map


# ---------------------------------------------------------------- TJDFT coletado (cache SQLite FTS5 dos JSONL)
_tjdft_lock = threading.Lock()


def tjdft_db() -> sqlite3.Connection:
    """Abre (e reconstrói quando os JSONL mudam) o cache com offsets e busca textual do TJDFT coletado."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / "tjdft.sqlite"
    sources = [p for p in TJDFT_FILES if p.exists()]
    signature = json.dumps([[str(p), p.stat().st_size, int(p.stat().st_mtime)] for p in sources])
    with _tjdft_lock:
        if path.exists():
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
            row = con.execute("SELECT value FROM info WHERE key = 'signature'").fetchone()
            if row and row[0] == signature:
                return con
            con.close()
        tmp = path.with_suffix(".tmp")
        tmp.unlink(missing_ok=True)
        con = sqlite3.connect(tmp)
        con.executescript("""
            CREATE TABLE info(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE docs(rowid INTEGER PRIMARY KEY, id TEXT UNIQUE, file TEXT, offset INTEGER, title TEXT, processo TEXT,
                              orgao TEXT, relator TEXT, data_julgamento TEXT, data_publicacao TEXT, date TEXT,
                              document_type TEXT, base TEXT, subbase TEXT, text_chars INTEGER);
            CREATE VIRTUAL TABLE docs_fts USING fts5(title, ementa, content, tokenize = 'unicode61 remove_diacritics 2');
        """)
        seen = set()
        for source in sources:
            with open(source, "rb") as f:
                offset = f.tell()
                for line in iter(f.readline, b""):
                    if line.strip():
                        r = json.loads(line)
                        if r["id"] not in seen:
                            seen.add(r["id"])
                            cur = con.execute(
                                "INSERT INTO docs(id, file, offset, title, processo, orgao, relator, data_julgamento, data_publicacao,"
                                " date, document_type, base, subbase, text_chars) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (r["id"], str(source), offset, r.get("title"), r.get("case_number"), r.get("orgao_julgador"),
                                 r.get("relator"), r.get("decision_date"), r.get("publication_date"), r.get("date"),
                                 r.get("document_type"), r.get("base"), r.get("subbase"), len(r.get("content") or "")))
                            con.execute("INSERT INTO docs_fts(rowid, title, ementa, content) VALUES (?,?,?,?)",
                                        (cur.lastrowid, r.get("title"), r.get("ementa"), r.get("content")))
                    offset = f.tell()
        con.execute("INSERT INTO info VALUES ('signature', ?)", (signature,))
        con.commit()
        con.close()
        os.replace(tmp, path)
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)


@functools.lru_cache(maxsize=1)
def tjdft_originals() -> dict:
    if not TJDFT_ORIGINALS.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l) for l in TJDFT_ORIGINALS.read_text(encoding="utf-8").splitlines() if l.strip()}


def tjdft_text_kind(r: dict) -> str:
    dtype = r.get("document_type")
    if dtype in ("acordao", "decisao") or (r.get("base") or "").startswith(("acordaos", "decisoes")):
        return "integra" if r.get("possui_inteiro_teor") and len(r.get("content") or "") > len(r.get("ementa") or "") else "ementa"
    return dtype or "outro"


def load_tjdft(doc_id: str) -> dict:
    con = tjdft_db()
    try:
        row = con.execute("SELECT file, offset FROM docs WHERE id = ?", (doc_id,)).fetchone()
    finally:
        con.close()
    if not row:
        raise NotFound(f"not_found: {doc_id} não está no TJDFT coletado (use tjdft_live_get com o uuid para buscar direto no TJDFT)")
    with open(row[0], "rb") as f:
        f.seek(row[1])
        r = json.loads(f.readline())
    meta = {k: r.get(k) for k in ("numero_acordao", "base", "subbase", "document_type", "codigo_classe_cnj", "decision",
                                  "local_publicacao", "turma_recursal", "possui_inteiro_teor", "uuid", "topics",
                                  "matched_queries", "legal_area", "source", "collected_at", "jurisprudencia_em_foco")
            if r.get(k) not in (None, "", [])}
    meta["ementa_chars"] = len(r.get("ementa") or "")
    if doc_id in tjdft_originals():
        meta["original_doc_id"] = f"{doc_id}:original"
    return {"id": r["id"], "title": r.get("title"), "court": "TJDFT", "processo": r.get("case_number"),
            "orgao": r.get("orgao_julgador"), "relator": r.get("relator"), "data_julgamento": r.get("decision_date"),
            "data_publicacao": r.get("publication_date"), "source_url": r.get("url"), "text_kind": tjdft_text_kind(r),
            "text": r.get("content") or "", "metadata": meta}


def load_tjdft_original(doc_id: str) -> dict:
    base_id = doc_id[: -len(":original")]
    r = tjdft_originals().get(base_id)
    if not r:
        raise NotFound(f"not_found: não há original .doc convertido para {base_id} (existem {len(tjdft_originals())})")
    return {"id": doc_id, "title": f"TJDFT – Acórdão {r.get('acordao')} – Processo {r.get('processo')} (original .doc)",
            "court": "TJDFT", "processo": r.get("processo"), "orgao": r.get("orgao"), "relator": r.get("relator"),
            "data_julgamento": r.get("data"), "data_publicacao": None, "source_url": r.get("source_url"),
            "text_kind": "original_doc", "text": r.get("text") or "",
            "metadata": {k: r.get(k) for k in ("acordao", "page_url", "original_format", "original_sha256", "completeness_verdict",
                                               "markers_in_original", "stored_words_found_in_original",
                                               "original_words_not_in_stored")}}


# ---------------------------------------------------------------- legislação
@functools.lru_cache(maxsize=1)
def laws() -> tuple[dict, dict]:
    by_id, by_article = {}, {}
    with open(LEI_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                by_id[r["id"]] = r
                by_article.setdefault((r["id"].split(":")[1], r["article"].upper()), []).append(r)
    for parts in by_article.values():
        parts.sort(key=lambda r: r["meta"].get("part") or 1)
    return by_id, by_article


def law_slug(code: str) -> str:
    by_id, _ = laws()
    wanted = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", code).encode("ascii", "ignore").decode().lower())
    aliases = {"cf": "cf88", "constituicao": "cf88", "constituicaofederal": "cf88", "codigocivil": "cc", "codigopenal": "cp",
               "4591": "lei459164", "lei4591": "lei459164", "condominios": "lei459164", "13709": "lgpd", "lei13709": "lgpd",
               "8078": "cdc", "codigodedefesadoconsumidor": "cdc", "cpc2015": "cpc"}
    wanted = aliases.get(wanted, wanted)
    for slug in {i.split(":")[1] for i in by_id}:
        if re.sub(r"[^a-z0-9]", "", slug) == wanted:
            return slug
    raise NotFound(f"not_found: lei {code!r} não coletada; disponíveis: {sorted({r['code'] for r in by_id.values()})}")


def load_law(doc_id: str) -> dict:
    r = laws()[0].get(doc_id)
    if not r:
        raise NotFound(f"not_found: {doc_id}; ids têm a forma lei:<slug>:art-<n>[-p<k>] (veja get_law_article/list_laws)")
    meta = r.get("meta") or {}
    return {"id": r["id"], "title": r.get("title"), "court": None, "processo": None, "orgao": None, "relator": None,
            "data_julgamento": None, "data_publicacao": None, "source_url": meta.get("url"), "text_kind": "lei",
            "text": r.get("text") or "",
            "metadata": {"code": r.get("code"), "article": r.get("article"), **{k: v for k, v in meta.items() if k != "url"}}}


# ---------------------------------------------------------------- STJ
def stj_con() -> sqlite3.Connection:
    if not STJ_DB.exists():
        raise NotFound(f"STJ open-data index missing ({STJ_DB})")
    con = sqlite3.connect(f"file:{STJ_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


ESPELHO_SECTIONS = [("ementa", "EMENTA"), ("decisao", "ACÓRDÃO / DECISÃO"), ("tese_juridica", "TESE JURÍDICA"), ("tema", "TEMA"),
                    ("notas", "NOTAS"), ("informacoes_complementares", "INFORMAÇÕES COMPLEMENTARES"),
                    ("referencias_legislativas", "REFERÊNCIAS LEGISLATIVAS"), ("jurisprudencia_citada", "JURISPRUDÊNCIA CITADA"),
                    ("acordaos_similares", "ACÓRDÃOS SIMILARES"), ("termos_auxiliares", "TERMOS AUXILIARES")]


def espelho_doc(row: dict) -> dict:
    processo = " ".join(v for v in (row.get("sigla_classe"), row.get("numero_processo")) if v)
    text = "\n\n".join(f"{label}\n{row[key].strip()}" for key, label in ESPELHO_SECTIONS if row.get(key) and row[key].strip())
    return {"id": f"stj:espelho:{row['id']}", "title": f"STJ – {processo} – {row.get('orgao') or ''} (espelho)".replace(" –  (", " – ("),
            "court": "STJ", "processo": processo, "orgao": row.get("orgao"), "relator": row.get("relator"),
            "data_julgamento": row.get("data_decisao"), "data_publicacao": row.get("data_publicacao"),
            "source_url": scon_search_url(processo), "text_kind": "espelho", "text": text,
            "metadata": {"num_registro": row.get("num_registro"), "tipo": row.get("tipo"), "descricao_classe": row.get("descricao_classe"),
                         "fonte": row.get("fonte"), "open_data_source_key": row.get("source_key"),
                         "scon_inteiro_teor_url": scon_inteiro_teor_url(row.get("num_registro"), row.get("data_publicacao")),
                         "sections": [label for key, label in ESPELHO_SECTIONS if row.get(key)]}}


def load_stj_espelho(doc_id: str) -> dict:
    con = stj_con()
    try:
        row = con.execute("SELECT * FROM espelhos WHERE id = ?", (doc_id.rsplit(":", 1)[1],)).fetchone()
    finally:
        con.close()
    if not row:
        raise NotFound(f"not_found: {doc_id}")
    return espelho_doc(dict(row))


def load_stj_integra(doc_id: str) -> dict:
    seq = doc_id.rsplit(":", 1)[1]
    if not seq.isdigit():
        raise NotFound(f"not_found: {doc_id} (esperado stj:integra:<SeqDocumento>)")
    con = stj_con()
    try:
        row = con.execute("SELECT * FROM integras_docs WHERE seq = ?", (int(seq),)).fetchone()
    finally:
        con.close()
    if not row:
        raise NotFound(f"not_found: {doc_id}")
    r = dict(row)
    text = stj.read_text(r.get("text_zip"), r.get("text_member")) if r.get("has_text") else ""
    return {"id": doc_id, "title": f"STJ – {r.get('processo')} – {r.get('tipo') or ''} (íntegra)", "court": "STJ",
            "processo": r.get("processo"), "orgao": None, "relator": r.get("ministro"), "data_julgamento": None,
            "data_publicacao": r.get("data_publicacao"),
            "source_url": scon_inteiro_teor_url(r.get("num_registro"), r.get("data_publicacao")) if (r.get("tipo") or "").upper().startswith("AC")
            else scon_search_url(r.get("processo")),
            "text_kind": "integra", "text": text,
            "empty_note": "íntegra listada nos metadados do STJ sem arquivo de texto publicado nos dados abertos",
            "metadata": {k: r.get(k) for k in ("seq", "num_registro", "classe", "tipo", "teor", "descricao", "assuntos", "recurso",
                                               "data_recebimento", "data_distribuicao")}
            | {"open_data_source_key": r.get("source_key"), "text_source": "dadosabertos.web.stj.jus.br (íntegras)"}}


@functools.lru_cache(maxsize=1)
def scon_exports() -> dict:
    if not SCON_EXPORT.exists():
        return {}
    out = {}
    for line in SCON_EXPORT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[f"stj:scon:{r['num_registro']}"] = r
    return out


def load_stj_scon(doc_id: str) -> dict:
    r = scon_exports().get(doc_id)
    if not r:
        raise NotFound(f"not_found: {doc_id}; inteiros teores do SCON disponíveis: {sorted(scon_exports())}")
    return {"id": doc_id, "title": f"STJ – {r.get('processo')} (inteiro teor, SCON)", "court": "STJ", "processo": r.get("processo"),
            "orgao": r.get("orgao"), "relator": r.get("relator"), "data_julgamento": r.get("data"),
            "data_publicacao": r.get("publicacao"), "source_url": r.get("source_url"), "text_kind": "integra",
            "text": r.get("text") or "",
            "metadata": {k: r.get(k) for k in ("num_registro", "tipo", "pdf_sha256", "pdf_pages", "obtained_via", "checks")}}


# ---------------------------------------------------------------- API do DBVECTOR (FAISS)
@functools.lru_cache(maxsize=1)
def api_headers() -> dict:
    return {"Authorization": f"Bearer {API_TOKEN_FILE.read_text().strip()}"} if API_TOKEN_FILE.exists() else {}


def api(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        resp = httpx.request(method, f"{API_URL}{path}", headers=api_headers(), timeout=120, **kwargs)
    except httpx.HTTPError as e:
        raise RuntimeError(f"api_unavailable: vector API at {API_URL} did not answer ({e.__class__.__name__})") from e
    if resp.status_code == 404:
        raise NotFound(f"not_found: {resp.json().get('detail')}")
    if resp.status_code >= 400:
        raise RuntimeError(f"api_error {resp.status_code}: {resp.text[:300]}")
    return resp


def load_indexed(doc_id: str) -> dict:
    r = api("GET", f"/doc/{quote(doc_id, safe=':')}").json()
    meta = r.get("meta") or {}
    return {"id": r["id"], "title": r.get("title"), "court": r.get("court"),
            "processo": meta.get("case_number") or meta.get("processo"), "orgao": meta.get("orgao_julgador"),
            "relator": meta.get("relator"), "data_julgamento": meta.get("decision_date") or r.get("date"),
            "data_publicacao": meta.get("publication_date"), "source_url": meta.get("url") or meta.get("source_url"),
            "text_kind": meta.get("text_kind") or "indexed_text", "text": r.get("text") or "",
            "metadata": {"code": r.get("code"), "article": r.get("article"), "date": r.get("date"), "source": "faiss_metadata", **meta}}


def load_doc(doc_id: str) -> dict:
    doc_id = (doc_id or "").strip()
    if doc_id.startswith("tjdft:") and doc_id.endswith(":original"):
        return load_tjdft_original(doc_id)
    if doc_id.startswith("tjdft:"):
        try:
            return load_tjdft(doc_id)
        except NotFound:
            return load_indexed(doc_id)
    if doc_id.startswith("lei:"):
        return load_law(doc_id)
    if doc_id.startswith("stj:espelho:"):
        return load_stj_espelho(doc_id)
    if doc_id.startswith("stj:integra:"):
        return load_stj_integra(doc_id)
    if doc_id.startswith("stj:scon:"):
        return load_stj_scon(doc_id)
    return load_indexed(doc_id)


# ---------------------------------------------------------------- TJDFT ao vivo
_live_lock = threading.Lock()


@functools.lru_cache(maxsize=1)
def live_client() -> TjdftClient:
    return TjdftClient(min_interval=1.0, timeout=60, max_retries=2)


def slim_live(reg: dict) -> dict:
    uuid = reg.get("uuid")
    ementa = clean_text(reg.get("ementa"))
    return {"id": f"tjdft:{uuid}", "uuid": uuid, "processo": reg.get("processo"), "identificador": reg.get("identificador"),
            "base": reg.get("base"), "subbase": reg.get("subbase"), "relator": reg.get("nomeRelator"),
            "orgao": reg.get("descricaoOrgaoJulgador"), "data_julgamento": iso_date(reg.get("dataJulgamento")),
            "data_publicacao": iso_date(reg.get("dataPublicacao")), "possui_inteiro_teor": reg.get("possuiInteiroTeor"),
            "segredo_justica": reg.get("segredoJustica"), "source_url": record_url(uuid, reg.get("base")) if uuid else None,
            "ementa_snippet": ementa[:500] + ("…" if len(ementa) > 500 else "")}


# ---------------------------------------------------------------- servidor MCP
INSTRUCTIONS = """Read-only Brazilian legal corpus from RAG-TCC. Every document tool returns: id, court, processo, orgao, relator,
data_julgamento, data_publicacao, source_url, text_kind (integra | ementa | espelho | original_doc | lei | informativo_jurisprudencia |
jurisprudencia_em_foco | indexed_text), text_sha256 over the FULL text, text_chars, and the requested slice (offset/limit, has_more).

Document ids: tjdft:<uuid> (collected TJDFT decision) · tjdft:<uuid>:original (text of the official .doc original) ·
lei:<slug>:art-<n>[-p<k>] (Planalto article, long articles split in parts) · stj:espelho:<id> (STJ acórdão espelho, 2022+) ·
stj:integra:<SeqDocumento> (STJ full text from open data, 2021+) · stj:scon:<num_registro> (STJ inteiro teor PDF from SCON) ·
other ids come from the vector index (older STJ/STF/TRF/SEEU material).

Coverage caveats: collected TJDFT is topic-scoped (LGPD, CFTV/cameras in condominiums, condominium fines); use tjdft_live_search /
tjdft_live_get for anything else in TJDFT. STJ open data has no full texts before 2021 and no espelhos before 2022; SCON itself is
behind Cloudflare and is not queried. Quote only after verify_quote returns exact_match=true on the same text_sha256."""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
READ_ONLY_REMOTE = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)

mcp: FastMCP = None  # criado em build_server()


def threaded(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))
    return wrapper


def semantic(query: str, k: int, court: Optional[str], date_from: Optional[str], date_to: Optional[str], id_prefix: Optional[str]) -> list:
    # id_prefix e court filtram dentro do FAISS (busca exata no subconjunto); datas são filtradas sobre os 100 vizinhos
    by_date = bool(date_from or date_to)
    payload = {"q": query, "k": 100 if by_date else k, "id_prefix": id_prefix or None, "court": court or None}
    results = api("POST", "/search", json=payload).json()["results"]
    out = []
    for r in results:
        meta = r.get("meta") or {}
        date = r.get("date") or ""
        if (date_from and (not date or date < date_from)) or (date_to and (not date or date > date_to)):
            continue
        text = r.get("text") or ""
        out.append({"id": r["id"], "title": r.get("title"), "court": r.get("court"), "date": r.get("date"),
                    "processo": meta.get("case_number"), "code": r.get("code"), "article": r.get("article"),
                    "source_url": meta.get("url"), "score": round(r["score"], 4),
                    "snippet": re.sub(r"\s+", " ", text[:400]).strip() + ("…" if len(text) > 400 else ""), "text_chars": len(text)})
        if len(out) >= k:
            break
    return out


def stj_totals(query: str, scope: str, tipo, desde, ate, ministro, orgao, classe) -> dict:
    fts = stj.to_fts_query(query)
    con = sqlite3.connect(f"file:{STJ_DB}?mode=ro", uri=True)
    totals = {}
    try:
        if scope in ("all", "espelhos"):
            where, params = stj._filters("e", "data_decisao", "relator", tipo, desde, ate, ministro, "sigla_classe", classe)
            if orgao:
                where += " AND e.orgao LIKE ?"
                params.append(f"%{orgao}%")
            totals["espelhos"] = con.execute(
                f"SELECT count(*) FROM (SELECT 1 FROM espelhos_fts JOIN espelhos e ON e.id = espelhos_fts.rowid"
                f" WHERE espelhos_fts MATCH ?{where} LIMIT {COUNT_CAP})", [fts, *params]).fetchone()[0]
        if scope in ("all", "integras"):
            where, params = stj._filters("d", "data_publicacao", "ministro", tipo, desde, ate, ministro, "classe", classe)
            totals["integras"] = con.execute(
                f"SELECT count(*) FROM (SELECT 1 FROM integras_fts JOIN integras_docs d ON d.seq = integras_fts.rowid"
                f" WHERE integras_fts MATCH ?{where} LIMIT {COUNT_CAP})", [fts, *params]).fetchone()[0]
    finally:
        con.close()
    return totals


def tjdft_local_search(query: str, limit: int, date_from, date_to, orgao, relator, document_type) -> dict:
    fts = stj.to_fts_query(query)
    clauses, params = [], []
    for column, value, op in (("d.date", date_from, ">="), ("d.date", date_to, "<="), ("d.orgao", orgao, "LIKE"),
                              ("d.relator", relator, "LIKE"), ("d.document_type", document_type, "=")):
        if value:
            clauses.append(f"{column} {op} ?")
            params.append(f"%{value}%" if op == "LIKE" else value)
    where = "".join(f" AND {c}" for c in clauses)
    con = tjdft_db()
    try:
        total = con.execute(f"SELECT count(*) FROM docs_fts JOIN docs d ON d.rowid = docs_fts.rowid WHERE docs_fts MATCH ?{where}",
                            [fts, *params]).fetchone()[0]
        rows = con.execute(
            "SELECT d.id, d.title, d.processo, d.orgao, d.relator, d.data_julgamento, d.data_publicacao, d.document_type, d.text_chars,"
            " bm25(docs_fts) AS score, snippet(docs_fts, -1, '[', ']', '…', 40)"
            f" FROM docs_fts JOIN docs d ON d.rowid = docs_fts.rowid WHERE docs_fts MATCH ?{where} ORDER BY score LIMIT ?",
            [fts, *params, limit]).fetchall()
    finally:
        con.close()
    return {"query": query, "fts_query": fts, "total": total, "returned": len(rows), "results": [
        {"id": r[0], "title": r[1], "court": "TJDFT", "processo": r[2], "orgao": r[3], "relator": r[4], "data_julgamento": r[5],
         "data_publicacao": r[6], "document_type": r[7], "text_chars": r[8], "score": round(r[9], 3), "snippet": r[10]} for r in rows]}


def build_server(host: str, port: int, allowed_hosts: list[str]) -> FastMCP:
    global mcp
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *allowed_hosts],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "https://chatgpt.com", "https://chat.openai.com",
                         *[f"https://{h}" for h in allowed_hosts]],
    )
    mcp = FastMCP("rag-tcc", instructions=INSTRUCTIONS, host=host, port=port, streamable_http_path="/mcp",
                  stateless_http=True, json_response=True, transport_security=security)

    # ---- compatibilidade com conectores do ChatGPT (deep research): search + fetch
    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def search(query: str) -> dict:
        """Search the whole corpus (vector index + STJ espelhos + collected TJDFT). Returns {results: [{id, title, url}]}; read with fetch(id)."""
        results, seen = [], set()

        def add(doc_id, title, url):
            if doc_id not in seen:
                seen.add(doc_id)
                results.append({"id": doc_id, "title": title or doc_id, "url": url or f"rag-tcc://{doc_id}"})

        for r in semantic(query, 10, None, None, None, None):
            add(r["id"], r["title"], r["source_url"])
        try:
            for r in tjdft_local_search(query, 5, None, None, None, None, None)["results"]:
                add(r["id"], r["title"], None)
        except sqlite3.OperationalError:
            pass
        try:
            for r in stj.search(STJ_DB, query, scope="espelhos", limit=5).get("espelhos", []):
                add(r["id"], f"STJ – {r['processo']} – {r.get('orgao') or ''}", r.get("scon_url"))
        except sqlite3.OperationalError:
            pass
        return {"results": results}

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def fetch(id: str) -> dict:
        """Full document by id (ChatGPT fetch shape): {id, title, text, url, metadata}. Text capped at 200k chars; see metadata.has_more."""
        e = envelope(load_doc(id), 0, 200000)
        meta = {k: e[k] for k in ("court", "processo", "orgao", "relator", "data_julgamento", "data_publicacao", "text_kind",
                                  "text_sha256", "text_chars", "has_more", "next_offset")} | e["metadata"]
        return {"id": e["id"], "title": e["title"] or e["id"], "text": e["text"], "url": e["source_url"] or f"rag-tcc://{e['id']}",
                "metadata": meta}

    # ---- ferramentas completas
    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def get_doc(id: str, offset: int = 0, limit: int = DEFAULT_LIMIT) -> dict:
        """Any document by id with provenance; long texts come in slices (offset/limit, max 200000). text_sha256 is over the full text."""
        return envelope(load_doc(id), offset, max(1, min(int(limit), 200000)))

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def verify_quote(doc_id: str, quote_text: str) -> dict:
        """Check a quote against the document's full text. exact_match = byte-exact substring; normalized_match ignores case,
        accents, curly quotes/dashes and whitespace. Offsets are character offsets in the full text (same text_sha256 as get_doc)."""
        doc = load_doc(doc_id)
        text = doc.get("text") or ""
        if not quote_text.strip():
            raise ValueError("quote_text vazio")
        exact, start = [], text.find(quote_text)
        while start >= 0 and len(exact) < 50:
            exact.append([start, start + len(quote_text)])
            start = text.find(quote_text, start + 1)
        folded, index_map = fold_with_map(text)
        folded_quote = fold_with_map(quote_text)[0].strip()
        normalized, pos = [], folded.find(folded_quote) if folded_quote else -1
        while pos >= 0 and len(normalized) < 50:
            normalized.append([index_map[pos], index_map[pos + len(folded_quote) - 1] + 1])
            pos = folded.find(folded_quote, pos + 1)
        first = (exact or normalized or [[None, None]])[0]
        context = text[max(0, first[0] - 200):first[1] + 200] if first[0] is not None else None
        return {"doc_id": doc["id"], "text_kind": doc.get("text_kind"), "text_sha256": sha256(text), "text_chars": len(text),
                "text_empty": not text, "exact_match": bool(exact), "exact_offsets": exact, "normalized_match": bool(normalized),
                "normalized_offsets": normalized, "offsets": exact or normalized,
                "offsets_kind": "exact" if exact else "normalized" if normalized else None, "context": context}

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def semantic_search(query: str, k: int = 10, court: Optional[str] = None, date_from: Optional[str] = None,
                        date_to: Optional[str] = None, id_prefix: Optional[str] = None) -> dict:
        """Semantic (embedding) search over the vector index: TJDFT, legislation, STJ/STF/TRF material.
        id_prefix (e.g. 'lei:lgpd', 'lei:cc', 'tjdft:') and court (TJDFT, STJ...) restrict the search itself (exact, no recall loss);
        date_from/date_to (YYYY-MM-DD) are applied to the 100 nearest neighbours."""
        results = semantic(query, max(1, min(int(k), 50)), court, date_from, date_to, id_prefix)
        return {"query": query, "returned": len(results),
                "total_note": "semantic search has no total; results are the nearest neighbours after filters", "results": results}

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def tjdft_search(query: str, limit: int = 20, date_from: Optional[str] = None, date_to: Optional[str] = None,
                     orgao: Optional[str] = None, relator: Optional[str] = None, document_type: Optional[str] = None) -> dict:
        """Keyword search (FTS5, accents ignored; "phrase", OR, NOT, prefix*) over the collected TJDFT corpus, with total count.
        document_type: acordao | decisao | informativo_jurisprudencia | jurisprudencia_em_foco."""
        return tjdft_local_search(query, max(1, min(int(limit), 100)), date_from, date_to, orgao, relator, document_type)

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def stj_search(query: str, scope: str = "all", limit: int = 20, tipo: Optional[str] = None, desde: Optional[str] = None,
                   ate: Optional[str] = None, ministro: Optional[str] = None, orgao: Optional[str] = None,
                   classe: Optional[str] = None) -> dict:
        """Keyword search (FTS5) in STJ open data. scope: espelhos (acórdão espelhos 2022+) | integras (full texts 2021+) | all.
        tipo: ACÓRDÃO | DECISÃO; desde/ate: YYYY-MM-DD; classe: REsp, AREsp...; totals capped at 10000."""
        if scope not in ("all", "espelhos", "integras"):
            raise ValueError("scope deve ser all, espelhos ou integras")
        limit = max(1, min(int(limit), 50))
        filters = dict(tipo=tipo, desde=desde, ate=ate, ministro=ministro, orgao=orgao, classe=classe)
        try:
            results = stj.search(STJ_DB, query, scope=scope, limit=limit, **filters)
            totals = stj_totals(query, scope, **filters)
        except sqlite3.OperationalError as e:
            raise ValueError(f"consulta inválida para FTS5 ({stj.to_fts_query(query)!r}): {e}") from e
        return {"query": query, "fts_query": stj.to_fts_query(query), "totals": totals, "total_cap": COUNT_CAP, **results}

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def stj_espelhos_by_processo(processo: str, limit: int = DEFAULT_LIMIT) -> dict:
        """All STJ espelhos for a case, e.g. 'REsp 1921653' or 'AREsp 2.556.551' (embargos/agravos come as separate espelhos)."""
        rows = stj.get_espelhos(STJ_DB, processo=processo)
        if not rows:
            raise NotFound(f"not_found: nenhum espelho para {processo!r} (espelhos cobrem acórdãos publicados de 2022 em diante)")
        return {"processo": processo, "total": len(rows), "espelhos": [envelope(espelho_doc(r), 0, limit) for r in rows]}

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def get_law_article(code: str, article: str) -> dict:
        """A law article from Planalto (current wording; revoked text removed). code: CF/88, ADCT, CC, CP, CPC, CPP, CDC, ECA, LGPD,
        LEP, 'Lei 4.591/64'; article: '5', '1.277', '1331-A', 'art. 7º'. Long articles come in ordered parts."""
        slug = law_slug(code)
        key = re.sub(r"(?i)^\s*art(igo)?\.?\s*", "", article)
        key = re.sub(r"[º°ª.\s]", "", key).upper()
        parts = laws()[1].get((slug, key))
        if not parts:
            raise NotFound(f"not_found: {code} art. {article} (procurado lei:{slug}:art-{key})")
        docs = [envelope(load_law(p["id"]), 0, None) for p in parts]
        full = "\n".join(p["text"] for p in docs)
        return {"code": parts[0]["code"], "article": key, "parts": len(docs), "source_url": docs[0]["source_url"],
                "fetched_at": docs[0]["metadata"].get("fetched_at"), "full_text_sha256": sha256(full), "documents": docs}

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def list_laws() -> dict:
        """Laws available to get_law_article, with article counts, source URL and fetch time."""
        out = {}
        for r in laws()[0].values():
            entry = out.setdefault(r["code"], {"code": r["code"], "slug": r["id"].split(":")[1], "law_name": r["meta"].get("law_name"),
                                               "source_url": r["meta"].get("url"), "fetched_at": r["meta"].get("fetched_at"),
                                               "records": 0, "articles": set()})
            entry["records"] += 1
            entry["articles"].add(r["article"])
        return {"laws": [{**v, "articles": len(v["articles"])} for v in out.values()]}

    @mcp.tool(annotations=READ_ONLY_REMOTE)
    @threaded
    def tjdft_live_search(query: str, page: int = 0, size: int = 20, sinonimos: bool = True) -> dict:
        """Live search on TJDFT's public jurisprudence API (all TJDFT, not only the collected corpus). Returns total hits and
        records; read one with tjdft_live_get(uuid). Rate-limited (~1 request/s)."""
        with _live_lock:
            data = live_client().search(query, pagina=max(0, int(page)), tamanho=max(1, min(int(size), 40)), sinonimos=sinonimos)
        records = [slim_live(r) for r in data.get("registros") or []]
        con = tjdft_db()
        try:
            local = {row[0] for row in con.execute(
                f"SELECT id FROM docs WHERE id IN ({','.join('?' * len(records))})", [r["id"] for r in records])} if records else set()
        finally:
            con.close()
        for r in records:
            r["in_collected_corpus"] = r["id"] in local
        return {"query": query, "total": (data.get("hits") or {}).get("value"), "page": page, "size": size, "results": records}

    @mcp.tool(annotations=READ_ONLY_REMOTE)
    @threaded
    def tjdft_live_get(uuid: str, offset: int = 0, limit: int = DEFAULT_LIMIT) -> dict:
        """Full TJDFT record straight from the public API by uuid (ementa + inteiro teor). Secret-of-justice records return metadata only."""
        with _live_lock:
            reg = live_client().fetch_full(uuid.strip().removeprefix("tjdft:"))
        if not reg:
            raise NotFound(f"not_found: uuid {uuid} não existe na API do TJDFT")
        slim = slim_live(reg)
        inteiro = clean_text(reg.get("inteiroTeor"))
        ementa = clean_text(reg.get("ementa"))
        secret = bool(reg.get("segredoJustica"))
        text = "" if secret else (inteiro or ementa)
        doc = {"id": slim["id"], "title": f"TJDFT – {reg.get('identificador') or ''} – Processo {reg.get('processo')}", "court": "TJDFT",
               "processo": slim["processo"], "orgao": slim["orgao"], "relator": slim["relator"],
               "data_julgamento": slim["data_julgamento"], "data_publicacao": slim["data_publicacao"], "source_url": slim["source_url"],
               "text_kind": "integra" if inteiro else "ementa", "text": text,
               "empty_note": "segredo de justiça: texto não é servido" if secret else None,
               "metadata": {"source": "jurisdf_api_live", "base": reg.get("base"), "subbase": reg.get("subbase"),
                            "decisao": clean_text(reg.get("decisao")), "ementa_chars": len(ementa), "segredo_justica": secret}}
        return envelope(doc, offset, max(1, min(int(limit), 200000)))

    @mcp.tool(annotations=READ_ONLY)
    @threaded
    def sources_status() -> dict:
        """What is available: document counts per source, periods and known gaps."""
        status = {}
        try:
            status["vector_index"] = api("GET", "/health").json()
        except Exception as e:  # noqa: BLE001
            status["vector_index"] = {"error": str(e)}
        con = tjdft_db()
        try:
            status["tjdft_collected"] = dict(con.execute("SELECT document_type, count(*) FROM docs GROUP BY document_type").fetchall())
            status["tjdft_collected_period"] = con.execute("SELECT min(date), max(date) FROM docs").fetchone()
        finally:
            con.close()
        status["tjdft_originals_doc"] = len(tjdft_originals())
        status["legislation_records"] = len(laws()[0])
        status["stj_open_data"] = stj.status(STJ_DB)
        status["stj_scon_inteiro_teor"] = sorted(scon_exports())
        status["gaps"] = ["STJ full texts only from 2021 and espelhos from 2022 (open data); SCON is not queried",
                          "collected TJDFT is topic-scoped; use tjdft_live_search/tjdft_live_get for the rest of TJDFT",
                          "STJ integras carry no órgão julgador; look it up in the espelho of the same processo"]
        return status

    return mcp


# ---------------------------------------------------------------- autenticação e execução
def mcp_token() -> str:
    if not MCP_TOKEN_FILE.exists():
        MCP_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(MCP_TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32))
    return MCP_TOKEN_FILE.read_text().strip()


class Gate:
    """Exige o token (Bearer em /mcp ou URL /k/<token>/mcp) e nunca registra o token no log."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path == "/health":
            return await self._reply(send, 200, {"status": "ok"})
        allowed = False
        m = re.fullmatch(r"/k/([^/]+)(/mcp/?)", path)
        if m and hmac.compare_digest(m.group(1).encode(), self.token.encode()):
            scope = dict(scope, path="/mcp", raw_path=b"/mcp")
            allowed = True
        elif path.rstrip("/") == "/mcp":
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            allowed = auth.lower().startswith("bearer ") and hmac.compare_digest(auth[7:].strip().encode(), self.token.encode())
            scope = dict(scope, path="/mcp", raw_path=b"/mcp")
        if not allowed:
            print(f"401 {scope['method']} {re.sub(r'/k/[^/]+', '/k/***', path)}", flush=True)
            return await self._reply(send, 401, {"error": "unauthorized"})
        return await self.app(scope, receive, send)

    @staticmethod
    async def _reply(send, status: int, body: dict):
        data = json.dumps(body).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
        await send({"type": "http.response.body", "body": data})


def main():
    ap = argparse.ArgumentParser(description="MCP HTTP somente leitura do RAG-TCC")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--allowed-host", action="append", default=[], help="Host público (túnel) aceito no header Host")
    args = ap.parse_args()
    server = build_server(args.host, args.port, args.allowed_host)
    tjdft_db().close()  # monta o cache antes de aceitar conexões
    import uvicorn
    uvicorn.run(Gate(server.streamable_http_app(), mcp_token()), host=args.host, port=args.port, access_log=False,
                log_level="info")


if __name__ == "__main__":
    main()
