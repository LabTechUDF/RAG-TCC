"""
TRF 4ª Região Query Queue Manager - Handles thread-safe processing of queries
"""
import json
import subprocess
import time
import fcntl
import os
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging


class TRF4QueryQueue:
    """
    Thread-safe queue-based manager for TRF 4ª Região queries:
    - Queue Manager: Handles thread-safe query stack and spawns spider processes
    - Spider: Only processes single queries
    - Uses file-based locking to prevent race conditions
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.queue_file = project_root / "trf4_scraper" / "queue_state.json"
        self.lock_file = project_root / "trf4_scraper" / "queue.lock"
        self.current_query: Optional[Dict] = None
        self.thread_local = threading.local()  # Thread-local storage for locks
        
        # Setup logging
        self.logger = logging.getLogger('TRF4QueryQueue')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _acquire_lock(self, timeout: int = 30) -> bool:
        """Acquire exclusive file lock with timeout (thread-safe)"""
        try:
            # Use thread-local storage for file descriptor
            self.thread_local.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
            
            # Try to acquire lock with timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    fcntl.flock(self.thread_local.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
                except IOError:
                    time.sleep(0.1)  # Wait 100ms before retry
            
            # Timeout reached
            os.close(self.thread_local.lock_fd)
            delattr(self.thread_local, 'lock_fd')
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to acquire lock: {e}")
            return False
    
    def _release_lock(self):
        """Release file lock (thread-safe)"""
        try:
            if hasattr(self.thread_local, 'lock_fd'):
                fcntl.flock(self.thread_local.lock_fd, fcntl.LOCK_UN)
                os.close(self.thread_local.lock_fd)
                delattr(self.thread_local, 'lock_fd')
        except Exception as e:
            self.logger.error(f"Failed to release lock: {e}")
    
    def _load_queue_state(self) -> Dict:
        """Load queue state from file"""
        if not self.queue_file.exists():
            return {
                'queue': [],
                'completed_queries': [],
                'failed_queries': [],
                'total_queries': 0
            }
        
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load queue state: {e}")
            return {
                'queue': [],
                'completed_queries': [],
                'failed_queries': [],
                'total_queries': 0
            }
    
    def _save_queue_state(self, state: Dict):
        """Save queue state to file"""
        try:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save queue state: {e}")
    
    def get_next_query(self) -> Optional[Dict]:
        """Thread-safe method to get the next query from queue"""
        if not self._acquire_lock():
            self.logger.error("Failed to acquire lock for getting next query")
            return None
        
        try:
            state = self._load_queue_state()
            
            if not state['queue']:
                self.logger.info("No more queries in queue")
                return None
            
            # Pop the next query (FIFO)
            next_query = state['queue'].pop(0)
            
            # Save updated state
            self._save_queue_state(state)
            
            self.logger.info(f"🎯 Retrieved Article {next_query['artigo']} from queue")
            self.logger.info(f"📊 Remaining queries: {len(state['queue'])}")
            
            return next_query
            
        finally:
            self._release_lock()
    
    def mark_query_completed(self, query: Dict, success: bool, error: Optional[str] = None):
        """Thread-safe method to mark query as completed or failed"""
        if not self._acquire_lock():
            self.logger.error("Failed to acquire lock for marking query completed")
            return
        
        try:
            state = self._load_queue_state()
            
            if success:
                state['completed_queries'].append({
                    'query': query,
                    'completed_at': datetime.now().isoformat(),
                    'status': 'completed'
                })
                self.logger.info(f"✅ Article {query['artigo']}: Marked as completed")
            else:
                state['failed_queries'].append({
                    'query': query,
                    'failed_at': datetime.now().isoformat(),
                    'error': error or 'Unknown error',
                    'status': 'failed'
                })
                self.logger.error(f"❌ Article {query['artigo']}: Marked as failed")
            
            # Save updated state
            self._save_queue_state(state)
            
        finally:
            self._release_lock()
    
    def load_queries(self, query_file_path: Path) -> bool:
        """Load queries from JSON file into the queue (thread-safe initialization)"""
        if not self._acquire_lock():
            self.logger.error("Failed to acquire lock for loading queries")
            return False
        
        try:
            if not query_file_path.exists():
                self.logger.error(f"Query file not found: {query_file_path}")
                return False
            
            with open(query_file_path, 'r', encoding='utf-8') as f:
                queries = json.load(f)
            
            # Initialize queue state
            state = {
                'queue': queries.copy(),
                'completed_queries': [],
                'failed_queries': [],
                'total_queries': len(queries),
                'initialized_at': datetime.now().isoformat()
            }
            
            self._save_queue_state(state)
            
            self.logger.info(f"📋 Loaded {len(queries)} queries into thread-safe queue")
            
            # Log queue contents
            for i, query in enumerate(queries):
                article = query.get('artigo', f'query_{i}')
                self.logger.info(f"   {i+1}. Article {article}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load queries: {e}")
            return False
        
        finally:
            self._release_lock()

    def check_for_groups(self, article_id: str) -> List[Path]:
        """Check if group files exist for a specific article"""
        groups_dir = self.project_root / "temp_queue" / "groups"
        if not groups_dir.exists():
            return []
        
        # Look for group files for this article
        group_files = list(groups_dir.glob(f"group_*_article_{article_id}.json"))
        return sorted(group_files)
    
    def load_group_for_worker(self, worker_id: int, article_id: str) -> Optional[Dict]:
        """Load specific group for a worker"""
        groups_dir = self.project_root / "temp_queue" / "groups"
        
        # Group files are numbered starting from 1, but worker_id starts from 0
        group_number = worker_id + 1
        group_file = groups_dir / f"group_{group_number}_article_{article_id}.json"
        
        if not group_file.exists():
            self.logger.warning(f"Group file not found for Worker-{worker_id}: {group_file}")
            return None
        
        try:
            with open(group_file, 'r', encoding='utf-8') as f:
                group_data = json.load(f)
            
            self.logger.info(f"📁 Worker-{worker_id} loaded Group {group_number}: {len(group_data.get('pages', []))} pages")
            return group_data
            
        except Exception as e:
            self.logger.error(f"Failed to load group file {group_file}: {e}")
            return None
    
    def create_single_query_file(self, query: Dict, temp_file_path: Path) -> bool:
        """Create a temporary file with a single query for the spider"""
        try:
            temp_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump([query], f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"Created single query file: {temp_file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating single query file: {e}")
            return False
    
    def run_single_spider(self, query: Dict, show_browser: bool = False) -> bool:
        """Run spider with a single query"""
        article = query['artigo']
        
        # Create temporary query file
        temp_dir = self.project_root / 'temp_queue'
        temp_file = temp_dir / f'query_{article}_{int(time.time())}.json'
        
        try:
            self.logger.info(f"🚀 Starting spider for Article {article}")
            
            if not self.create_single_query_file(query, temp_file):
                return False
            
            # Build scrapy command
            cmd = [
                'scrapy', 'crawl', 'trf4_jurisprudencia',
                '-a', f'query_file={temp_file}',
                '-L', 'INFO'
            ]
            
            if show_browser:
                cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless": false}'])
            
            # Run the command
            self.logger.info(f"📋 Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout per query
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ Article {article}: Spider completed successfully")
                self.mark_query_completed(query, success=True)
                return True
            else:
                self.logger.error(f"❌ Article {article}: Spider failed")
                self.logger.error(f"   STDOUT: {result.stdout}")
                self.logger.error(f"   STDERR: {result.stderr}")
                self.mark_query_completed(query, success=False, error=result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏰ Article {article}: Spider timed out after 30 minutes")
            self.mark_query_completed(query, success=False, error='Timeout after 30 minutes')
            return False
            
        except Exception as e:
            self.logger.error(f"💥 Article {article}: Exception occurred: {e}")
            self.mark_query_completed(query, success=False, error=str(e))
            return False
            
        finally:
            # Clean up temporary file
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    self.logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp file: {e}")

    def run_group_spider(self, group_data: Dict, show_browser: bool = False, worker_id: int = 0) -> bool:
        """Run spider for a specific group of pages"""
        article = group_data.get('article', 'unknown')
        group_id = group_data.get('group_id', 0)
        pages_count = len(group_data.get('pages', []))
        
        # Create temporary group file
        temp_dir = self.project_root / 'temp_queue'
        temp_file = temp_dir / f'group_{group_id}_article_{article}_{int(time.time())}.json'
        
        try:
            self.logger.info(f"🚀 Worker-{worker_id} starting Group {group_id} for Article {article} ({pages_count} pages)")
            
            # Save group data to temp file
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(group_data, f, indent=2, ensure_ascii=False)
            
            # Build scrapy command for group processing
            cmd = [
                'scrapy', 'crawl', 'trf4_jurisprudencia',
                '-a', f'group_file={temp_file}',
                '-a', f'worker_id={worker_id}',
                '-L', 'INFO'
            ]
            
            if show_browser:
                cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless": false}'])
            
            # Run the command
            self.logger.info(f"📋 Worker-{worker_id} executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout per group
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ Worker-{worker_id} Group {group_id}: Completed successfully ({pages_count} pages)")
                return True
            else:
                self.logger.error(f"❌ Worker-{worker_id} Group {group_id}: Failed")
                self.logger.error(f"   STDOUT: {result.stdout}")
                self.logger.error(f"   STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏰ Worker-{worker_id} Group {group_id}: Timed out after 30 minutes")
            return False
            
        except Exception as e:
            self.logger.error(f"💥 Worker-{worker_id} Group {group_id}: Exception occurred: {e}")
            return False
            
        finally:
            # Clean up temporary file
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    self.logger.debug(f"Worker-{worker_id} cleaned up temp file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Worker-{worker_id} failed to clean up temp file: {e}")
    
    def run_single_spider(self, query: Dict, show_browser: bool = False, discovery_mode: bool = False) -> bool:
        """Run spider with a single query"""
        article = query['artigo']
        
        # Create temporary query file
        temp_dir = self.project_root / 'temp_queue'
        temp_file = temp_dir / f'query_{article}_{int(time.time())}.json'
        
        try:
            mode_text = "discovery" if discovery_mode else "processing"
            self.logger.info(f"🚀 Starting spider for Article {article} ({mode_text} mode)")
            
            if not self.create_single_query_file(query, temp_file):
                return False
            
            # Build scrapy command
            cmd = [
                'scrapy', 'crawl', 'trf4_jurisprudencia',
                '-a', f'query_file={temp_file}',
                '-L', 'INFO'
            ]
            
            if discovery_mode:
                cmd.extend(['-a', 'discovery_mode=true'])
            
            if show_browser:
                cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless": false}'])
            
            # Run the command
            self.logger.info(f"📋 Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout per query
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ Article {article}: Spider completed successfully ({mode_text} mode)")
                if not discovery_mode:
                    self.mark_query_completed(query, success=True)
                return True
            else:
                self.logger.error(f"❌ Article {article}: Spider failed ({mode_text} mode)")
                self.logger.error(f"   STDOUT: {result.stdout}")
                self.logger.error(f"   STDERR: {result.stderr}")
                if not discovery_mode:
                    self.mark_query_completed(query, success=False, error=result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏰ Article {article}: Spider timed out after 30 minutes ({mode_text} mode)")
            if not discovery_mode:
                self.mark_query_completed(query, success=False, error='Timeout after 30 minutes')
            return False
            
        except Exception as e:
            self.logger.error(f"💥 Article {article}: Exception occurred: {e} ({mode_text} mode)")
            if not discovery_mode:
                self.mark_query_completed(query, success=False, error=str(e))
            return False
            
        finally:
            # Clean up temporary file
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    self.logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp file: {e}")
    
    def process_queue(self, show_browser: bool = False) -> Dict:
        """Process all queries in the queue sequentially (thread-safe version)"""
        start_time = datetime.now()
        
        self.logger.info("🎯 Starting sequential query processing")
        self.logger.info("=" * 60)
        
        # Get initial total count
        state = self._load_queue_state()
        total_queries = state.get('total_queries', 0)
        
        processed_count = 0
        while True:
            # Get next query thread-safely
            query = self.get_next_query()
            if query is None:
                break  # No more queries
            
            processed_count += 1
            article = query['artigo']
            
            self.logger.info(f"📋 Processing Article {article} ({processed_count}/{total_queries})")
            
            # Run spider for this single query
            success = self.run_single_spider(query, show_browser)
            
            if success:
                self.logger.info(f"✅ Article {article}: Processing completed")
            else:
                self.logger.error(f"❌ Article {article}: Processing failed")
            
            self.logger.info("-" * 40)
        
        # Generate final report
        end_time = datetime.now()
        duration = end_time - start_time
        
        final_state = self._load_queue_state()
        
        report = {
            'total_queries': total_queries,
            'successful': len(final_state['completed_queries']),
            'failed': len(final_state['failed_queries']),
            'duration': str(duration),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'completed_queries': final_state['completed_queries'],
            'failed_queries': final_state['failed_queries']
        }
        
        self.print_final_report(report)
        return report
    
    def process_single_query(self, show_browser: bool = False, worker_id: int = None) -> Optional[Dict]:
        """Process a single query from the queue (for concurrent processing)"""
        query = self.get_next_query()
        if query is None:
            return None
        
        article = query['artigo']
        self.logger.info(f"🎯 Worker processing Article {article}")
        
        # First, run the discovery spider to generate group files
        success = self.run_single_spider(query, show_browser, discovery_mode=True)
        
        if not success:
            self.logger.error(f"❌ Discovery failed for Article {article}")
            return {
                'query': query,
                'success': False,
                'processed_at': datetime.now().isoformat(),
                'error': 'Discovery phase failed'
            }
        
        # Wait a moment for group files to be written
        time.sleep(2)
        
        # Check if group files were generated
        group_files = self.check_for_groups(article)
        
        if not group_files:
            self.logger.warning(f"⚠️ No group files found for Article {article}, proceeding with original method")
            # Fallback to original processing
            success = self.run_single_spider(query, show_browser, discovery_mode=False)
            return {
                'query': query,
                'success': success,
                'processed_at': datetime.now().isoformat()
            }
        
        self.logger.info(f"📁 Found {len(group_files)} group files for Article {article}")
        
        # Process each group with separate workers if we have multiple groups
        if len(group_files) > 1:
            self.logger.info(f"🚀 Starting parallel group processing for Article {article}")
            
            # Execute all 3 workers simultaneously using threading
            import concurrent.futures
            group_results = []
            
            def run_worker_group(group_idx, group_file):
                """Run a single worker group"""
                group_data = self.load_group_for_worker(group_idx, article)
                if group_data:
                    self.logger.info(f"🔥 Worker-{group_idx} starting Group {group_data['group_id']} SIMULTANEOUSLY")
                    group_success = self.run_group_spider(group_data, show_browser, group_idx)
                    return {
                        'worker_id': group_idx,
                        'group_id': group_data['group_id'],
                        'success': group_success,
                        'pages_count': len(group_data.get('pages', []))
                    }
                return None
            
            # Execute all workers simultaneously
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # Submit all workers at the same time
                future_to_worker = {
                    executor.submit(run_worker_group, group_idx, group_file): group_idx 
                    for group_idx, group_file in enumerate(group_files)
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_worker):
                    worker_id = future_to_worker[future]
                    try:
                        result = future.result()
                        if result:
                            group_results.append(result)
                            self.logger.info(f"✅ Worker-{worker_id} completed Group {result['group_id']}")
                    except Exception as e:
                        self.logger.error(f"❌ Worker-{worker_id} failed: {e}")
            
            overall_success = all(result['success'] for result in group_results)
            
            result = {
                'query': query,
                'success': overall_success,
                'processed_at': datetime.now().isoformat(),
                'groups_processed': group_results,
                'processing_mode': 'parallel_groups'
            }
        else:
            # Single group, process normally
            group_data = self.load_group_for_worker(0, article)
            success = self.run_group_spider(group_data, show_browser, 0) if group_data else False
            
            result = {
                'query': query,
                'success': success,
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'single_group'
            }
        
        if result['success']:
            self.logger.info(f"✅ Worker completed Article {article}")
        else:
            self.logger.error(f"❌ Worker failed Article {article}")
        
        return result
    
    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        if not self._acquire_lock():
            self.logger.error("Failed to acquire lock for getting queue status")
            return {}
        
        try:
            state = self._load_queue_state()
            
            return {
                'remaining_queries': len(state['queue']),
                'completed_queries': len(state['completed_queries']),
                'failed_queries': len(state['failed_queries']),
                'total_queries': state.get('total_queries', 0),
                'progress_percentage': (
                    (len(state['completed_queries']) + len(state['failed_queries'])) / 
                    max(state.get('total_queries', 1), 1) * 100
                ),
                'next_articles': [q['artigo'] for q in state['queue'][:5]]  # Next 5 articles
            }
        
        finally:
            self._release_lock()
    
    def cleanup_queue_files(self):
        """Clean up queue state and lock files"""
        try:
            if self.queue_file.exists():
                self.queue_file.unlink()
                self.logger.info("Cleaned up queue state file")
            
            if self.lock_file.exists():
                self.lock_file.unlink()
                self.logger.info("Cleaned up lock file")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup queue files: {e}")
    
    def print_final_report(self, report: Dict):
        """Print a comprehensive final report"""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("📊 FINAL PROCESSING REPORT")
        self.logger.info("=" * 60)
        
        self.logger.info(f"⏱️  Total duration: {report['duration']}")
        self.logger.info(f"📋 Total queries: {report['total_queries']}")
        self.logger.info(f"✅ Successful: {report['successful']}")
        self.logger.info(f"❌ Failed: {report['failed']}")
        self.logger.info(f"📈 Success rate: {(report['successful'] / report['total_queries'] * 100):.1f}%")
        
        if report['completed_queries']:
            self.logger.info("\n✅ Successfully processed articles:")
            for item in report['completed_queries']:
                article = item['query']['artigo']
                self.logger.info(f"   • Article {article}")
        
        if report['failed_queries']:
            self.logger.info("\n❌ Failed articles:")
            for item in report['failed_queries']:
                article = item['query']['artigo']
                error = item['error'][:100] + "..." if len(item['error']) > 100 else item['error']
                self.logger.info(f"   • Article {article}: {error}")
        
        self.logger.info("=" * 60)
    
    def count_extracted_items(self) -> Dict:
        """Count items extracted for each successfully processed article"""
        main_data_dir = self.project_root / 'data' / 'trf4_jurisprudencia'
        
        results = {}
        total_items = 0
        
        if not main_data_dir.exists():
            self.logger.warning("No data directory found")
            return results
        
        for json_file in main_data_dir.rglob('*.jsonl'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    count = len([line for line in lines if line.strip()])
                    
                    # Extract article number from path
                    article_match = json_file.parts
                    for part in article_match:
                        if part.startswith('art_'):
                            article = part.replace('art_', '')
                            results[article] = count
                            total_items += count
                            break
                            
            except Exception as e:
                self.logger.warning(f"Error counting items in {json_file}: {e}")
        
        self.logger.info(f"\n📊 Extracted items summary:")
        for article, count in sorted(results.items()):
            self.logger.info(f"   Article {article}: {count} items")
        self.logger.info(f"   Total: {total_items} items")
        
        return results


def run_fr_queue_based(project_root: Path, query_file: Path, show_browser: bool = False) -> Dict:
    """
    Main function to run TRF 4ª Região scraping with queue-based architecture
    """
    queue_manager = TRF4QueryQueue(project_root)
    
    # Load queries into queue
    if not queue_manager.load_queries(query_file):
        return {'error': 'Failed to load queries'}
    
    # Process all queries sequentially
    report = queue_manager.process_queue(show_browser)
    
    # Count extracted items
    queue_manager.count_extracted_items()
    
    return report


if __name__ == '__main__':
    # Test the queue system
    project_root = Path(__file__).parent
    query_file = project_root / 'test_queries.json'
    
    print("🧪 Testing TRF 4ª Região Queue System")
    report = run_fr_queue_based(project_root, query_file)
    print(f"Test completed: {report['successful']}/{report['total_queries']} successful")