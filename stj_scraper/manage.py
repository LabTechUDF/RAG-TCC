#!/usr/bin/env python3
"""
STJ Dataset Scraper Manager
"""

import argparse
import sys
from pathlib import Path
import logging
import os

# Add the current directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# STJDatasetScraper (Scrapy) é importado só nos comandos que o usam: open-data não depende do Scrapy
from stj_scraper.open_data import build as od_build, search as od_search, sync as od_sync
from stj_scraper.open_data.ckan import ESPELHOS_ORGAOS, CkanClient


class STJScraperManager:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = self.project_root / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'app.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(name)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def run_stj_crawl(self, dataset_url=None, limit=None, article_filter=None, 
                      cluster_order='article', out_dir='data', output_jsonl=None,
                      resume=False, write_txt=False):
        """Execute STJ dataset crawling"""
        
        # Default values
        if dataset_url is None:
            dataset_url = "https://dadosabertos.web.stj.jus.br/dataset/integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica"
        
        if output_jsonl is None:
            output_jsonl = str(self.project_root / out_dir / 'stj_decisoes_monocraticas.jsonl')
        
        self.logger.info("🎯 Starting STJ Dataset Scraping")
        self.logger.info(f"   Dataset URL: {dataset_url}")
        self.logger.info(f"   Output JSONL: {output_jsonl}")
        self.logger.info(f"   Limit: {limit if limit else 'All'}")
        self.logger.info(f"   Article Filter: {article_filter if article_filter else 'All'}")
        self.logger.info(f"   Cluster Order: {cluster_order}")
        self.logger.info(f"   Resume: {resume}")
        self.logger.info(f"   Write TXT files: {write_txt}")
        
        try:
            from stj_scraper.stj_queue_manager import STJDatasetScraper

            scraper = STJDatasetScraper(
                project_root=self.project_root,
                dataset_url=dataset_url,
                output_jsonl=output_jsonl,
                article_filter=article_filter,
                cluster_order=cluster_order,
                limit=limit,
                write_txt=write_txt
            )
            
            report = scraper.run_scraping(resume=resume)
            
            if 'error' in report:
                self.logger.error(f"❌ Scraping failed: {report['error']}")
                return False
            
            # Log final report
            self.logger.info("📊 Final Results:")
            self.logger.info(f"   Zips processed: {report.get('zips_processed', 0)}")
            self.logger.info(f"   Decisions found: {report.get('decisions_found', 0)}")
            self.logger.info(f"   Monocratic decisions: {report.get('monocratic_decisions', 0)}")
            self.logger.info(f"   TXT files found: {report.get('txt_files_found', 0)}")
            self.logger.info(f"   JSONL lines written: {report.get('jsonl_lines_written', 0)}")
            
            success_rate = (report.get('jsonl_lines_written', 0) / max(report.get('monocratic_decisions', 1), 1)) * 100
            self.logger.info(f"   Success rate: {success_rate:.1f}%")
            
            return success_rate >= 50
            
        except Exception as e:
            self.logger.error(f"❌ Error in STJ scraping: {e}")
            return False
    
    def show_queue_status(self):
        """Show current queue status"""
        from stj_scraper.stj_queue_manager import STJDatasetScraper

        scraper = STJDatasetScraper(self.project_root)
        status = scraper.get_queue_status()
        
        print("📊 STJ Queue Status:")
        print(f"   Resources remaining: {status.get('remaining_resources', 0)}")
        print(f"   Resources completed: {status.get('completed_resources', 0)}")
        print(f"   Resources failed: {status.get('failed_resources', 0)}")
        print(f"   Progress: {status.get('progress_percentage', 0):.1f}%")
        
        if status.get('next_resources'):
            print(f"   Next resources: {', '.join(status['next_resources'][:5])}")
        
        if status.get('total_resources', 0) == 0:
            print("   ℹ️  No active queue found")
    
    def cleanup_queue_files(self):
        """Clean up queue state files"""
        from stj_scraper.stj_queue_manager import STJDatasetScraper

        scraper = STJDatasetScraper(self.project_root)
        scraper.cleanup_queue_files()
        print("✅ Queue files cleaned up")


def run_open_data(args, project_root: Path) -> bool:
    """open-data sync | build | search | text | status"""
    import json

    data_dir = Path(args.data_dir) if args.data_dir else project_root / 'data' / 'open_data'
    db_path = data_dir / 'stj_open_data.sqlite'
    what = tuple(w.strip() for w in getattr(args, 'what', 'integras,espelhos').split(',') if w.strip())

    if args.od_command == 'sync':
        orgaos = [o.strip() for o in args.orgaos.split(',')] if args.orgaos else None
        report = od_sync.sync(data_dir, CkanClient(delay=args.delay), what=what, since=args.since,
                              until=args.until, orgaos=orgaos, limit=args.limit)
        missing = report.pop('days_metadata_without_texts', [])
        print(f"📦 sync: {report} | days with metadata but no texts: {len(missing)} {missing[:5]}")
        return not report.get('failed')

    if args.od_command == 'build':
        report = od_build.build(data_dir, db_path, what=what, since=args.since, until=args.until, limit=args.limit)
        print(f"📚 build: {report}")
        return True

    if args.od_command == 'search':
        if not db_path.exists():
            print(f"❌ {db_path} não existe — rode open-data sync e build primeiro")
            return False
        results = od_search.search(db_path, args.query, scope=args.scope, limit=args.limit, tipo=args.tipo,
                                   desde=args.desde, ate=args.ate, ministro=args.ministro, orgao=args.orgao,
                                   classe=args.classe)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return True
        for source, items in results.items():
            print(f"\n=== {source}: {len(items)} resultados")
            for r in items:
                data = r.get('data_decisao') or r.get('data_publicacao')
                pessoa = r.get('relator') or r.get('ministro')
                print(f"  {r['score']:>8} {r['id']:<22} {r.get('processo') or '':<22} {r.get('tipo') or '':<9} {data or '':<10} {pessoa or ''}")
                if r.get('snippet'):
                    print(f"           {r['snippet'][:300]}")
        return True

    if args.od_command == 'text':
        doc = od_search.get_text(db_path, args.seq)
        if not doc:
            print(f"❌ SeqDocumento {args.seq} não encontrado")
            return False
        print(f"{doc['processo']} | {doc['tipo']} | {doc['data_publicacao']} | {doc['ministro']}\n\n{doc['text']}")
        return True

    if args.od_command == 'status':
        print(json.dumps(od_search.status(db_path), ensure_ascii=False, indent=2))
        return True

    print("use: open-data {sync,build,search,text,status}")
    return False


def main():
    parser = argparse.ArgumentParser(description='STJ Dataset Scraper Manager')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # STJ crawl command
    stj_parser = subparsers.add_parser('stj', help='STJ dataset operations')
    stj_subparsers = stj_parser.add_subparsers(dest='stj_command', help='STJ commands')
    
    crawl_parser = stj_subparsers.add_parser('crawl', help='Crawl STJ dataset')
    crawl_parser.add_argument('--dataset-url', help='Dataset URL')
    crawl_parser.add_argument('--limit', type=int, help='Limit number of resources to process')
    crawl_parser.add_argument('--article-filter', help='Filter by article numbers (comma separated)')
    crawl_parser.add_argument('--cluster-order', choices=['article', 'random'], default='article', help='Clustering order')
    crawl_parser.add_argument('--out', default='data', help='Output directory')
    crawl_parser.add_argument('--output-jsonl', help='Output JSONL file path')
    crawl_parser.add_argument('--resume', action='store_true', help='Resume from previous state')
    crawl_parser.add_argument('--write-txt', type=str, default='false', choices=['true', 'false'], help='Write TXT files to disk')
    
    # Status and cleanup commands
    subparsers.add_parser('status', help='Show current queue status')
    subparsers.add_parser('cleanup', help='Clean up queue state files')

    # STJ open data (dadosabertos.web.stj.jus.br): sync -> build -> search
    od_parser = subparsers.add_parser('open-data', help='STJ open data: íntegras + espelhos, local term search')
    od_parser.add_argument('--data-dir', default=None, help='Base directory (default: data/open_data)')
    od_sub = od_parser.add_subparsers(dest='od_command', help='open-data commands')

    od_sync_p = od_sub.add_parser('sync', help='Download/refresh files from the open data portal (incremental)')
    od_sync_p.add_argument('--what', default='integras,espelhos', help='integras,espelhos')
    od_sync_p.add_argument('--since', help='First day (YYYY-MM-DD)')
    od_sync_p.add_argument('--until', help='Last day (YYYY-MM-DD)')
    od_sync_p.add_argument('--orgaos', help=f"Espelhos panels (comma separated): {','.join(ESPELHOS_ORGAOS)}")
    od_sync_p.add_argument('--limit', type=int, help='Max files to download in this run')
    od_sync_p.add_argument('--delay', type=float, default=1.0, help='Seconds between requests')

    od_build_p = od_sub.add_parser('build', help='Ingest downloaded files into SQLite FTS5 (incremental)')
    od_build_p.add_argument('--what', default='integras,espelhos', help='integras,espelhos')
    od_build_p.add_argument('--since', help='First day (YYYY-MM-DD)')
    od_build_p.add_argument('--until', help='Last day (YYYY-MM-DD)')
    od_build_p.add_argument('--limit', type=int, help='Max files to ingest in this run')

    od_search_p = od_sub.add_parser('search', help='Search any term (FTS5 syntax: "frase", OR, NOT, NEAR, prefixo*)')
    od_search_p.add_argument('query')
    od_search_p.add_argument('--scope', choices=['all', 'espelhos', 'integras'], default='all')
    od_search_p.add_argument('--tipo', help='ACÓRDÃO or DECISÃO')
    od_search_p.add_argument('--desde', help='YYYY-MM-DD')
    od_search_p.add_argument('--ate', help='YYYY-MM-DD')
    od_search_p.add_argument('--ministro', help='Relator/ministro (partial name)')
    od_search_p.add_argument('--orgao', help='Órgão julgador (espelhos, partial name)')
    od_search_p.add_argument('--classe', help='Class, e.g. REsp, AREsp')
    od_search_p.add_argument('--limit', type=int, default=10)
    od_search_p.add_argument('--json', action='store_true', help='Print JSON')

    od_text_p = od_sub.add_parser('text', help='Print the full text of an íntegra by SeqDocumento')
    od_text_p.add_argument('seq', type=int)

    od_sub.add_parser('status', help='Show corpus counts and periods')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = STJScraperManager()
    
    try:
        if args.command == 'stj' and args.stj_command == 'crawl':
            write_txt = args.write_txt.lower() == 'true'
            success = manager.run_stj_crawl(
                dataset_url=args.dataset_url,
                limit=args.limit,
                article_filter=args.article_filter,
                cluster_order=args.cluster_order,
                out_dir=args.out,
                output_jsonl=args.output_jsonl,
                resume=args.resume,
                write_txt=write_txt
            )
            sys.exit(0 if success else 1)
        
        elif args.command == 'status':
            manager.show_queue_status()
        
        elif args.command == 'cleanup':
            manager.cleanup_queue_files()

        elif args.command == 'open-data':
            sys.exit(0 if run_open_data(args, manager.project_root) else 1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()