"""
Coleta em duas fases:
1. Busca: roda todas as queries, pagina os resultados e monta um índice
   uuid -> {topics, queries, listing}. Checkpoint salvo a cada query.
2. Inteiro teor: busca cada uuid ainda não gravado e grava no JSONL (append).
Ao final, sincroniza matched_queries/topics dos registros já gravados.
"""
import json
import logging
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .client import MAX_PAGE_SIZE, TjdftApiError, TjdftClient
from .normalize import normalize_record, primary_topic

logger = logging.getLogger(__name__)


def load_queries(path: Path) -> List[Tuple[str, str]]:
    """Lê arquivo 'tema|query' (linhas vazias e # são ignoradas)."""
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        topic, sep, query = line.partition("|")
        queries.append((topic.strip(), query.strip()) if sep else ("manual", topic.strip()))
    return queries


def slim_listing(registro: Dict[str, Any], full_text: bool) -> None:
    """Remove campos pesados da listagem antes de guardar no índice de busca.

    - inteiroTeor só é descartado quando o fetch_full vai trazê-lo de novo (possuiInteiroTeor);
      decisões monocráticas vêm com possuiInteiroTeor=false, mas com o texto integral na listagem.
    - jurisprudenciaEmFoco só vem na listagem (o registro completo de acórdãos não traz);
      guarda a referência sem o conteúdo, que vem em bytes e é grande.
    """
    for heavy in ("marcadores", "inteiroTeorHtml"):
        registro.pop(heavy, None)
    if full_text and registro.get("possuiInteiroTeor"):
        registro.pop("inteiroTeor", None)
    if registro.get("jurisprudenciaEmFoco"):
        registro["jurisprudenciaEmFoco"] = [
            {k: v for k, v in item.items() if k != "conteudo"}
            for item in registro["jurisprudenciaEmFoco"]
            if isinstance(item, dict)
        ]



def _write_json_atomic(path: Path, data: Any, compact: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(data, ensure_ascii=False, indent=2)
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class TjdftCollector:
    def __init__(
        self,
        output_jsonl: Path,
        client: TjdftClient,
        sinonimos: bool = True,
        full_text: bool = True,
        download_pdf: bool = False,
        keep_html: bool = False,
        limit: Optional[int] = None,
    ):
        self.output_jsonl = output_jsonl
        self.client = client
        self.sinonimos = sinonimos
        self.full_text = full_text
        self.download_pdf = download_pdf
        self.keep_html = keep_html
        self.limit = limit

        data_dir = output_jsonl.parent
        data_dir.mkdir(parents=True, exist_ok=True)
        self.search_index_path = data_dir / f"{output_jsonl.stem}_search_index.json"
        self.stats_path = data_dir / f"{output_jsonl.stem}_stats.json"
        self.pdf_dir = data_dir / "pdf"

    def run(self, queries: List[Tuple[str, str]], resume: bool = False) -> Dict[str, Any]:
        if resume and self.search_index_path.exists():
            index = json.loads(self.search_index_path.read_text(encoding="utf-8"))
        else:
            index = {"queries": {}, "records": {}}

        self._search_all(queries, index)
        report = self._fetch_all(index)
        self._sync_matches(index)

        report["queries"] = list(index["queries"].values())
        report["unique_records"] = len(index["records"])
        report["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_json_atomic(self.stats_path, report)
        return report

    # ------------------------------------------------------------------ busca
    def _search_all(self, queries: List[Tuple[str, str]], index: Dict[str, Any]) -> None:
        for n, (topic, query) in enumerate(queries, 1):
            key = f"{topic}|{query}"
            if index["queries"].get(key, {}).get("done"):
                logger.info(f"⏭️  [{n}/{len(queries)}] já buscada: {key}")
                continue

            first = self.client.search(query, 0, MAX_PAGE_SIZE, self.sinonimos)
            hits = (first.get("hits") or {}).get("value", 0)
            pages = math.ceil(hits / MAX_PAGE_SIZE)
            logger.info(f"🔎 [{n}/{len(queries)}] {key}: {hits} resultados, {pages} páginas")

            found, segredo = 0, 0
            for pagina in range(pages):
                data = first if pagina == 0 else self.client.search(query, pagina, MAX_PAGE_SIZE, self.sinonimos)
                registros = data.get("registros") or []
                if not registros:
                    logger.warning(f"⚠️ Página {pagina} vazia para '{query}', interrompendo paginação")
                    break
                for registro in registros:
                    if registro.get("segredoJustica"):
                        segredo += 1
                        continue
                    slim_listing(registro, self.full_text)
                    entry = index["records"].setdefault(
                        registro["uuid"], {"topics": [], "queries": [], "listing": registro}
                    )
                    if topic not in entry["topics"]:
                        entry["topics"].append(topic)
                    if query not in entry["queries"]:
                        entry["queries"].append(query)
                    found += 1

            index["queries"][key] = {
                "topic": topic,
                "query": query,
                "hits": hits,
                "pages": pages,
                "collected": found,
                "segredo_skipped": segredo,
                "done": True,
            }
            _write_json_atomic(self.search_index_path, index, compact=True)

    # --------------------------------------------------------- inteiro teor
    def _written_uuids(self) -> Set[str]:
        if not self.output_jsonl.exists():
            return set()
        uuids = set()
        with open(self.output_jsonl, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    uuids.add(json.loads(line)["uuid"])
        return uuids

    def _fetch_all(self, index: Dict[str, Any]) -> Dict[str, Any]:
        written = self._written_uuids()
        todo = [uuid for uuid in index["records"] if uuid not in written]
        if self.limit:
            todo = todo[: self.limit]
        logger.info(f"📥 {len(written)} já gravados, {len(todo)} a buscar")

        counts = Counter()
        failed: List[str] = []
        with open(self.output_jsonl, "a", encoding="utf-8") as f:
            for n, uuid in enumerate(todo, 1):
                entry = index["records"][uuid]
                registro = entry["listing"]

                if self.full_text and registro.get("possuiInteiroTeor", True):
                    try:
                        full = self.client.fetch_full(uuid)
                    except TjdftApiError as e:
                        logger.error(f"❌ Falha ao buscar inteiro teor {uuid}: {e}")
                        failed.append(uuid)
                        continue
                    if full:
                        registro = {**registro, **full}
                    else:
                        counts["full_text_missing"] += 1

                if self.download_pdf and registro.get("possuiInteiroTeor"):
                    try:
                        if self.client.download_pdf(uuid, self.pdf_dir / f"{uuid}.pdf"):
                            counts["pdfs"] += 1
                    except TjdftApiError as e:
                        logger.warning(f"⚠️ Falha ao baixar PDF {uuid}: {e}")

                record = normalize_record(registro, entry["queries"], entry["topics"], self.keep_html)
                if not record["content"]:
                    counts["empty_content"] += 1
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                counts["written"] += 1

                if n % 25 == 0 or n == len(todo):
                    logger.info(f"   {n}/{len(todo)} gravados")

        return {
            "written_now": counts["written"],
            "written_total": len(written) + counts["written"],
            "pending": len(index["records"]) - len(written) - counts["written"],
            "failed": failed,
            "empty_content": counts["empty_content"],
            "full_text_missing": counts["full_text_missing"],
            "pdfs_downloaded": counts["pdfs"],
        }

    def _sync_matches(self, index: Dict[str, Any]) -> None:
        """Atualiza matched_queries/topics de registros gravados em execuções anteriores."""
        if not self.output_jsonl.exists():
            return
        changed = 0
        lines = []
        with open(self.output_jsonl, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                entry = index["records"].get(record["uuid"])
                if entry and (record.get("matched_queries") != entry["queries"] or record.get("topics") != sorted(entry["topics"])):
                    record["matched_queries"] = entry["queries"]
                    record["topics"] = sorted(entry["topics"])
                    record["cluster_name"] = primary_topic(entry["topics"])
                    changed += 1
                lines.append(json.dumps(record, ensure_ascii=False))
        if changed:
            tmp = self.output_jsonl.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(self.output_jsonl)
            logger.info(f"🔄 {changed} registros com matched_queries/topics atualizados")
