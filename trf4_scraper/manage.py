#!/usr/bin/env python3
"""
TRF 4ª Região Queue-Based Scraper Manager
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Garante que o pacote 4r_scraper pode ser importado ao rodar diretamente
sys.path.insert(0, str(Path(__file__).parent))

from trf4_scraper.trf4_scraper.trf4_queue_manager import run_fr_queue_based, TRF4QueryQueue


class TRF4QueueManager:
    def __init__(self):
        self.project_root = Path(__file__).parent
    
    def run_fr_sequential_queue(self, show_browser=False):
        print("🎯 Running TRF 4ª Região Jurisprudência with Sequential Queue Architecture")
        query_file = self.project_root / 'data' / 'simple_query_spider' / 'query_links.json'
        
        if not query_file.exists():
            print(f"❌ Query file not found: {query_file}")
            return False
        
        try:
            report = run_fr_queue_based(self.project_root, query_file, show_browser)
            
            if 'error' in report:
                print(f"❌ Queue processing failed: {report['error']}")
                return False
            
            success_rate = (report['successful'] / report['total_queries']) * 100
            return success_rate >= 50
            
        except Exception as e:
            print(f"❌ Error in queue-based processing: {e}")
            return False
    
    def run_fr_concurrent_queue(self, max_workers=3, show_browser=False):
        print(f"🎯 Running TRF 4ª Região Jurisprudência with Concurrent Queue Architecture ({max_workers} workers)")
        query_file = self.project_root / 'data' / 'simple_query_spider' / 'query_links.json'
        
        if not query_file.exists():
            print(f"❌ Query file not found: {query_file}")
            return False
        
        try:
            queue_manager = TRF4QueryQueue(self.project_root)
            
            if not queue_manager.load_queries(query_file):
                print("❌ Failed to load queries")
                return False
            
            completed_workers = 0
            total_processed = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for worker_id in range(max_workers):
                    future = executor.submit(self._concurrent_worker, queue_manager, worker_id, show_browser)
                    futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        worker_results = future.result()
                        if worker_results:
                            completed_workers += 1
                            total_processed += worker_results.get('processed_count', 0)
                            print(f"✅ Worker completed: {worker_results}")
                    except Exception as e:
                        print(f"❌ Worker failed: {e}")
            
            final_status = queue_manager.get_queue_status()
            print(f"\n📊 Final Results:")
            print(f"   Workers completed: {completed_workers}/{max_workers}")
            print(f"   Total processed: {total_processed}")
            print(f"   Successful: {final_status['completed_queries']}")
            print(f"   Failed: {final_status['failed_queries']}")
            
            success_rate = (final_status['completed_queries'] / max(final_status['total_queries'], 1)) * 100
            return success_rate >= 50
            
        except Exception as e:
            print(f"❌ Error in concurrent queue processing: {e}")
            return False
    
    def _concurrent_worker(self, queue_manager, worker_id, show_browser):
        processed_count = 0
        worker_logger = f"Worker-{worker_id}"
        
        print(f"🔄 {worker_logger}: Starting")
        
        while True:
            try:
                result = queue_manager.process_single_query(show_browser)
                if result is None:
                    break
                
                processed_count += 1
                article = result['query']['artigo']
                
                if result['success']:
                    print(f"✅ {worker_logger}: Completed Article {article}")
                else:
                    print(f"❌ {worker_logger}: Failed Article {article}")
                    
            except Exception as e:
                print(f"💥 {worker_logger}: Error processing query: {e}")
                break
        
        print(f"🏁 {worker_logger}: Finished (processed {processed_count} queries)")
        return {'worker_id': worker_id, 'processed_count': processed_count}
    
    def show_queue_status(self):
        queue_manager = TRF4QueryQueue(self.project_root)
        status = queue_manager.get_queue_status()
        
        print("📊 Queue Status:")
        print(f"   Remaining: {status.get('remaining_queries', 0)}")
        print(f"   Completed: {status.get('completed_queries', 0)}")
        print(f"   Failed: {status.get('failed_queries', 0)}")
        print(f"   Progress: {status.get('progress_percentage', 0):.1f}%")
        
        if status.get('next_articles'):
            print(f"   Next articles: {', '.join(status['next_articles'])}")
        
        if status.get('total_queries', 0) == 0:
            print("   ℹ️  No active queue found")
    
    def cleanup_queue_files(self):
        queue_manager = TRF4QueryQueue(self.project_root)
        queue_manager.cleanup_queue_files()
        print("✅ Queue files cleaned up")


def main():
    parser = argparse.ArgumentParser(description='TRF 4ª Região Queue-Based Scraper Manager')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    sequential_parser = subparsers.add_parser('sequential', help='Run with sequential queue processing')
    sequential_parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    
    concurrent_parser = subparsers.add_parser('concurrent', help='Run with concurrent queue processing')
    concurrent_parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers')
    concurrent_parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    
    subparsers.add_parser('status', help='Show current queue status')
    subparsers.add_parser('cleanup', help='Clean up queue state files')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = TRF4QueueManager()
    
    try:
        if args.command == 'sequential':
            success = manager.run_fr_sequential_queue(show_browser=args.show_browser)
            sys.exit(0 if success else 1)
        
        elif args.command == 'concurrent':
            success = manager.run_fr_concurrent_queue(
                max_workers=args.workers,
                show_browser=args.show_browser
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
