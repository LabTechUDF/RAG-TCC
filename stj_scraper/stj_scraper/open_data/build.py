"""
Monta o corpus local do STJ em SQLite + FTS5 a partir de data/open_data/raw/.

- integras_docs: um registro por documento publicado (metadados diários), com ponteiro para o texto no ZIP.
- integras_fts: índice FTS5 sem conteúdo (content=''): os ~28 GB de texto ficam só nos ZIPs (~10 GB).
- espelhos / espelhos_fts: espelhos de acórdãos (ementa, decisão, legislação, precedentes citados, teses).
- ingested: arquivos já processados; um dia só é reprocessado se o metadado ou o ZIP mudarem.

O tokenizador ignora acentos: "condominio" encontra "condomínio".
"""
import html
import json
import logging
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .sync import in_window, normalize_day

logger = logging.getLogger(__name__)
TOKENIZE = "unicode61 remove_diacritics 2"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS integras_docs (
    seq INTEGER PRIMARY KEY,
    num_registro TEXT, processo TEXT, classe TEXT, tipo TEXT, data_publicacao TEXT,
    data_recebimento TEXT, data_distribuicao TEXT, ministro TEXT, recurso TEXT, teor TEXT,
    descricao TEXT, assuntos TEXT, has_text INTEGER, text_zip TEXT, text_member TEXT, text_chars INTEGER,
    source_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_integras_registro ON integras_docs(num_registro);
CREATE INDEX IF NOT EXISTS idx_integras_data ON integras_docs(data_publicacao);
CREATE VIRTUAL TABLE IF NOT EXISTS integras_fts USING fts5(
    texto, meta, content='', contentless_delete=1, tokenize='{TOKENIZE}'
);
CREATE TABLE IF NOT EXISTS espelhos (
    id INTEGER PRIMARY KEY, num_registro TEXT, numero_processo TEXT, sigla_classe TEXT, descricao_classe TEXT,
    orgao TEXT, relator TEXT, tipo TEXT, data_decisao TEXT, data_publicacao TEXT, fonte TEXT,
    ementa TEXT, decisao TEXT, jurisprudencia_citada TEXT, referencias_legislativas TEXT, acordaos_similares TEXT,
    notas TEXT, informacoes_complementares TEXT, termos_auxiliares TEXT, tese_juridica TEXT, tema TEXT,
    source_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_espelhos_registro ON espelhos(num_registro);
CREATE INDEX IF NOT EXISTS idx_espelhos_data ON espelhos(data_decisao);
CREATE VIRTUAL TABLE IF NOT EXISTS espelhos_fts USING fts5(
    ementa, decisao, jurisprudencia, referencias, notas, complementares, termos, tese, processo,
    tokenize='{TOKENIZE}'
);
CREATE TABLE IF NOT EXISTS ingested (
    path TEXT PRIMARY KEY, kind TEXT, key TEXT, signature TEXT, docs INTEGER, texts INTEGER, ingested_at TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(SCHEMA)
    return con


def none_if_empty(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ("", "None", "null") else text


def pick(record: dict, *names: str) -> Optional[str]:
    for name in names:
        value = none_if_empty(record.get(name))
        if value is not None:
            return value
    return None


def normalize_date(value) -> Optional[str]:
    """'2025-06-12' fica igual; epoch em ms (arquivos de 2022-2023, ex. '1643680800000') vira a data em UTC.

    Esses timestamps marcam meia-noite local do STJ (02:00 ou 03:00 UTC), então a data UTC é o dia correto.
    """
    text = none_if_empty(value)
    if text and text.isdigit() and len(text) >= 12:
        return datetime.fromtimestamp(int(text) / 1000, timezone.utc).date().isoformat()
    return text


def clean_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[a-zA-Z][^<>]*>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_json_list(path: Path) -> List[dict]:
    raw = path.read_bytes().decode("utf-8-sig", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # O STJ publica meses sem acórdãos como um JSON malformado com "Obs": "Sem lançamentos para o mês de ..."
        if "Sem lançamentos" in raw[:2000]:
            logger.info(f"ℹ️ {path}: mês sem lançamentos (arquivo placeholder do STJ)")
            return []
        raise
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return next((v for v in data.values() if isinstance(v, list)), [data])
    return []


def signature(*paths: Optional[Path]) -> str:
    parts = []
    for p in paths:
        if p and p.exists():
            st = p.stat()
            parts.append(f"{p.name}:{st.st_size}:{int(st.st_mtime)}")
    return "|".join(parts)


def already_ingested(con: sqlite3.Connection, path: Path, sig: str) -> bool:
    row = con.execute("SELECT signature FROM ingested WHERE path = ?", (str(path),)).fetchone()
    return bool(row and row[0] == sig)


def mark_ingested(con, path: Path, kind: str, key: str, sig: str, docs: int, texts: int) -> None:
    con.execute(
        "INSERT OR REPLACE INTO ingested VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(path), kind, key, sig, docs, texts, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )


# ------------------------------------------------------------------ íntegras
def zip_members(zf: Optional[zipfile.ZipFile]) -> Dict[str, str]:
    members: Dict[str, str] = {}
    if not zf:
        return members
    for info in zf.infolist():
        if info.filename.lower().endswith(".txt"):
            stem = Path(info.filename).stem
            members[stem] = info.filename
            members.setdefault(stem.lstrip("0") or "0", info.filename)
    return members


def repair_zip(zip_path: Path) -> Optional[Path]:
    """Reconstrói um ZIP sem diretório central (arquivo publicado truncado pelo STJ, ex. textos 2026-01-26)
    lendo os cabeçalhos locais em sequência. Grava <dia>.repaired.zip ao lado e o devolve."""
    import struct
    import zlib

    repaired = zip_path.with_name(zip_path.stem + ".repaired.zip")
    if repaired.exists() and repaired.stat().st_mtime >= zip_path.stat().st_mtime:
        return repaired
    data = zip_path.read_bytes()
    members = {}
    pos = 0
    while True:
        pos = data.find(b"PK\x03\x04", pos)
        if pos < 0:
            break
        try:
            _, flag, method, _, _, _, csize, _, nlen, xlen = struct.unpack("<HHHHHIIIHH", data[pos + 4:pos + 30])
            name = data[pos + 30:pos + 30 + nlen].decode("utf-8", errors="replace")
            start = pos + 30 + nlen + xlen
            if flag & 0x08 or csize == 0:
                nxt = data.find(b"PK\x03\x04", start)
                chunk = data[start:nxt if nxt > 0 else len(data)]
            else:
                chunk = data[start:start + csize]
            content = zlib.decompressobj(-15).decompress(chunk) if method == 8 else chunk
            if name.lower().endswith(".txt") and content:
                members[name] = content
            pos = start + max(len(chunk), 1)
        except Exception:
            pos += 4
    if not members:
        return None
    tmp = repaired.with_name(repaired.name + ".part")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, content in members.items():
            out.writestr(name, content)
    tmp.replace(repaired)
    logger.warning(f"🩹 {zip_path.name}: ZIP sem diretório central; {len(members)} textos recuperados em {repaired.name}")
    return repaired


def ingest_integras_day(con: sqlite3.Connection, meta_path: Path, zip_path: Optional[Path]) -> Tuple[int, int]:
    key = meta_path.stem
    records = load_json_list(meta_path)
    zf = None
    if zip_path and zip_path.exists():
        try:
            zf = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile:
            zip_path = repair_zip(zip_path)
            zf = zipfile.ZipFile(zip_path) if zip_path else None
    members = zip_members(zf)
    docs = texts = 0
    try:
        for record in records:
            seq_raw = pick(record, "SeqDocumento", "seqDocumento", "seq_documento")
            if not seq_raw or not seq_raw.isdigit():
                continue
            seq = int(seq_raw)
            member = members.get(seq_raw) or members.get(seq_raw.lstrip("0"))
            text = clean_text(zf.read(member)) if (zf and member) else ""
            processo = pick(record, "processo")
            row = (
                seq, pick(record, "numeroRegistro"), processo,
                re.sub(r"\s*\d[\d.]*\s*$", "", processo) if processo else None,
                pick(record, "tipoDocumento"), normalize_date(pick(record, "dataPublicacao")),
                normalize_date(pick(record, "dataRecebimento")),
                normalize_date(pick(record, "dataDistribuição", "dataDistribuicao")), pick(record, "NM_MINISTRO", "ministro"),
                pick(record, "recurso"), pick(record, "teor"), pick(record, "descricaoMonocratica"),
                pick(record, "assuntos"), int(bool(text)), str(zip_path) if member else None, member,
                len(text), key,
            )
            existing = con.execute("SELECT has_text, text_zip, text_member FROM integras_docs WHERE seq = ?", (seq,)).fetchone()
            if existing and existing[0] and not text:
                # O mesmo documento aparece em mais de um dia de metadados; não apaga o texto já vinculado
                continue
            if existing:
                con.execute("DELETE FROM integras_fts WHERE rowid = ?", (seq,))
            con.execute("INSERT OR REPLACE INTO integras_docs VALUES (" + ",".join("?" * len(row)) + ")", row)
            meta = " ".join(v for v in (row[2], row[4], row[8], row[9], row[10], row[11]) if v)
            con.execute("INSERT INTO integras_fts(rowid, texto, meta) VALUES (?, ?, ?)", (seq, text, meta))
            docs += 1
            texts += bool(text)
    finally:
        if zf:
            zf.close()
    return docs, texts


# ------------------------------------------------------------------ espelhos
def parse_publicacao(value) -> Tuple[Optional[str], Optional[str]]:
    text = none_if_empty(value)
    if not text:
        return None, None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    fonte = text.split("DATA:")[0].strip() if "DATA:" in text else None
    return (f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None), fonte


def iso_compact(value) -> Optional[str]:
    text = none_if_empty(value)
    if text and len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def as_text(value) -> Optional[str]:
    if isinstance(value, list):
        joined = "\n\n".join(str(v).strip() for v in value if none_if_empty(v))
        return joined or None
    return none_if_empty(value)


def ingest_espelhos_file(con: sqlite3.Connection, path: Path) -> int:
    count = 0
    for record in load_json_list(path):
        id_raw = pick(record, "id")
        if not id_raw or not id_raw.isdigit():
            continue
        data_publicacao, fonte = parse_publicacao(record.get("dataPublicacao"))
        row = {
            "id": int(id_raw), "num_registro": pick(record, "numeroRegistro"),
            "numero_processo": pick(record, "numeroProcesso"), "sigla_classe": pick(record, "siglaClasse"),
            "descricao_classe": pick(record, "descricaoClasse"), "orgao": pick(record, "nomeOrgaoJulgador"),
            "relator": pick(record, "ministroRelator"), "tipo": pick(record, "tipoDeDecisao"),
            "data_decisao": iso_compact(record.get("dataDecisao")), "data_publicacao": data_publicacao, "fonte": fonte,
            "ementa": as_text(record.get("ementa")), "decisao": as_text(record.get("decisao")),
            "jurisprudencia_citada": as_text(record.get("jurisprudenciaCitada")),
            "referencias_legislativas": as_text(record.get("referenciasLegislativas")),
            "acordaos_similares": as_text(record.get("acordaosSimilares")), "notas": as_text(record.get("notas")),
            "informacoes_complementares": as_text(record.get("informacoesComplementares")),
            "termos_auxiliares": as_text(record.get("termosAuxiliares")),
            "tese_juridica": as_text(record.get("teseJuridica")), "tema": as_text(record.get("tema")),
            "source_key": f"{path.parent.name}/{path.stem}",
        }
        if con.execute("SELECT 1 FROM espelhos WHERE id = ?", (row["id"],)).fetchone():
            con.execute("DELETE FROM espelhos_fts WHERE rowid = ?", (row["id"],))
        con.execute(f"INSERT OR REPLACE INTO espelhos ({','.join(row)}) VALUES ({','.join('?' * len(row))})", tuple(row.values()))
        processo = " ".join(v for v in (row["sigla_classe"], row["numero_processo"], row["num_registro"], row["relator"], row["orgao"]) if v)
        con.execute(
            "INSERT INTO espelhos_fts(rowid, ementa, decisao, jurisprudencia, referencias, notas, complementares, termos, tese, processo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row["id"], row["ementa"], row["decisao"], row["jurisprudencia_citada"], row["referencias_legislativas"],
             row["notas"], row["informacoes_complementares"], row["termos_auxiliares"], row["tese_juridica"], processo),
        )
        count += 1
    return count


# ------------------------------------------------------------------ orquestração
def build(data_dir: Path, db_path: Optional[Path] = None, what: Iterable[str] = ("integras", "espelhos"),
          since: Optional[str] = None, until: Optional[str] = None, limit: Optional[int] = None) -> Dict:
    raw_dir = data_dir / "raw"
    db_path = db_path or data_dir / "stj_open_data.sqlite"
    con = connect(db_path)
    since, until = normalize_day(since), normalize_day(until)
    report = {"integras_days": 0, "integras_docs": 0, "integras_texts": 0, "espelhos_files": 0, "espelhos_docs": 0,
              "skipped_unchanged": 0, "failed_files": []}
    processed = 0
    try:
        if "integras" in what:
            for meta_path in sorted((raw_dir / "integras" / "metadados").glob("*.json")):
                if not in_window(meta_path.stem, since, until):
                    continue
                zip_path = raw_dir / "integras" / "textos" / f"{meta_path.stem}.zip"
                sig = signature(meta_path, zip_path)
                if already_ingested(con, meta_path, sig):
                    report["skipped_unchanged"] += 1
                    continue
                if limit and processed >= limit:
                    break
                try:
                    docs, texts = ingest_integras_day(con, meta_path, zip_path if zip_path.exists() else None)
                except Exception as e:  # arquivo corrompido/malformado: registra e segue; não marca como ingerido
                    con.rollback()
                    logger.error(f"❌ íntegras {meta_path.stem}: {e}")
                    report["failed_files"].append(f"{meta_path}: {e}")
                    continue
                mark_ingested(con, meta_path, "integras", meta_path.stem, sig, docs, texts)
                con.commit()
                processed += 1
                report["integras_days"] += 1
                report["integras_docs"] += docs
                report["integras_texts"] += texts
                logger.info(f"📚 íntegras {meta_path.stem}: {docs} docs, {texts} com texto")
        if "espelhos" in what:
            for path in sorted((raw_dir / "espelhos").glob("*/*.json")):
                if not in_window(path.stem, since, until):
                    continue
                sig = signature(path)
                if already_ingested(con, path, sig):
                    report["skipped_unchanged"] += 1
                    continue
                if limit and processed >= limit:
                    break
                try:
                    docs = ingest_espelhos_file(con, path)
                except Exception as e:  # arquivo corrompido/malformado: registra e segue; não marca como ingerido
                    con.rollback()
                    logger.error(f"❌ espelhos {path.parent.name}/{path.stem}: {e}")
                    report["failed_files"].append(f"{path}: {e}")
                    continue
                mark_ingested(con, path, "espelhos", path.stem, sig, docs, 0)
                con.commit()
                processed += 1
                report["espelhos_files"] += 1
                report["espelhos_docs"] += docs
                logger.info(f"🪞 espelhos {path.parent.name}/{path.stem}: {docs} acórdãos")
    finally:
        con.close()
    return report
