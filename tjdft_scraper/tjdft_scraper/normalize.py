"""
Normaliza registros da API do TJDFT para o schema usado pelos demais scrapers
(compatível com DBVECTOR/src/tools/tratamento_dados.py e src/schema.py:Doc).
"""
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

SITE_URL = "https://jurisdf.tjdft.jus.br"

BASE_LABELS = {
    "acordaos": "Acórdão",
    "acordaos-tr": "Acórdão (Turma Recursal)",
    "decisoes-monocraticas": "Decisão monocrática",
    "decisoes-presidencia": "Decisão da Presidência",
    "decisoes": "Decisão",
}

DOCUMENT_TYPES = {
    "acordaos": "acordao",
    "decisoes": "decisao",
    "informativo-jurisprudencia": "informativo_jurisprudencia",
    "jurisprudencia-foco": "jurisprudencia_em_foco",
}
NON_DECISION_BASES = ("informativo-jurisprudencia", "jurisprudencia-foco")

# Ordem de prioridade para escolher o cluster principal quando um registro
# aparece em buscas de mais de um tema
TOPIC_PRIORITY = ["condominio_cameras", "cftv", "lgpd"]


def clean_text(value: Optional[str]) -> str:
    """Remove HTML residual e normaliza espaços preservando quebras de parágrafo."""
    if not value:
        return ""
    # Algumas ementas vêm com HTML do editor (<p class="MsoNormal">) ou escapado (&lt;br&gt;)
    text = html.unescape(html.unescape(value))
    text = re.sub(r"<\s*br\s*/?\s*>|<\s*/\s*p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<!--.*?-->|</?[a-zA-Z][^<>]*>", "", text, flags=re.DOTALL)
    text = text.replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


BRASILIA = timezone(timedelta(hours=-3))


def iso_date(value: Optional[str]) -> Optional[str]:
    """Converte o timestamp UTC da API para a data em Brasília.

    '2026-08-13T03:00:00.000Z' -> '2026-08-13'; '2026-09-12T02:59:59.000Z' -> '2026-09-11'.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(BRASILIA).date().isoformat()
    except ValueError:
        return value[:10]


def record_url(uuid: str, base: Optional[str]) -> str:
    if (base or "").startswith("decisoes"):
        return f"{SITE_URL}/decisoes/{uuid}/inteiro-teor"
    return f"{SITE_URL}/acordaos/{uuid}"


def primary_topic(topics: Iterable[str]) -> str:
    topics = list(topics)
    for topic in TOPIC_PRIORITY:
        if topic in topics:
            return topic
    return sorted(topics)[0] if topics else "tjdft"


def legal_area(orgao_julgador: Optional[str]) -> str:
    orgao = (orgao_julgador or "").upper()
    return "Penal" if "CRIMINAL" in orgao else "Cível"


def normalize_record(
    registro: Dict[str, Any],
    matched_queries: List[str],
    topics: List[str],
    keep_html: bool = False,
) -> Dict[str, Any]:
    uuid = registro["uuid"]
    base = registro.get("subbase") or registro.get("base")
    ementa = clean_text(registro.get("ementa"))
    inteiro_teor = clean_text(registro.get("inteiroTeor"))
    decisao = clean_text(registro.get("decisao"))

    # Em decisões monocráticas a API repete o texto integral em "ementa" e "inteiroTeor".
    # Acórdãos também trazem a ementa dentro do inteiro teor, mas ali ela é bem menor e deve ficar na frente.
    if ementa and inteiro_teor and min(len(ementa), len(inteiro_teor)) >= 0.9 * max(len(ementa), len(inteiro_teor)) \
            and (ementa in inteiro_teor or inteiro_teor in ementa):
        inteiro_teor = max(ementa, inteiro_teor, key=len)
        ementa = ""
    # Ementa primeiro: o embedder trunca textos longos e o inteiro teor começa com cabeçalho
    content = "\n\n".join(part for part in (ementa, inteiro_teor) if part) or decisao
    processo = (registro.get("processo") or "").strip()
    decision_date = iso_date(registro.get("dataJulgamento"))
    publication_date = iso_date(registro.get("dataPublicacao"))

    # A busca também devolve documentos que não são decisões (informativos e notas temáticas),
    # sem processo nem órgão julgador e com link próprio no site do TJDFT
    base_raw = registro.get("base")
    if base_raw == "informativo-jurisprudencia":
        title = f"TJDFT – Informativo de Jurisprudência nº {registro.get('edicaoIJ')} – {clean_text(registro.get('tituloIJ'))}"
        url = registro.get("linkIJ") or record_url(uuid, base_raw)
    elif base_raw == "jurisprudencia-foco":
        tema = (registro.get("paiJF") or {}).get("descricao")
        title = f"TJDFT – Jurisprudência em Foco – {tema + ': ' if tema else ''}{clean_text(registro.get('descricaoJF'))}"
        url = registro.get("linkJF") or record_url(uuid, base_raw)
    else:
        title = f"TJDFT – {BASE_LABELS.get(base, base)} {registro.get('identificador', '')} – Processo {processo}".strip()
        url = record_url(uuid, base_raw)
    orgao = registro.get("descricaoOrgaoJulgador")

    record = {
        "id": f"tjdft:{uuid}",
        "case_number": processo or None,
        "title": title,
        "document_type": DOCUMENT_TYPES.get(base_raw, base_raw),
        "content": content,
        "ementa": ementa,
        "court": "TJDFT",
        "tribunal": "TJDFT",
        # Decisões monocráticas não têm data de julgamento na API; usa a de publicação
        "date": decision_date or publication_date,
        "decision_date": decision_date,
        "publication_date": publication_date,
        "relator": registro.get("nomeRelator"),
        "orgao_julgador": registro.get("descricaoOrgaoJulgador"),
        "decision": decisao,
        "numero_acordao": registro.get("identificador"),
        "base": registro.get("base"),
        "subbase": registro.get("subbase"),
        "codigo_classe_cnj": registro.get("codigoClasseCnj"),
        "local_publicacao": registro.get("localDePublicacao"),
        "turma_recursal": registro.get("turmaRecursal"),
        "possui_inteiro_teor": bool(inteiro_teor),
        "uuid": uuid,
        "url": url,
        "legal_area": legal_area(orgao) if orgao else None,
        "cluster_name": primary_topic(topics),
        "topics": sorted(topics),
        "matched_queries": matched_queries,
        "source": "jurisdf_api",
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    # "Jurisprudência em Foco": notas temáticas do TJDFT que citam a decisão.
    # O conteúdo vem como Buffer (bytes) e é grande; guardamos só a referência.
    em_foco = [
        {k: v for k, v in item.items() if k != "conteudo"}
        for item in registro.get("jurisprudenciaEmFoco") or []
        if isinstance(item, dict)
    ]
    if em_foco:
        record["jurisprudencia_em_foco"] = em_foco
    if keep_html:
        record["inteiro_teor_html"] = registro.get("inteiroTeorHtml")
    return record
