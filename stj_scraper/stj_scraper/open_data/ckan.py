"""
Cliente da API CKAN do portal de dados abertos do STJ.

O portal não passa pelo Cloudflare; o projeto se identifica no User-Agent e espaça as requisições.
Os nomes dos arquivos variam ao longo dos anos ("metadados20210104", "metadados20220502.json",
"Metadados 20240203", "20240205" -> textos20240205.zip, meses de 2022 como "202202.zip"), então cada
recurso é classificado pelo nome e pela URL e recebe uma chave de data (YYYYMMDD ou YYYYMM).
"""
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

import requests

BASE_URL = "https://dadosabertos.web.stj.jus.br"
USER_AGENT = "RAG-TCC/stj_scraper (Academic Research; Contact: tcc@udf.edu.br)"
INTEGRAS_DATASET = "integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica"
ESPELHOS_ORGAOS = [
    "corte-especial", "primeira-secao", "segunda-secao", "terceira-secao", "primeira-turma",
    "segunda-turma", "terceira-turma", "quarta-turma", "quinta-turma", "sexta-turma",
]
RETRY_STATUS = {429, 500, 502, 503, 504}
DATE_KEY_RE = re.compile(r"(20\d{2}(?:0[1-9]|1[0-2])(?:[0-3]\d)?)(?!\d)")

logger = logging.getLogger(__name__)


def espelhos_dataset(orgao: str) -> str:
    return f"espelhos-de-acordaos-{orgao}"


@dataclass
class Resource:
    dataset: str
    resource_id: str
    name: str
    url: str
    format: str
    size: int
    last_modified: str
    kind: str   # metadados | textos | espelho | outro
    key: str    # YYYYMMDD (ou YYYYMM nos arquivos mensais)

    def local_path(self, raw_dir: Path) -> Path:
        if self.kind == "metadados":
            return raw_dir / "integras" / "metadados" / f"{self.key}.json"
        if self.kind == "textos":
            return raw_dir / "integras" / "textos" / f"{self.key}.zip"
        if self.kind == "espelho":
            orgao = self.dataset.replace("espelhos-de-acordaos-", "")
            return raw_dir / "espelhos" / orgao / f"{self.key}.json"
        return raw_dir / "outros" / self.dataset / (self.url.rsplit("/", 1)[-1] or self.resource_id)


def classify(dataset: str, raw: dict) -> Resource:
    name = (raw.get("name") or "").strip()
    url = (raw.get("url") or "").strip()
    fmt = (raw.get("format") or "").upper()
    tail = url.rsplit("/", 1)[-1].lower()
    probe = f"{name.lower()} {tail}"
    match = DATE_KEY_RE.search(re.sub(r"\s+", "", name)) or DATE_KEY_RE.search(tail)
    key = match.group(1) if match else ""

    if dataset == INTEGRAS_DATASET:
        if "dicionario" in probe or not key:
            kind = "outro"
        elif "metadados" in probe:
            kind = "metadados"
        elif "textos" in probe or tail.endswith(".zip") or name.lower().endswith(".zip") or fmt == "ZIP":
            kind = "textos"
        else:
            kind = "outro"
    else:
        kind = "espelho" if key and (fmt == "JSON" or tail.endswith(".json") or name.lower().endswith(".json")) else "outro"

    return Resource(
        dataset=dataset, resource_id=raw.get("id", ""), name=name, url=url, format=fmt,
        size=int(raw.get("size") or 0), last_modified=raw.get("last_modified") or raw.get("created") or "",
        kind=kind, key=key,
    )


class CkanClient:
    """Requisições espaçadas, com novas tentativas em 429/5xx/timeouts."""

    def __init__(self, delay: float = 1.0, timeout: int = 120, retries: int = 4):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self._last = 0.0

    def _get(self, url: str, **kwargs) -> requests.Response:
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == self.retries:
                    raise
                logger.warning(f"⚠️ {e.__class__.__name__} em {url} (tentativa {attempt}/{self.retries})")
                time.sleep(5 * attempt)
                continue
            if resp.status_code in RETRY_STATUS and attempt < self.retries:
                retry_after = resp.headers.get("Retry-After", "")
                delay = min(int(retry_after), 300) if retry_after.isdigit() else 10 * attempt
                logger.warning(f"⚠️ HTTP {resp.status_code} em {url} (tentativa {attempt}/{self.retries}), aguardando {delay}s")
                resp.close()
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"tentativas esgotadas: {url}")

    def resources(self, dataset: str) -> List[Resource]:
        data = self._get(f"{BASE_URL}/api/3/action/package_show", params={"id": dataset}).json()
        if not data.get("success"):
            raise RuntimeError(f"CKAN package_show falhou para {dataset}")
        return [classify(dataset, r) for r in data["result"].get("resources", [])]

    def download(self, resource: Resource, dest: Path) -> int:
        """Baixa em arquivo .part e só renomeia no fim (download interrompido não vira arquivo válido)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        written = 0
        with self._get(resource.url, stream=True) as resp:
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
                        written += len(chunk)
        part.replace(dest)
        return written
