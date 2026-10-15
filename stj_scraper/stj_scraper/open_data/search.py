"""
Busca de qualquer termo no corpus local do STJ (SQLite FTS5).

Consulta: palavras soltas (todas precisam aparecer), "frase exata", OR, NOT, NEAR(...), prefixo* —
sintaxe do FTS5. Tokens com pontuação (ex.: 1.365.279) viram frase automaticamente. Acentos são ignorados.
"""
import re
import sqlite3
import unicodedata
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

TOKEN_RE = re.compile(r'"[^"]*"|NEAR\([^)]*\)|\(|\)|[^\s()"]+')
OPERATORS = {"AND", "OR", "NOT"}


def to_fts_query(query: str) -> str:
    """Normaliza a consulta para o FTS5.

    - frases entre aspas, NEAR(...), parênteses e AND/OR/NOT são preservados;
    - entre dois termos vizinhos sem operador entra AND explícito (o FTS5 rejeita "(a OR b) c");
    - termos com pontuação (1.365.279, art.1.337) viram frase; prefixo* é mantido.
    """
    parts = []
    for token in TOKEN_RE.findall(query.strip()):
        if token in OPERATORS or token in ("(", ")") or token.startswith('"') or token.startswith("NEAR("):
            parts.append(token)
        elif re.fullmatch(r"\w+\*?", token):
            parts.append(token)
        else:
            inner = token.replace('"', "")
            parts.append(f'"{inner}"')
    result = []
    for token in parts:
        starts_operand = token not in OPERATORS and token != ")"
        ends_operand = bool(result) and result[-1] not in OPERATORS and result[-1] != "("
        if starts_operand and ends_operand:
            result.append("AND")
        result.append(token)
    return " ".join(result)


def _fold(text: str) -> str:
    """Minúsculas sem acento, preservando o tamanho (1 caractere -> 1 caractere) para recortar o trecho."""
    return "".join((unicodedata.normalize("NFKD", ch)[:1] or ch).lower() for ch in text)


def make_snippet(text: str, query: str, width: int = 320) -> str:
    if not text:
        return ""
    folded = _fold(text)
    terms = [_fold(t) for t in re.findall(r"[\w.]+", re.sub(r"\b(AND|OR|NOT|NEAR)\b", " ", query)) if len(t) > 2]
    positions = [folded.find(t) for t in terms if folded.find(t) >= 0]
    start = max(0, min(positions) - width // 3) if positions else 0
    snippet = re.sub(r"\s+", " ", text[start:start + width]).strip()
    return ("…" if start else "") + snippet + ("…" if start + width < len(text) else "")


def read_text(text_zip: Optional[str], member: Optional[str]) -> str:
    if not text_zip or not member or not Path(text_zip).exists():
        return ""
    from .build import clean_text
    with zipfile.ZipFile(text_zip) as zf:
        return clean_text(zf.read(member))


def _filters(prefix: str, date_col: str, person_col: str, tipo, desde, ate, pessoa, classe_col, classe) -> (str, list):
    clauses, params = [], []
    if tipo:
        clauses.append(f"{prefix}.tipo = ?")
        params.append(tipo)
    if desde:
        clauses.append(f"{prefix}.{date_col} >= ?")
        params.append(desde)
    if ate:
        clauses.append(f"{prefix}.{date_col} <= ?")
        params.append(ate)
    if pessoa:
        clauses.append(f"{prefix}.{person_col} LIKE ?")
        params.append(f"%{pessoa}%")
    if classe:
        clauses.append(f"{prefix}.{classe_col} = ?")
        params.append(classe)
    return ("".join(f" AND {c}" for c in clauses), params)


def search_integras(con: sqlite3.Connection, query: str, limit: int = 10, tipo: Optional[str] = None,
                    desde: Optional[str] = None, ate: Optional[str] = None, ministro: Optional[str] = None,
                    classe: Optional[str] = None, snippets: bool = True) -> List[Dict]:
    fts = to_fts_query(query)
    where, params = _filters("d", "data_publicacao", "ministro", tipo, desde, ate, ministro, "classe", classe)
    rows = con.execute(
        "SELECT d.seq, d.num_registro, d.processo, d.classe, d.tipo, d.data_publicacao, d.ministro, d.teor, d.descricao,"
        " d.has_text, d.text_zip, d.text_member, d.text_chars, bm25(integras_fts) AS score"
        " FROM integras_fts JOIN integras_docs d ON d.seq = integras_fts.rowid"
        f" WHERE integras_fts MATCH ?{where} ORDER BY score LIMIT ?",
        [fts, *params, limit],
    ).fetchall()
    results = []
    for (seq, registro, processo, classe_, tipo_, data, ministro_, teor, descricao, has_text, zip_path, member,
         chars, score) in rows:
        results.append({
            "source": "integras", "id": f"stj:integra:{seq}", "seq": seq, "num_registro": registro,
            "processo": processo, "classe": classe_, "tipo": tipo_, "data_publicacao": data, "ministro": ministro_,
            "teor": teor, "descricao": descricao, "has_text": bool(has_text), "text_chars": chars, "score": round(score, 3),
            "snippet": make_snippet(read_text(zip_path, member), fts) if snippets and has_text else None,
            "scon_url": f"https://scon.stj.jus.br/SCON/pesquisar.jsp?b=ACOR&livre={quote(processo or '')}",
        })
    return results


def search_espelhos(con: sqlite3.Connection, query: str, limit: int = 10, tipo: Optional[str] = None,
                    desde: Optional[str] = None, ate: Optional[str] = None, relator: Optional[str] = None,
                    classe: Optional[str] = None, orgao: Optional[str] = None) -> List[Dict]:
    fts = to_fts_query(query)
    where, params = _filters("e", "data_decisao", "relator", tipo, desde, ate, relator, "sigla_classe", classe)
    if orgao:
        where += " AND e.orgao LIKE ?"
        params.append(f"%{orgao}%")
    rows = con.execute(
        "SELECT e.id, e.num_registro, e.sigla_classe, e.numero_processo, e.orgao, e.relator, e.tipo, e.data_decisao,"
        " e.data_publicacao, e.fonte, e.tema, e.tese_juridica, bm25(espelhos_fts) AS score,"
        " snippet(espelhos_fts, -1, '[', ']', '…', 40) AS trecho"
        " FROM espelhos_fts JOIN espelhos e ON e.id = espelhos_fts.rowid"
        f" WHERE espelhos_fts MATCH ?{where} ORDER BY score LIMIT ?",
        [fts, *params, limit],
    ).fetchall()
    return [{
        "source": "espelhos", "id": f"stj:espelho:{row[0]}", "num_registro": row[1],
        "processo": " ".join(v for v in (row[2], row[3]) if v), "orgao": row[4], "relator": row[5], "tipo": row[6],
        "data_decisao": row[7], "data_publicacao": row[8], "fonte": row[9], "tema": row[10], "tese_juridica": row[11],
        "score": round(row[12], 3), "snippet": row[13],
        "scon_url": f"https://scon.stj.jus.br/SCON/pesquisar.jsp?b=ACOR&livre={quote(' '.join(v for v in (row[2], row[3]) if v))}",
    } for row in rows]


def search(db_path: Path, query: str, scope: str = "all", limit: int = 10, **filters) -> Dict[str, List[Dict]]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        out: Dict[str, List[Dict]] = {}
        if scope in ("all", "espelhos"):
            out["espelhos"] = search_espelhos(con, query, limit, tipo=filters.get("tipo"), desde=filters.get("desde"),
                                              ate=filters.get("ate"), relator=filters.get("ministro"),
                                              classe=filters.get("classe"), orgao=filters.get("orgao"))
        if scope in ("all", "integras"):
            out["integras"] = search_integras(con, query, limit, tipo=filters.get("tipo"), desde=filters.get("desde"),
                                              ate=filters.get("ate"), ministro=filters.get("ministro"),
                                              classe=filters.get("classe"))
        return out
    finally:
        con.close()


def get_text(db_path: Path, seq: int) -> Optional[Dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT processo, tipo, data_publicacao, ministro, text_zip, text_member FROM integras_docs WHERE seq = ?",
                          (seq,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    return {"seq": seq, "processo": row[0], "tipo": row[1], "data_publicacao": row[2], "ministro": row[3],
            "text": read_text(row[4], row[5])}


def get_espelhos(db_path: Path, espelho_id: Optional[int] = None, processo: Optional[str] = None) -> List[Dict]:
    """Espelhos completos por id (stj:espelho:<id>) ou por processo ("REsp 1921653", "AREsp 2.556.551")."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        if espelho_id is not None:
            rows = con.execute("SELECT * FROM espelhos WHERE id = ?", (espelho_id,)).fetchall()
        elif processo:
            m = re.match(r"^\s*(.+?)\s+([\d.]+)\s*(?:/\s*[A-Z]{2})?\s*$", processo)
            if not m:
                return []
            rows = con.execute(
                "SELECT * FROM espelhos WHERE sigla_classe = ? AND numero_processo = ? ORDER BY data_decisao",
                (m.group(1).strip(), m.group(2).replace(".", "")),
            ).fetchall()
        else:
            return []
    finally:
        con.close()
    return [dict(row) | {"id_api": f"stj:espelho:{row['id']}"} for row in rows]


def status(db_path: Path) -> Dict:
    if not db_path.exists():
        return {"db": str(db_path), "exists": False}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        q = lambda sql: con.execute(sql).fetchone()
        return {
            "db": str(db_path), "db_gb": round(db_path.stat().st_size / 1e9, 2),
            "integras_docs": q("SELECT count(*) FROM integras_docs")[0],
            "integras_with_text": q("SELECT count(*) FROM integras_docs WHERE has_text = 1")[0],
            "integras_period": q("SELECT min(data_publicacao), max(data_publicacao) FROM integras_docs"),
            "espelhos_docs": q("SELECT count(*) FROM espelhos")[0],
            "espelhos_period": q("SELECT min(data_decisao), max(data_decisao) FROM espelhos"),
            "files_ingested": q("SELECT count(*) FROM ingested")[0],
        }
    finally:
        con.close()
