"""
Download incremental dos dados abertos do STJ para data/open_data/raw/.

O manifest (raw/manifest.json) guarda URL, last_modified e tamanho de cada arquivo baixado: um arquivo
só é baixado de novo se o recurso mudou no portal ou se sumiu do disco.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .ckan import ESPELHOS_ORGAOS, INTEGRAS_DATASET, CkanClient, Resource, espelhos_dataset

logger = logging.getLogger(__name__)


def normalize_day(value: Optional[str]) -> Optional[str]:
    """'2025-06-12' ou '20250612' -> '20250612'."""
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) not in (6, 8):
        raise ValueError(f"data inválida: {value} (use YYYY-MM-DD)")
    return digits


def in_window(key: str, since: Optional[str], until: Optional[str]) -> bool:
    """Compara chaves YYYYMMDD; arquivos mensais (YYYYMM) cobrem o mês inteiro."""
    start, end = (key + "01", key + "31") if len(key) == 6 else (key, key)
    if since and end < since.ljust(8, "0"):
        return False
    if until and start > until.ljust(8, "9"):
        return False
    return True


def load_manifest(path: Path) -> Dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_manifest(path: Path, manifest: Dict[str, dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def list_resources(client: CkanClient, what: Iterable[str], orgaos: Optional[List[str]]) -> List[Resource]:
    resources: List[Resource] = []
    if "integras" in what:
        resources += [r for r in client.resources(INTEGRAS_DATASET) if r.kind in ("metadados", "textos")]
    if "espelhos" in what:
        for orgao in orgaos or ESPELHOS_ORGAOS:
            resources += [r for r in client.resources(espelhos_dataset(orgao)) if r.kind == "espelho"]
    return resources


def sync(data_dir: Path, client: CkanClient, what: Iterable[str] = ("integras", "espelhos"),
         since: Optional[str] = None, until: Optional[str] = None, orgaos: Optional[List[str]] = None,
         limit: Optional[int] = None) -> Dict:
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    since, until = normalize_day(since), normalize_day(until)

    resources = [r for r in list_resources(client, what, orgaos) if in_window(r.key, since, until)]
    # Mesmo arquivo publicado duas vezes: fica o mais recente
    latest: Dict[str, Resource] = {}
    for r in resources:
        path = str(r.local_path(raw_dir))
        if path not in latest or r.last_modified > latest[path].last_modified:
            latest[path] = r
    logger.info(f"📦 {len(latest)} arquivos no recorte ({Counter(r.kind for r in latest.values())})")

    stats = Counter()
    for n, (path_str, r) in enumerate(sorted(latest.items()), 1):
        path = Path(path_str)
        entry = manifest.get(path_str)
        if path.exists() and entry and entry.get("url") == r.url and entry.get("last_modified") == r.last_modified:
            stats["skipped"] += 1
            continue
        if limit and stats["downloaded"] >= limit:
            stats["not_downloaded_limit"] += 1
            continue
        try:
            size = client.download(r, path)
        except Exception as e:
            logger.error(f"❌ {r.dataset}/{r.name}: {e}")
            stats["failed"] += 1
            continue
        manifest[path_str] = {
            "dataset": r.dataset, "resource_id": r.resource_id, "name": r.name, "url": r.url, "kind": r.kind,
            "key": r.key, "last_modified": r.last_modified, "size": size,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        save_manifest(manifest_path, manifest)
        stats["downloaded"] += 1
        stats["bytes"] += size
        if stats["downloaded"] % 25 == 0:
            logger.info(f"   {n}/{len(latest)} verificados, {stats['downloaded']} baixados ({stats['bytes'] / 1e9:.2f} GB)")

    days_meta = {r.key for r in latest.values() if r.kind == "metadados"}
    days_text = {r.key for r in latest.values() if r.kind == "textos"}
    report = dict(stats)
    report["days_metadata_without_texts"] = sorted(days_meta - days_text)
    return report
