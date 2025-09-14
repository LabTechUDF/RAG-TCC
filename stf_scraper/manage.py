#!/usr/bin/env python3
"""
Management script for Brazilian Legal Content Scrapers
"""

import subprocess
import argparse
import sys
import json
import threading
import tempfile
import shutil
import time
from pathlib import Path
from datetime import datetime

# Import the new queue manager
from stf_queue_manager import run_stf_queue_based
from concurrent.futures import ThreadPoolExecutor, as_completed


class STFScraperManager:
    """Manager for STF legal content scrapers"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.available_spiders = [
            'stf_jurisprudencia', 
            'simple_query_spider',
        ]
    
    def list_spiders(self):
        """List all available spiders"""
        print("📚 Available STF Legal Scrapers:")
        print("=" * 50)
        
        for spider in self.available_spiders:
            config_file = self.project_root / 'configs' / spider / 'config.json'
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    description = config.get('description', 'No description')
                    print(f"  🕷️  {spider:<20} - {description}")
                except Exception as e:
                    print(f"  🕷️  {spider:<20} - Error loading config: {e}")
            else:
                print(f"  🕷️  {spider:<20} - Config not found")
        print()
    
    def run_spider(self, spider_name, dry_run=False, max_pages=None, output_format='json', show_browser=False):
        """Run a specific spider"""
        if spider_name not in self.available_spiders:
            print(f"❌ Error: Spider '{spider_name}' not found.")
            print(f"Available spiders: {', '.join(self.available_spiders)}")
            return False
        
        print(f"🚀 Running {spider_name} spider...")
        if dry_run:
            print("🔍 DRY RUN MODE - No data will be saved")
        if show_browser:
            print("👀 BROWSER VISIBLE - You can watch the scraping process")
        
        # Build scrapy command
        cmd = ['poetry', 'run', 'scrapy', 'crawl', spider_name]
        
        # Add custom settings
        if dry_run:
            cmd.extend(['-s', 'ITEM_PIPELINES={}'])
        
        if max_pages:
            cmd.extend(['-s', f'CLOSESPIDER_PAGECOUNT={max_pages}'])
        
        # Control browser visibility
        if show_browser:
            cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless":false}'])
        
        # Set output format
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/{spider_name}/scraped_{timestamp}.{output_format}"
        
        if not dry_run:
            cmd.extend(['-o', output_file])
        
        # Add verbose logging
        cmd.extend(['-L', 'INFO'])
        
                # Create logs directory for parallel processing
        if spider_name == 'stf_jurisprudencia_parallel':
            logs_dir = Path(self.project_root) / 'logs' / 'parallel_contexts'
            logs_dir.mkdir(parents=True, exist_ok=True)
            print(f"� Created logs directory: {logs_dir}")
        
        try:
            # Change to project directory
            result = subprocess.run(cmd, cwd=self.project_root, check=True)
            
            if result.returncode == 0:
                print(f"✅ Successfully completed {spider_name} spider!")
                if not dry_run:
                    print(f"📄 Data saved to: {output_file}")
                return True
            else:
                print(f"❌ Spider {spider_name} failed with return code {result.returncode}")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Error running spider {spider_name}: {e}")
            return False
        except KeyboardInterrupt:
            print(f"\n⏹️  Spider {spider_name} interrupted by user")
            return False
    
    def run_all_spiders(self, dry_run=False, max_pages=None, show_browser=False):
        """Run all available spiders"""
        print("🚀 Running ALL Brazilian Legal Scrapers...")
        print("=" * 50)
        
        results = {}
        start_time = datetime.now()
        
        for spider in self.available_spiders:
            print(f"\n📋 Starting {spider}...")
            success = self.run_spider(spider, dry_run=dry_run, max_pages=max_pages, show_browser=show_browser)
            results[spider] = success
        
        # Print summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "=" * 50)
        print("📊 SCRAPING SUMMARY")
        print("=" * 50)
        
        successful = sum(results.values())
        total = len(results)
        
        print(f"⏱️  Total time: {duration}")
        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}/{total}")
        
        print("\nDetailed results:")
        for spider, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {spider}")
        
        return successful == total
    
    def run_stf_multithreaded(self, num_threads=5, dry_run=False, max_pages=None, show_browser=False):
        """Run STF jurisprudencia spider with multi-threading by splitting queries"""
        print(f"🚀 Running STF Jurisprudencia with {num_threads} threads...")
        print("=" * 60)
        
        # Load queries from the main query file
        query_file = self.project_root / 'data' / 'simple_query_spider' / 'query_links.json'
        if not query_file.exists():
            print(f"❌ Query file not found: {query_file}")
            return False
        
        try:
            with open(query_file, 'r', encoding='utf-8') as f:
                all_queries = json.load(f)
        except Exception as e:
            print(f"❌ Error loading queries: {e}")
            return False
        
        print(f"📋 Loaded {len(all_queries)} queries to process")
        
        # Split queries into chunks for each thread
        chunk_size = max(1, len(all_queries) // num_threads)
        query_chunks = []
        
        for i in range(0, len(all_queries), chunk_size):
            chunk = all_queries[i:i + chunk_size]
            if chunk:  # Only add non-empty chunks
                query_chunks.append(chunk)
        
        # Adjust if we have more chunks than threads due to rounding
        if len(query_chunks) > num_threads:
            # Merge the last chunks
            while len(query_chunks) > num_threads:
                last_chunk = query_chunks.pop()
                query_chunks[-1].extend(last_chunk)
        
        print(f"📦 Split into {len(query_chunks)} chunks:")
        for i, chunk in enumerate(query_chunks):
            articles = [q['artigo'] for q in chunk]
            print(f"  Thread {i+1}: Articles {', '.join(articles)} ({len(chunk)} queries)")
        
        # Create temporary directories and files for each thread
        temp_dir = self.project_root / 'temp_multithreaded'
        temp_dir.mkdir(exist_ok=True)
        
        temp_files = []
        temp_dirs = []
        
        try:
            for i, chunk in enumerate(query_chunks):
                # Create temp query file
                temp_query_file = temp_dir / f'queries_thread_{i+1}.json'
                with open(temp_query_file, 'w', encoding='utf-8') as f:
                    json.dump(chunk, f, ensure_ascii=False, indent=2)
                temp_files.append(temp_query_file)
                
                # Create temp output directory
                temp_output_dir = temp_dir / f'output_thread_{i+1}'
                temp_output_dir.mkdir(exist_ok=True)
                temp_dirs.append(temp_output_dir)
            
            # Function to run a single spider instance
            def run_spider_thread(thread_id, query_file, output_dir):
                """Run spider for a specific thread"""
                print(f"🕷️  Thread {thread_id}: Starting spider...")
                
                try:
                    # Build scrapy command
                    cmd = [
                        'scrapy', 'crawl', 'stf_jurisprudencia',
                        '-a', f'query_file={query_file}',
                    ]
                    
                    if dry_run:
                        cmd.extend(['-s', 'DRY_RUN=true'])
                    
                    if max_pages:
                        cmd.extend(['-s', f'MAX_PAGES={max_pages}'])
                    
                    if show_browser:
                        cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless": false}'])
                    
                    # Run the command
                    result = subprocess.run(
                        cmd,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        timeout=3600  # 1 hour timeout
                    )
                    
                    if result.returncode == 0:
                        print(f"✅ Thread {thread_id}: Completed successfully")
                        return True
                    else:
                        print(f"❌ Thread {thread_id}: Failed with error:")
                        print(f"   {result.stderr}")
                        return False
                        
                except subprocess.TimeoutExpired:
                    print(f"⏰ Thread {thread_id}: Timed out after 1 hour")
                    return False
                except Exception as e:
                    print(f"❌ Thread {thread_id}: Exception occurred: {e}")
                    return False
            
            # Run all threads in parallel
            print(f"\n🏃 Starting {len(query_chunks)} threads in parallel...")
            start_time = datetime.now()
            
            results = {}
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Submit all tasks
                future_to_thread = {
                    executor.submit(run_spider_thread, i+1, temp_files[i], temp_dirs[i]): i+1
                    for i in range(len(query_chunks))
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_thread):
                    thread_id = future_to_thread[future]
                    try:
                        success = future.result()
                        results[thread_id] = success
                    except Exception as e:
                        print(f"❌ Thread {thread_id}: Exception in thread execution: {e}")
                        results[thread_id] = False
            
            # Calculate summary
            end_time = datetime.now()
            duration = end_time - start_time
            successful = sum(results.values())
            total = len(results)
            
            print(f"\n" + "=" * 60)
            print("📊 MULTI-THREADED SCRAPING SUMMARY")
            print("=" * 60)
            print(f"⏱️  Total time: {duration}")
            print(f"✅ Successful threads: {successful}/{total}")
            print(f"❌ Failed threads: {total - successful}/{total}")
            
            print(f"\nThread results:")
            for thread_id, success in sorted(results.items()):
                status = "✅" if success else "❌"
                chunk_info = f"Articles {', '.join([q['artigo'] for q in query_chunks[thread_id-1]])}"
                print(f"  {status} Thread {thread_id}: {chunk_info}")
            
            # Merge results if successful
            if successful > 0:
                print(f"\n📋 Merging results from {successful} successful threads...")
                self._merge_thread_results(temp_dirs, results)
            
            return successful == total
            
        finally:
            # Cleanup temporary files and directories
            print(f"\n🧹 Cleaning up temporary files...")
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                print("✅ Cleanup completed")
            except Exception as e:
                print(f"⚠️  Warning: Could not clean up temp directory: {e}")
    
    def run_stf_queue_based(self, dry_run=False, show_browser=False):
        """Run STF jurisprudencia spider with queue-based sequential processing"""
        print("🎯 Running STF Jurisprudencia with Queue-Based Architecture")
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
            from stf_queue_manager import STFQueryQueue
            
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
        """Count and report results from successful threads in main data directory"""
        main_data_dir = self.project_root / 'data' / 'stf_jurisprudencia'
        main_data_dir.mkdir(parents=True, exist_ok=True)
        
        total_items = 0
        successful_threads = sum(1 for success in results.values() if success)
        
        print(f"📋 Counting results from {successful_threads} successful threads...")
        
        # Since spiders write directly to final location, count items from the actual output files
        for json_file in main_data_dir.rglob('*.jsonl'):
            if json_file.is_file() and json_file.stat().st_size > 0:
                try:
                    # Count items in this file
                    with open(json_file, 'r', encoding='utf-8') as f:
                        item_count = sum(1 for _ in f)
                    total_items += item_count
                    
                    # Extract article number from filename for reporting
                    article_match = json_file.name.split('_')[0].replace('art', '')
                    print(f"  📁 Article {article_match}: {item_count} items")
                    
                except Exception as e:
                    print(f"  ⚠️  Error counting items in {json_file.name}: {e}")
        
        print(f"✅ Merged {total_items} total items into {main_data_dir}")
    
    def _merge_json_files(self, source_file, target_file):
        """Merge JSON files, handling both array and JSONL formats"""
        try:
            if source_file.suffix == '.jsonl' and target_file.suffix == '.jsonl':
                # JSONL format - append lines
                with open(source_file, 'r', encoding='utf-8') as src:
                    with open(target_file, 'a', encoding='utf-8') as tgt:
                        for line in src:
                            if line.strip():
                                tgt.write(line)
            else:
                # JSON array format - merge arrays
                with open(source_file, 'r', encoding='utf-8') as src:
                    source_data = json.load(src)
                
                with open(target_file, 'r', encoding='utf-8') as tgt:
                    target_data = json.load(tgt)
                
                if isinstance(source_data, list) and isinstance(target_data, list):
                    merged_data = target_data + source_data
                else:
                    merged_data = [target_data, source_data]
                
                with open(target_file, 'w', encoding='utf-8') as tgt:
                    json.dump(merged_data, tgt, ensure_ascii=False, indent=2)
                    
        except Exception as e:
            # If merging fails, just copy the file with a different name
            timestamp = datetime.now().strftime('%H%M%S')
            backup_name = f"{target_file.stem}_backup_{timestamp}{target_file.suffix}"
            backup_path = target_file.parent / backup_name
            shutil.copy2(source_file, backup_path)
    
    def show_stats(self):
        """Show statistics from recent scraping runs"""
        stats_file = self.project_root / 'data' / 'scraping_stats.json'
        
        if not stats_file.exists():
            print("📊 No statistics available. Run some scrapers first!")
            return
        
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
            
            print("📊 LATEST SCRAPING STATISTICS")
            print("=" * 50)
            print(f"Total items scraped: {stats.get('total_items', 0)}")
            print(f"Duration: {stats.get('duration', 0):.2f} seconds")
            print(f"Start time: {stats.get('start_time', 'Unknown')}")
            
            print("\nItems by theme:")
            for theme, count in stats.get('items_by_theme', {}).items():
                print(f"  📝 {theme}: {count}")
            
            print("\nQuality distribution:")
            quality_stats = stats.get('items_by_quality', {})
            print(f"  🌟 High quality: {quality_stats.get('high', 0)}")
            print(f"  ⭐ Medium quality: {quality_stats.get('medium', 0)}")
            print(f"  📋 Low quality: {quality_stats.get('low', 0)}")
            
        except Exception as e:
            print(f"❌ Error reading statistics: {e}")
    
    def clean_data(self):
        """Clean up old data files"""
        data_dir = self.project_root / 'data'
        if not data_dir.exists():
            print("🗂️  No data directory found.")
            return
        
        print("🧹 Cleaning up old data files...")
        
        # Count files before cleanup
        total_files = sum(1 for _ in data_dir.rglob('*.json*'))
        
        # Ask for confirmation
        response = input(f"Are you sure you want to delete {total_files} data files? (y/N): ")
        if response.lower() != 'y':
            print("❌ Cleanup cancelled.")
            return
        
        # Remove data files
        deleted_count = 0
        for file_path in data_dir.rglob('*.json*'):
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        
        print(f"✅ Deleted {deleted_count} files.")
    
    def check_config(self, spider_name=None):
        """Check configuration for spiders"""
        if spider_name:
            spiders_to_check = [spider_name] if spider_name in self.available_spiders else []
            if not spiders_to_check:
                print(f"❌ Spider '{spider_name}' not found.")
                return
        else:
            spiders_to_check = self.available_spiders
        
        print("🔧 CONFIGURATION CHECK")
        print("=" * 50)
        
        for spider in spiders_to_check:
            config_file = self.project_root / 'configs' / spider / 'config.json'
            print(f"\n📋 {spider}:")
            
            if not config_file.exists():
                print(f"  ❌ Config file not found: {config_file}")
                continue
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Check required fields
                required_fields = ['name', 'start_url', 'selectors']
                for field in required_fields:
                    if field in config:
                        print(f"  ✅ {field}: {config[field] if field != 'selectors' else 'configured'}")
                    else:
                        print(f"  ❌ Missing {field}")
                
                # Check URLs
                if 'start_url' in config:
                    print(f"  🌐 Start URL: {config['start_url']}")
                
                if 'fallback_urls' in config:
                    print(f"  🔗 Fallback URLs: {len(config['fallback_urls'])} configured")
                
            except Exception as e:
                print(f"  ❌ Error reading config: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='🇧🇷 Brazilian Legal Content Scraper Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                              # List all available spiders
  %(prog)s run jurisprudencia               # Run jurisprudencia spider
  %(prog)s run-all --dry-run                # Test all spiders without saving
  %(prog)s run-stf-multithreaded --threads 5  # Run STF with 5 threads
  %(prog)s run-stf-queue --dry-run         # Run STF with queue-based sequential processing
  %(prog)s run direito_penal --max-pages 5  # Limit to 5 pages
  %(prog)s stats                            # Show scraping statistics
  %(prog)s check-config                     # Check all configurations
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all available spiders')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a specific spider')
    run_parser.add_argument('spider', choices=['jurisprudencia', 'stf_jurisprudencia', 'sumulas_stf', 'normativas_stj', 'direito_penal', 'tribunais_estaduais', 'simple_query_spider'])
    run_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    run_parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape')
    run_parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')
    run_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Run all command
    run_all_parser = subparsers.add_parser('run-all', help='Run all spiders')
    run_all_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    run_all_parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape per spider')
    run_all_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Multi-threaded STF command
    multithread_parser = subparsers.add_parser('run-stf-multithreaded', help='Run STF jurisprudencia with multiple threads')
    multithread_parser.add_argument('--threads', type=int, default=5, help='Number of threads to use (default: 5)')
    multithread_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    multithread_parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape per thread')
    multithread_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Queue-based STF command (new single responsibility architecture)
    queue_parser = subparsers.add_parser('run-stf-queue', help='Run STF jurisprudencia with queue-based sequential processing')
    queue_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    queue_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Concurrent queue-based STF command
    concurrent_parser = subparsers.add_parser('run-stf-concurrent', help='Run STF jurisprudencia with concurrent queue processing')
    concurrent_parser.add_argument('--workers', type=int, default=3, help='Number of concurrent workers (default: 3)')
    concurrent_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    concurrent_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Queue status command
    subparsers.add_parser('queue-status', help='Show current queue status')
    
    # Queue cleanup command
    subparsers.add_parser('queue-cleanup', help='Clean up queue state files')
    
    # Stats command
    subparsers.add_parser('stats', help='Show scraping statistics')
    
    # Clean command
    subparsers.add_parser('clean', help='Clean up old data files')
    
    # Check config command
    check_parser = subparsers.add_parser('check-config', help='Check spider configurations')
    check_parser.add_argument('spider', nargs='?', help='Specific spider to check')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = STFScraperManager()
    
    try:
        if args.command == 'list':
            manager.list_spiders()
        
        elif args.command == 'run':
            manager.run_spider(
                args.spider, 
                dry_run=args.dry_run,
                max_pages=args.max_pages,
                output_format=args.format,
                show_browser=args.show_browser
            )
        
        elif args.command == 'run-all':
            manager.run_all_spiders(
                dry_run=args.dry_run,
                max_pages=args.max_pages,
                show_browser=args.show_browser
            )
        
        elif args.command == 'run-stf-multithreaded':
            manager.run_stf_multithreaded(
                num_threads=args.threads,
                dry_run=args.dry_run,
                max_pages=args.max_pages,
                show_browser=args.show_browser
            )
        
        elif args.command == 'run-stf-queue':
            success = manager.run_stf_queue_based(
                dry_run=args.dry_run,
                show_browser=args.show_browser
            )
            sys.exit(0 if success else 1)
        
        elif args.command == 'run-stf-concurrent':
            success = manager.run_stf_concurrent_queue(
                max_workers=args.workers,
                dry_run=args.dry_run,
                show_browser=args.show_browser
            )
            sys.exit(0 if success else 1)
        
        elif args.command == 'queue-status':
            from stf_queue_manager import STFQueryQueue
            queue_manager = STFQueryQueue(manager.project_root)
            status = queue_manager.get_queue_status()
            print("📊 Queue Status:")
            print(f"   Remaining: {status.get('remaining_queries', 0)}")
            print(f"   Completed: {status.get('completed_queries', 0)}")
            print(f"   Failed: {status.get('failed_queries', 0)}")
            print(f"   Progress: {status.get('progress_percentage', 0):.1f}%")
            if status.get('next_articles'):
                print(f"   Next articles: {', '.join(status['next_articles'])}")
        
        elif args.command == 'queue-cleanup':
            from stf_queue_manager import STFQueryQueue
            queue_manager = STFQueryQueue(manager.project_root)
            queue_manager.cleanup_queue_files()
            print("✅ Queue files cleaned up")
        
        elif args.command == 'stats':
            manager.show_stats()
        
        elif args.command == 'clean':
            manager.clean_data()
        
        elif args.command == 'check-config':
            manager.check_config(args.spider)
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 