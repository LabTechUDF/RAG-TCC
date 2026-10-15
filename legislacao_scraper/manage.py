#!/usr/bin/env python3
"""
Planalto Legislation Scraper Manager
"""

import argparse
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

# Add the current directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from legislacao_scraper.parser import build_records, html_to_blocks, parse_articles, slugify_code

PROJECT_ROOT = Path(__file__).parent
LAWS_CONFIG = PROJECT_ROOT / "configs" / "leis.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "legislacao.jsonl"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
# O Planalto derruba conexões cujo User-Agent não começa com "Mozilla/5.0"
USER_AGENT = "Mozilla/5.0 (compatible; RAG-TCC/legislacao_scraper; Academic Research; Contact: tcc@udf.edu.br)"

logger = logging.getLogger(__name__)


def setup_logging():
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.FileHandler(log_dir / "app.log"), logging.StreamHandler()],
    )


def download(url: str, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            if attempt == retries:
                raise
            logger.warning(f"⚠️ {url}: {e} (tentativa {attempt}/{retries})")
            time.sleep(5 * attempt)


def load_records(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_fetch(args) -> bool:
    output = Path(args.out).resolve()
    laws = json.loads(LAWS_CONFIG.read_text(encoding="utf-8"))
    only = {c.strip() for c in args.only.split(",")} if args.only else None
    if only:
        unknown = only - {law["code"] for law in laws}
        if unknown:
            logger.error(f"❌ Códigos desconhecidos: {sorted(unknown)}")
            return False
        laws = [law for law in laws if law["code"] in only]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    new_records, report, failed = [], {}, []
    for n, law in enumerate(laws, 1):
        raw_path = RAW_DIR / f"{slugify_code(law['code'])}.htm"
        if raw_path.exists() and not args.refresh:
            raw = raw_path.read_bytes()
        else:
            if n > 1:
                time.sleep(args.delay)
            logger.info(f"⬇️  [{n}/{len(laws)}] {law['code']}: {law['url']}")
            try:
                raw = download(law["url"])
            except requests.RequestException as e:
                logger.error(f"❌ {law['code']}: falha no download ({e})")
                failed.append(law["code"])
                continue
            raw_path.write_bytes(raw)

        blocks, html_stats = html_to_blocks(raw)
        articles, parse_stats = parse_articles(blocks, law["code"], law.get("adct_code"))
        records, record_stats = build_records(law, articles, fetched_at)
        new_records.extend(records)
        report[law["code"]] = {**html_stats, **parse_stats, **record_stats}
        logger.info(f"📜 {law['code']}: {record_stats['articles']} artigos, {record_stats['records']} registros, "
                    f"{record_stats['revoked_skipped']} revogados, {html_stats['struck_removed']} trechos riscados removidos")

    # Com --only, preserva os registros das demais leis já gravados
    codes = {r["code"] for r in new_records} | {law.get("adct_code") for law in laws if law.get("adct_code")}
    kept = [r for r in load_records(output) if only and r["code"] not in codes]
    tmp = output.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for record in kept + new_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(output)

    stats_path = output.parent / "legislacao_stats.json"
    stats_path.write_text(json.dumps({"generated_at": fetched_at, "laws": report}, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"✅ {len(kept) + len(new_records)} registros em {output}")
    if failed:
        logger.error(f"❌ Leis não baixadas: {failed}. Rode novamente com --only {','.join(failed)}")
    return not failed


def show_stats(args):
    records = load_records(Path(args.out).resolve())
    if not records:
        print("ℹ️  Nenhum registro encontrado")
        return
    articles = {code: set() for code in {r["code"] for r in records}}
    parts = Counter()
    for r in records:
        articles[r["code"]].add(r["article"])
        parts[r["code"]] += 1
    print(f"{'Código':<14}{'Artigos':>9}{'Registros':>11}")
    for code in sorted(articles):
        print(f"{code:<14}{len(articles[code]):>9}{parts[code]:>11}")
    print(f"{'TOTAL':<14}{sum(len(a) for a in articles.values()):>9}{len(records):>11}")


def show_article(args):
    found = [r for r in load_records(Path(args.out).resolve()) if r["code"] == args.code and r["article"] == args.article]
    if not found:
        print(f"ℹ️  {args.code} art. {args.article} não encontrado")
    for r in found:
        print(f"[{r['id']}] {r['title']}\n{r['text']}\n")


def main():
    parser = argparse.ArgumentParser(description="Planalto Legislation Scraper Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    fetch_parser = subparsers.add_parser("fetch", help="Download laws and split them by article")
    fetch_parser.add_argument("--only", help="Comma separated codes from configs/leis.json (e.g. LGPD,CC)")
    fetch_parser.add_argument("--refresh", action="store_true", help="Ignore cached HTML in data/raw/")
    fetch_parser.add_argument("--delay", type=float, default=2.0, help="Seconds between downloads")
    fetch_parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSONL file path")

    stats_parser = subparsers.add_parser("stats", help="Show article counts per law")
    stats_parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="JSONL file path")

    show_parser = subparsers.add_parser("show", help="Print one article")
    show_parser.add_argument("code", help="Law code, e.g. CC")
    show_parser.add_argument("article", help="Article id, e.g. 1277 or 5-A")
    show_parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="JSONL file path")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    setup_logging()
    try:
        if args.command == "fetch":
            sys.exit(0 if run_fetch(args) else 1)
        elif args.command == "stats":
            show_stats(args)
        elif args.command == "show":
            show_article(args)
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
