"""
Parser de páginas de legislação do Planalto: HTML -> artigos -> registros JSONL.

- Remove texto revogado (<strike>, <s>, <del>, style line-through) das versões compiladas
- Divide o texto em artigos ("Art. 1º", "Art. 1.277.", "Art. 5º-A")
- Ignora artigos citados entre aspas (alterações de outras leis)
- Guarda a hierarquia (Parte/Livro/Título/Capítulo/Seção/Subseção)
- Divide artigos longos em partes, porque o embedder trunca textos longos
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BLOCK_MARK = "\ue000"  # caractere de uso privado que marca limite de bloco
BLOCK_TAGS = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "td", "table", "blockquote", "center", "pre"]
MAX_STRUCK_CHARS = 20000  # <strike> maior que isso provavelmente é tag não fechada

ART_RE = re.compile(r"^Art\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:[º°ª]|o\b)?\s*(?:-\s*([A-Z]{1,3})\b)?\s*[.:\-–]?\s*")
HEADING_RE = re.compile(
    r"^(PARTE\s+(?:GERAL|ESPECIAL)|LIVRO\s+[IVXLC]+|T[ÍI]TULO\s+[IVXLC]+|CAP[ÍI]TULO\s+[IVXLC]+|SUBSE[ÇC][ÃA]O\s+[IVXLC]+|SE[ÇC][ÃA]O\s+[IVXLC]+)(?:-[A-Z])?\b",
    re.IGNORECASE,
)
HEADING_LEVELS = ["PARTE", "LIVRO", "TITULO", "CAPITULO", "SECAO", "SUBSECAO"]
STOP_RE = re.compile(r"^(?:Bras[íi]lia|Rio de Janeiro)\s*,\s*\d{1,2}\s+de\s+\w+|^Este texto não substitui", re.IGNORECASE)
ADCT_RE = re.compile(r"ATO DAS DISPOSI[ÇC][ÕO]ES CONSTITUCIONAIS TRANSIT[ÓO]RIAS")

ANNOTATION_RE = re.compile(
    r"\(\s*(?:Reda[çc][ãa]o dada|Inclu[íi]d[oa]|Acrescentad[oa]|Acrescid[oa]|Vide|Regulamento|Regulamenta[çc][ãa]o|"
    r"Vig[êe]ncia|Renumerad[oa]|Produ[çc][ãa]o de efeitos?|Promulga[çc][ãa]o|Convertid[oa]|Revigorad[oa]|"
    r"Execu[çc][ãa]o suspensa|Suspens[oa]|Declarad[oa]|Mantid[oa]|Transformad[oa]|Ver\b)[^()]*(?:\([^()]*\)[^()]*)*\)",
    re.IGNORECASE,
)
# Links soltos no fim do dispositivo ("... titular. Vigência", "§ 1º . Vigência")
TRAILING_LINKS_RE = re.compile(r"(?:\s*\b(?:Vig[êe]ncia|Regulamento|Mensagem de veto|Produ[çc][ãa]o de efeitos?|Vide\s+[^.;:]*)\s*)+$", re.IGNORECASE)
REVOKED_RE = re.compile(r"\(\s*(?:Revogad[oa]s?|VETADO|Vetad[oa])[^()]*(?:\([^()]*\)[^()]*)*\)", re.IGNORECASE)
ENUM_ONLY_RE = re.compile(
    r"^(?:Art\.?\s*[\d.]+\s*(?:[º°ª]|o\b)?(?:-[A-Z]+)?|[IVXLCDM]+|§\s*\d+\s*(?:[º°ª]|o\b)?(?:-[A-Z]+)?|Par[áa]grafo [úu]nico|[a-z]\)|\d+\))?\s*[.:\-–]*\s*$"
)


@dataclass
class Article:
    code: str
    number: int
    suffix: str
    lines: List[str]
    hierarquia: List[str] = field(default_factory=list)

    @property
    def key(self) -> Tuple[int, str]:
        return (self.number, self.suffix)

    @property
    def article_id(self) -> str:
        return f"{self.number}-{self.suffix}" if self.suffix else str(self.number)

    @property
    def label(self) -> str:
        number = f"{self.number:,}".replace(",", ".")
        ordinal = "º" if self.number <= 9 else ""
        return f"Art. {number}{ordinal}" + (f"-{self.suffix}" if self.suffix else "")


def decode_html(raw: bytes) -> str:
    """Páginas do Planalto em geral são windows-1252 sem charset declarado."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def html_to_blocks(raw: bytes) -> Tuple[List[str], Dict[str, int]]:
    """Converte o HTML em blocos de texto (um por parágrafo), sem texto revogado."""
    soup = BeautifulSoup(decode_html(raw), "lxml")
    stats = {"struck_removed": 0, "struck_unwrapped": 0}

    for tag in soup(["script", "style", "head"]):
        tag.decompose()

    struck = soup.find_all(["strike", "s", "del"]) + soup.find_all(style=re.compile(r"line-through", re.IGNORECASE))
    for tag in struck:
        if tag.decomposed:
            continue
        if len(tag.get_text()) > MAX_STRUCK_CHARS:
            tag.unwrap()
            stats["struck_unwrapped"] += 1
        else:
            tag.decompose()
            stats["struck_removed"] += 1

    # Nas páginas do Planalto boa parte do texto fica fora de <body> após o parse
    # (HTML malformado), então usamos o documento inteiro, já sem <head>
    body = soup
    for br in body.find_all("br"):
        br.replace_with(BLOCK_MARK)
    for tag in body.find_all(BLOCK_TAGS):
        tag.insert_before(BLOCK_MARK)
        tag.insert_after(BLOCK_MARK)

    blocks = [re.sub(r"\s+", " ", piece).strip() for piece in body.get_text().split(BLOCK_MARK)]
    return [b for b in blocks if b], stats


def _heading_level(text: str) -> Optional[int]:
    word = text.split()[0].upper()
    word = word.translate(str.maketrans("ÍÇÃ", "ICA"))
    return HEADING_LEVELS.index(word) if word in HEADING_LEVELS else None


def parse_articles(blocks: List[str], code: str, adct_code: Optional[str] = None) -> Tuple[List[Article], Dict[str, int]]:
    articles: List[Article] = []
    stats = {"continuations_out_of_order": 0}
    current: Optional[Article] = None
    last_key: Tuple[int, str] = (0, "")
    hierarchy: List[Optional[str]] = [None] * len(HEADING_LEVELS)
    pending_heading: Optional[int] = None
    current_code = code
    stopped = False

    def flush():
        nonlocal current
        if current:
            articles.append(current)
            current = None

    for block in blocks:
        # Só o título da seção (artigos da CF citam o ADCT no texto)
        if adct_code and len(block) < 80 and ADCT_RE.match(block.upper()) and articles:
            flush()
            current_code, stopped, last_key = adct_code, False, (0, "")
            hierarchy = [None] * len(HEADING_LEVELS)
            pending_heading = None
            continue

        if stopped:
            continue

        if STOP_RE.search(block):
            flush()
            stopped = True
            continue

        heading = HEADING_RE.match(block)
        if heading and len(block) < 250:
            level = _heading_level(block)
            if level is not None:
                flush()
                title = _clean_lines([block])
                title = title[0] if title else heading.group(0)
                hierarchy[level] = title
                for lower in range(level + 1, len(HEADING_LEVELS)):
                    hierarchy[lower] = None
                pending_heading = level if len(title) <= len(heading.group(0)) + 2 else None
                continue

        match = ART_RE.match(block)
        if match:
            number = int(match.group(1).replace(".", ""))
            key = (number, match.group(2) or "")
            if key > last_key:
                flush()
                current = Article(
                    code=current_code,
                    number=number,
                    suffix=key[1],
                    lines=[block[match.end():]],
                    hierarquia=[h for h in hierarchy if h],
                )
                last_key = key
                pending_heading = None
                continue
            stats["continuations_out_of_order"] += 1

        if pending_heading is not None and current is None and len(block) < 250:
            name = _clean_lines([block])
            if name:  # blocos só com anotação "(Incluído pela Lei ...)" são ignorados
                hierarchy[pending_heading] = f"{hierarchy[pending_heading]} – {name[0]}"
                pending_heading = None
            continue

        if current:
            current.lines.append(block)

    flush()
    return articles, stats


def _clean_lines(lines: List[str]) -> List[str]:
    cleaned = []
    for line in lines:
        line = ANNOTATION_RE.sub("", line)
        line = REVOKED_RE.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        line = TRAILING_LINKS_RE.sub("", line)
        if line and not ENUM_ONLY_RE.match(line):
            cleaned.append(line)
    return cleaned


def _split_parts(lines: List[str], max_chars: int, target_chars: int) -> List[List[str]]:
    pieces: List[str] = []
    for line in lines:
        if len(line) <= max_chars:
            pieces.append(line)
            continue
        sentence = ""
        for chunk in re.split(r"(?<=[.;:])\s+", line):
            if sentence and len(sentence) + len(chunk) + 1 > target_chars:
                pieces.append(sentence)
                sentence = chunk
            else:
                sentence = f"{sentence} {chunk}".strip()
        if sentence:
            pieces.append(sentence)

    if sum(len(p) for p in pieces) <= max_chars:
        return [pieces]

    parts, current, size = [], [], 0
    for piece in pieces:
        if current and size + len(piece) > target_chars:
            parts.append(current)
            current, size = [], 0
        current.append(piece)
        size += len(piece) + 1
    if current:
        parts.append(current)
    return parts


def slugify_code(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")


def build_records(
    law: Dict[str, Any],
    articles: List[Article],
    fetched_at: str,
    max_chars: int = 1500,
    target_chars: int = 1200,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    records: List[Dict[str, Any]] = []
    seen_ids: Dict[str, int] = {}
    stats = {"articles": 0, "revoked_skipped": 0, "records": 0, "duplicate_ids": 0}

    for article in articles:
        lines = _clean_lines(article.lines)
        if not lines:
            stats["revoked_skipped"] += 1
            continue
        stats["articles"] += 1

        law_name = law["name"] if article.code == law["code"] else f"Ato das Disposições Constitucionais Transitórias ({law['code']})"
        context = " / ".join(article.hierarquia[-2:])
        parts = _split_parts(lines, max_chars, target_chars)

        base_id = f"lei:{slugify_code(article.code)}:art-{article.article_id}"
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            stats["duplicate_ids"] += 1
            base_id = f"{base_id}-dup{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1

        for n, part_lines in enumerate(parts, 1):
            multi = len(parts) > 1
            part_label = f" (parte {n}/{len(parts)})" if multi else ""
            header = f"{law_name} – {article.label}{part_label}"
            body = "\n".join(part_lines)
            text = f"{header}\n{context}\n{body}" if context else f"{header}\n{body}"

            records.append({
                "id": f"{base_id}-p{n}" if multi else base_id,
                "text": text,
                "title": f"{article.code}, {article.label}{part_label}",
                "code": article.code,
                "article": article.article_id,
                "meta": {
                    "tipo": "legislacao",
                    "source": "planalto",
                    "law_name": law_name,
                    "article_label": article.label,
                    "hierarquia": article.hierarquia,
                    "part": n,
                    "parts": len(parts),
                    "url": law["url"],
                    "fetched_at": fetched_at,
                },
            })
            stats["records"] += 1

    return records, stats
