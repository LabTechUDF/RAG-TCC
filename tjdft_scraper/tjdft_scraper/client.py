"""
Cliente HTTP para a API pública de jurisprudência do TJDFT (jurisdf).

Endpoints (descobertos no bundle Angular de https://jurisdf.tjdft.jus.br):
- POST /api/v1/pesquisa                  -> busca paginada (tamanho máximo 40)
- POST /api/v1/pesquisa (uuid + retornaInteiroTeor) -> registro com inteiro teor
- GET  /api/v1/pesquisa/download/{uuid}  -> PDF do inteiro teor
"""
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

API_URL = "https://jurisdf.tjdft.jus.br/api/v1/pesquisa"
DOWNLOAD_URL = "https://jurisdf.tjdft.jus.br/api/v1/pesquisa/download/{uuid}"
MAX_PAGE_SIZE = 40
USER_AGENT = "RAG-TCC/tjdft_scraper (Academic Research; Contact: tcc@udf.edu.br)"
RETRY_STATUS = {429, 500, 502, 503, 504}

logger = logging.getLogger(__name__)


class TjdftApiError(RuntimeError):
    """Erro definitivo ao chamar a API do TJDFT."""


class TjdftClient:
    """Cliente com throttle entre requisições e retry com backoff exponencial."""

    def __init__(self, min_interval: float = 1.0, timeout: int = 60, max_retries: int = 5):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request = 0.0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == self.max_retries:
                    raise TjdftApiError(f"{method} {url}: {e}") from e
                delay = 2 ** attempt
                logger.warning(f"⚠️ {e.__class__.__name__} (tentativa {attempt}/{self.max_retries}), nova tentativa em {delay}s")
                time.sleep(delay)
                continue

            if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                retry_after = resp.headers.get("Retry-After", "")
                delay = int(retry_after) if retry_after.isdigit() else 2 ** attempt
                logger.warning(f"⚠️ HTTP {resp.status_code} (tentativa {attempt}/{self.max_retries}), nova tentativa em {delay}s")
                time.sleep(delay)
                continue

            if resp.status_code >= 400:
                raise TjdftApiError(f"{method} {url}: HTTP {resp.status_code} {resp.text[:300]}")
            return resp

        raise TjdftApiError(f"{method} {url}: tentativas esgotadas")

    def search(self, query: str, pagina: int = 0, tamanho: int = MAX_PAGE_SIZE, sinonimos: bool = True) -> Dict[str, Any]:
        """Busca uma página de resultados (pagina começa em 0)."""
        payload = {
            "query": query,
            "termosAcessorios": [],
            "pagina": pagina,
            "tamanho": min(tamanho, MAX_PAGE_SIZE),
            "sinonimos": sinonimos,
            "espelho": True,
            "inteiroTeor": False,
            "retornaTotalizacao": False,
        }
        return self._request("POST", API_URL, json=payload).json()

    def fetch_full(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Busca um registro pelo uuid, incluindo o inteiro teor."""
        payload = {
            "termosAcessorios": [{"campo": "uuid", "valor": uuid}],
            "pagina": 0,
            "tamanho": 1,
            "espelho": False,
            "inteiroTeor": False,
            "sinonimos": False,
            "retornaInteiroTeor": True,
            "retornaTotalizacao": False,
        }
        registros = self._request("POST", API_URL, json=payload).json().get("registros") or []
        return registros[0] if registros else None

    def download_pdf(self, uuid: str, path: Path) -> bool:
        """Baixa o PDF do inteiro teor. Retorna False se a resposta não for PDF."""
        resp = self._request("GET", DOWNLOAD_URL.format(uuid=uuid), headers={"Accept": "application/pdf"})
        if "pdf" not in resp.headers.get("Content-Type", ""):
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return True
