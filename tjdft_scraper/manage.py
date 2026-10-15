#!/usr/bin/env python3
"""
TJDFT Jurisprudence Scraper Manager
"""

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from tjdft_scraper.client import TjdftApiError, TjdftClient
from tjdft_scraper.collector import TjdftCollector, load_queries
from tjdft_scraper.normalize import DOCUMENT_TYPES, NON_DECISION_BASES, clean_text, normalize_record

PROJECT_ROOT = Path(__file__).parent
DEFAULT_QUERIES = PROJECT_ROOT / "configs" / "queries_cftv_lgpd.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "tjdft_cftv_lgpd.jsonl"


def setup_logging():
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.FileHandler(log_dir / "app.log"), logging.StreamHandler()],
    )


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def run_crawl(args) -> bool:
    logger = logging.getLogger(__name__)
    output = resolve(args.out)

    if args.query:
        queries = [(q.partition("|")[0], q.partition("|")[2]) if "|" in q else ("manual", q) for q in args.query]
    else:
        queries = load_queries(resolve(args.queries))

    if output.exists() and not (args.resume or args.overwrite):
        logger.error(f"❌ {output} já existe. Use --resume para continuar ou --overwrite para recomeçar.")
        return False
    if args.overwrite:
        for path in (output, output.parent / f"{output.stem}_search_index.json"):
            path.unlink(missing_ok=True)

    logger.info("🎯 Starting TJDFT scraping")
    logger.info(f"   Queries: {len(queries)}")
    logger.info(f"   Output JSONL: {output}")
    logger.info(f"   Limit: {args.limit if args.limit else 'All'}")
    logger.info(f"   Full text: {not args.no_full_text} | PDF: {args.download_pdf} | Sinônimos: {args.sinonimos}")
    logger.info(f"   Resume: {args.resume}")

    collector = TjdftCollector(
        output_jsonl=output,
        client=TjdftClient(min_interval=args.delay),
        sinonimos=args.sinonimos == "true",
        full_text=not args.no_full_text,
        download_pdf=args.download_pdf,
        keep_html=args.keep_html,
        limit=args.limit,
    )
    try:
        report = collector.run(queries, resume=args.resume)
    except TjdftApiError as e:
        logger.error(f"❌ Erro na API do TJDFT: {e}. Rode novamente com --resume para continuar.")
        return False

    logger.info("📊 Final Results:")
    logger.info(f"   Unique records found: {report['unique_records']}")
    logger.info(f"   Written now: {report['written_now']} (total {report['written_total']})")
    logger.info(f"   Pending: {report['pending']} | Failed: {len(report['failed'])} | Empty content: {report['empty_content']}")
    logger.info(f"   Stats: {collector.stats_path}")
    return not report["failed"]


def show_status(args):
    output = resolve(args.out)
    if not output.exists():
        print(f"ℹ️  {output} não existe")
        return

    by_topic, by_base, by_area = Counter(), Counter(), Counter()
    total, with_full_text = 0, 0
    with open(output, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            with_full_text += record.get("possui_inteiro_teor", False)
            by_topic.update(record.get("topics") or [record.get("cluster_name")])
            by_base[record.get("subbase") or record.get("base")] += 1
            by_area[record.get("legal_area")] += 1

    print(f"📊 {output}")
    print(f"   Registros: {total} (com inteiro teor: {with_full_text})")
    print(f"   Por tema: {dict(by_topic.most_common())}")
    print(f"   Por base: {dict(by_base.most_common())}")
    print(f"   Por área: {dict(by_area.most_common())}")

    stats_path = output.parent / f"{output.stem}_stats.json"
    if stats_path.exists():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        print(f"\n🔎 Queries (gerado em {stats.get('generated_at')}):")
        for q in stats.get("queries", []):
            print(f"   {q['hits']:>6} hits  {q['collected']:>6} coletados  {q['segredo_skipped']:>3} segredo  {q['topic']}|{q['query']}")


def reclean(args):
    """Corrige registros gravados antes de uma mudança na normalização (não rodar durante o crawl).

    - reaplica clean_text nos campos de texto;
    - refaz informativos e notas "Jurisprudência em Foco" a partir da listagem guardada no índice
      de busca (a listagem já traz todo o texto desses documentos).
    """
    output = resolve(args.out)
    if not output.exists():
        print(f"ℹ️  {output} não existe")
        return
    index_path = output.parent / f"{output.stem}_search_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))["records"] if index_path.exists() else {}

    fields = ("content", "ementa", "decision")
    tmp = output.with_suffix(".jsonl.tmp")
    total, cleaned, rebuilt = 0, 0, 0
    with open(output, encoding="utf-8") as fin, open(tmp, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            entry = index.get(record["uuid"])
            if entry and entry["listing"].get("base") in NON_DECISION_BASES:
                collected_at = record.get("collected_at")
                record = normalize_record(entry["listing"], entry["queries"], entry["topics"])
                record["collected_at"] = collected_at or record["collected_at"]
                rebuilt += 1
            else:
                before = [record.get(field) for field in fields]
                for field in fields:
                    if record.get(field):
                        record[field] = clean_text(record[field])
                cleaned += before != [record.get(field) for field in fields]
                if not record.get("document_type"):
                    record["document_type"] = DOCUMENT_TYPES.get(record.get("base"), record.get("base"))
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(output)
    print(f"🧹 {total} registros: {cleaned} com texto limpo, {rebuilt} informativos/notas refeitos ({output})")


def main():
    parser = argparse.ArgumentParser(description="TJDFT Jurisprudence Scraper Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    crawl_parser = subparsers.add_parser("crawl", help="Search jurisdf and collect decisions")
    crawl_parser.add_argument("--queries", default=str(DEFAULT_QUERIES), help="File with 'topic|query' lines")
    crawl_parser.add_argument("--query", action="append", help="Ad-hoc query ('topic|query' or 'query'); repeatable, overrides --queries")
    crawl_parser.add_argument("--limit", type=int, help="Max number of records to fetch in this run")
    crawl_parser.add_argument("--no-full-text", action="store_true", help="Do not fetch inteiro teor (ementa only)")
    crawl_parser.add_argument("--download-pdf", action="store_true", help="Download inteiro teor PDFs to data/pdf/")
    crawl_parser.add_argument("--keep-html", action="store_true", help="Keep inteiro_teor_html in the JSONL")
    crawl_parser.add_argument("--sinonimos", choices=["true", "false"], default="true", help="Use jurisdf synonym expansion")
    crawl_parser.add_argument("--delay", type=float, default=1.0, help="Minimum seconds between requests")
    crawl_parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSONL file path")
    crawl_parser.add_argument("--resume", action="store_true", help="Resume from previous search index and JSONL")
    crawl_parser.add_argument("--overwrite", action="store_true", help="Discard previous output and start over")

    status_parser = subparsers.add_parser("status", help="Show collected data summary")
    status_parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSONL file path")

    reclean_parser = subparsers.add_parser("reclean", help="Re-apply text cleaning to an existing JSONL (not while crawling)")
    reclean_parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSONL file path")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    setup_logging()
    try:
        if args.command == "crawl":
            sys.exit(0 if run_crawl(args) else 1)
        elif args.command == "status":
            show_status(args)
        elif args.command == "reclean":
            reclean(args)
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user. Use --resume to continue.")
        sys.exit(1)


if __name__ == "__main__":
    main()
