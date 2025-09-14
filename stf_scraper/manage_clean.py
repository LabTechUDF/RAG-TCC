#!/usr/bin/env python3
"""
Management script for STF Queue-Based Scrapers
Clean implementation focused on thread-safe queue processing
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import the queue manager
from stf_queue_manager import run_stf_queue_based, STFQueryQueue


class STFQueueManager:
    """Clean manager for STF queue-based scrapers"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
    
    def run_stf_sequential_queue(self, dry_run=False, show_browser=False):
        """Run STF jurisprudencia spider with queue-based sequential processing"""
        print("🎯 Running STF Jurisprudencia with Queue-Based Sequential Architecture")
        print("=" * 60)
        
        # Load queries from the main query file
        query_file = self.project_root / 'data' / 'simple_query_spider' / 'query_links.json'
        if not query_file.exists():
            print(f"❌ Query file not found: {query_file}")
            return False
        
        try:
            # Use the queue manager to process all queries
            report = run_stf_queue_based(self.project_root, query_file, dry_run, show_browser)
            
            if 'error' in report:
                print(f"❌ Queue processing failed: {report['error']}")
                return False
            
            success_rate = (report['successful'] / report['total_queries']) * 100
            return success_rate >= 50  # Consider successful if at least 50% complete
            
        except Exception as e:
            print(f"❌ Error in queue-based processing: {e}")
            return False
    
    def run_stf_concurrent_queue(self, max_workers=3, dry_run=False, show_browser=False):
        """Run STF jurisprudencia spider with concurrent queue processing"""
        print(f"🎯 Running STF Jurisprudencia with Concurrent Queue Architecture ({max_workers} workers)")
        print("=" * 60)
        
        # Load queries from the main query file
        query_file = self.project_root / 'data' / 'simple_query_spider' / 'query_links.json'
        if not query_file.exists():
            print(f"❌ Query file not found: {query_file}")
            return False
        
        try:
            # Initialize queue manager
            queue_manager = STFQueryQueue(self.project_root)
            
            # Load queries into queue
            if not queue_manager.load_queries(query_file):
                print("❌ Failed to load queries")
                return False
            
            # Process with multiple workers
            completed_workers = 0
            total_processed = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit workers
                futures = []
                for worker_id in range(max_workers):
                    future = executor.submit(self._concurrent_worker, queue_manager, worker_id, dry_run, show_browser)
                    futures.append(future)
                
                # Wait for completion and collect results
                for future in as_completed(futures):
                    try:
                        worker_results = future.result()
                        if worker_results:
                            completed_workers += 1
                            total_processed += worker_results.get('processed_count', 0)
                            print(f"✅ Worker completed: {worker_results}")
                    except Exception as e:
                        print(f"❌ Worker failed: {e}")
            
            # Get final status
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
    
    def _concurrent_worker(self, queue_manager, worker_id, dry_run, show_browser):
        """Worker function for concurrent processing"""
        processed_count = 0
        worker_logger = f"Worker-{worker_id}"
        
        print(f"🔄 {worker_logger}: Starting")
        
        while True:
            try:
                result = queue_manager.process_single_query(dry_run, show_browser)
                if result is None:
                    break  # No more queries
                
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
        """Show current queue status"""
        queue_manager = STFQueryQueue(self.project_root)
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
        """Clean up queue state files"""
        queue_manager = STFQueryQueue(self.project_root)
        queue_manager.cleanup_queue_files()
        print("✅ Queue files cleaned up")


def main():
    """Main entry point for STF Queue Manager"""
    parser = argparse.ArgumentParser(
        description='🇧🇷 STF Queue-Based Scraper Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sequential --dry-run              # Sequential queue processing (safe)
  %(prog)s concurrent --workers 3 --dry-run # Concurrent processing with 3 workers
  %(prog)s status                           # Show current queue status
  %(prog)s cleanup                          # Clean up queue files
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Sequential queue processing
    sequential_parser = subparsers.add_parser('sequential', help='Run with sequential queue processing')
    sequential_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    sequential_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Concurrent queue processing
    concurrent_parser = subparsers.add_parser('concurrent', help='Run with concurrent queue processing')
    concurrent_parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers (default: 3)')
    concurrent_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    concurrent_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Queue status command
    subparsers.add_parser('status', help='Show current queue status')
    
    # Queue cleanup command
    subparsers.add_parser('cleanup', help='Clean up queue state files')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = STFQueueManager()
    
    try:
        if args.command == 'sequential':
            success = manager.run_stf_sequential_queue(
                dry_run=args.dry_run,
                show_browser=args.show_browser
            )
            sys.exit(0 if success else 1)
        
        elif args.command == 'concurrent':
            success = manager.run_stf_concurrent_queue(
                max_workers=args.workers,
                dry_run=args.dry_run,
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