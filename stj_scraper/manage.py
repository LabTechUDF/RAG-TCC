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

from stj_scraper.stj_queue_manager import STJDatasetScraper


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
        scraper = STJDatasetScraper(self.project_root)
        scraper.cleanup_queue_files()
        print("✅ Queue files cleaned up")


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
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()