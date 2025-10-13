"""
STJ Dataset Scraper Queue Manager
"""
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import filelock

from stj_scraper.utils.ckan_utils import CKANPortalScraper
from stj_scraper.utils.zip_utils import ZipProcessor
from stj_scraper.utils.text_extraction import LegalTextProcessor
from stj_scraper.utils.clustering import DecisionClusterer
from stj_scraper.utils.io_utils import save_json, load_json, append_jsonl
from stj_scraper.items import STJDecisionItem


class STJDatasetScraper:
    """Main STJ Dataset Scraper with queue-based processing"""
    
    def __init__(self, project_root: Path, dataset_url: str = None, output_jsonl: str = None,
                 article_filter: str = None, cluster_order: str = 'article', 
                 limit: int = None, write_txt: bool = False):
        
        self.project_root = Path(project_root)
        self.dataset_url = dataset_url or "https://dadosabertos.web.stj.jus.br/dataset/integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica"
        self.output_jsonl = output_jsonl or str(self.project_root / 'data' / 'stj_decisoes_monocraticas.jsonl')
        self.limit = limit
        self.write_txt = write_txt
        
        # Initialize components
        self.ckan_scraper = CKANPortalScraper()
        self.zip_processor = ZipProcessor(temp_dir=str(self.project_root / 'temp_queue'))
        self.text_processor = LegalTextProcessor()
        
        # Parse article filter
        article_list = None
        if article_filter:
            article_list = [art.strip() for art in article_filter.split(',')]
        self.clusterer = DecisionClusterer(article_filter=article_list, cluster_order=cluster_order)
        
        # Queue management
        self.queue_file = self.project_root / 'stj_scraper' / 'queue_state.json'
        self.lock_file = self.project_root / 'stj_scraper' / 'queue.lock'
        
        # Ensure directories exist
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        Path(self.output_jsonl).parent.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    def run_scraping(self, resume: bool = False) -> Dict[str, Any]:
        """Execute the complete scraping process"""
        
        self.logger.info("🚀 Starting STJ Dataset Scraping")
        
        try:
            with filelock.FileLock(str(self.lock_file)):
                return self._execute_scraping_locked(resume)
                
        except filelock.Timeout:
            error_msg = "Another scraping process is already running"
            self.logger.error(error_msg)
            return {'error': error_msg}
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            self.logger.error(error_msg)
            return {'error': error_msg}
    
    def _execute_scraping_locked(self, resume: bool) -> Dict[str, Any]:
        """Execute scraping with file lock"""
        
        # Initialize or load queue state
        if resume and self.queue_file.exists():
            queue_state = load_json(self.queue_file) or {}
            self.logger.info("📥 Resuming from existing queue state")
        else:
            # Collect resources from dataset
            self.logger.info("🔍 Discovering resources from dataset...")
            resources = self.ckan_scraper.get_dataset_resources_html(self.dataset_url)
            
            if not resources:
                return {'error': 'No resources found in dataset'}
            
            # Apply limit if specified
            if self.limit:
                resources = resources[:self.limit]
                self.logger.info(f"📊 Limited to {len(resources)} resources")
            
            queue_state = {
                'resources': resources,
                'processed': [],
                'failed': [],
                'current_index': 0,
                'total_resources': len(resources),
                'start_time': time.time(),
                'stats': {
                    'zips_processed': 0,
                    'decisions_found': 0,
                    'monocratic_decisions': 0,
                    'txt_files_found': 0,
                    'jsonl_lines_written': 0
                }
            }
            save_json(queue_state, self.queue_file)
            self.logger.info(f"📋 Initialized queue with {len(resources)} resources")
        
        # Process resources
        try:
            while queue_state['current_index'] < len(queue_state['resources']):
                resource = queue_state['resources'][queue_state['current_index']]
                
                self.logger.info(f"🔄 Processing resource {queue_state['current_index']+1}/{len(queue_state['resources'])}: {resource.get('filename', 'Unknown')}")
                
                result = self._process_single_resource(resource)
                
                if result['success']:
                    queue_state['processed'].append(resource['resource_id'])
                    # Update stats
                    stats_update = result.get('stats', {})
                    for key, value in stats_update.items():
                        queue_state['stats'][key] += value
                    
                    self.logger.info(f"✅ Successfully processed {resource.get('filename', 'Unknown')}")
                else:
                    queue_state['failed'].append({
                        'resource_id': resource['resource_id'],
                        'error': result.get('error', 'Unknown error')
                    })
                    self.logger.error(f"❌ Failed to process {resource.get('filename', 'Unknown')}: {result.get('error', 'Unknown error')}")
                
                queue_state['current_index'] += 1
                
                # Save progress
                save_json(queue_state, self.queue_file)
                
                # Small delay to be respectful
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("⏹️ Scraping interrupted by user")
            save_json(queue_state, self.queue_file)
        except Exception as e:
            self.logger.error(f"💥 Unexpected error during processing: {e}")
            save_json(queue_state, self.queue_file)
            return {'error': str(e)}
        
        # Final report
        queue_state['end_time'] = time.time()
        queue_state['duration'] = queue_state['end_time'] - queue_state['start_time']
        
        final_stats = queue_state['stats'].copy()
        final_stats.update({
            'total_resources': queue_state['total_resources'],
            'processed_resources': len(queue_state['processed']),
            'failed_resources': len(queue_state['failed']),
            'duration_seconds': queue_state['duration']
        })
        
        save_json(queue_state, self.queue_file)
        
        return final_stats
    
    def _process_single_resource(self, resource: Dict) -> Dict[str, Any]:
        """Process a single ZIP resource"""
        
        try:
            # Get download URL
            download_url = self.ckan_scraper.get_resource_download_url(resource['resource_page_url'])
            if not download_url:
                return {'success': False, 'error': 'Could not get download URL'}
            
            # Download ZIP file
            temp_zip = Path(tempfile.gettempdir()) / f"stj_{resource['resource_id']}.zip"
            
            if not self.ckan_scraper.download_resource(download_url, str(temp_zip)):
                return {'success': False, 'error': 'Failed to download ZIP'}
            
            try:
                # Extract JSON manifests
                manifests = self.zip_processor.extract_json_manifests(str(temp_zip))
                if not manifests:
                    return {'success': False, 'error': 'No JSON manifests found in ZIP'}
                
                stats = {
                    'zips_processed': 1,
                    'decisions_found': 0,
                    'monocratic_decisions': 0,
                    'txt_files_found': 0,
                    'jsonl_lines_written': 0
                }
                
                # Process each JSON manifest
                for manifest in manifests:
                    manifest_stats = self._process_json_manifest(
                        manifest['data'], str(temp_zip), resource, download_url
                    )
                    
                    # Aggregate stats
                    for key, value in manifest_stats.items():
                        stats[key] += value
                
                return {'success': True, 'stats': stats}
                
            finally:
                # Cleanup temp ZIP file
                if temp_zip.exists():
                    temp_zip.unlink()
                
        except Exception as e:
            self.logger.error(f"Error processing resource {resource['resource_id']}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_json_manifest(self, json_data: Any, zip_path: str, resource: Dict, download_url: str) -> Dict[str, int]:
        """Process JSON manifest and extract decisions"""
        
        stats = {
            'decisions_found': 0,
            'monocratic_decisions': 0,
            'txt_files_found': 0,
            'jsonl_lines_written': 0
        }
        
        # Handle different JSON structures
        if isinstance(json_data, list):
            records = json_data
        elif isinstance(json_data, dict) and 'records' in json_data:
            records = json_data['records']
        elif isinstance(json_data, dict) and 'data' in json_data:
            records = json_data['data']
        else:
            records = [json_data] if isinstance(json_data, dict) else []
        
        for record in records:
            if not isinstance(record, dict):
                continue
            
            stats['decisions_found'] += 1
            
            # Check if it's a monocratic decision
            if not self.text_processor.is_monocratic_decision(record):
                continue
            
            stats['monocratic_decisions'] += 1
            
            # Extract seqDocumento
            seq_documento = record.get('seqDocumento')
            if not seq_documento:
                continue
            
            # Find corresponding TXT file
            txt_result = self.zip_processor.find_txt_file(zip_path, str(seq_documento))
            if not txt_result:
                self.logger.warning(f"TXT file not found for seqDocumento: {seq_documento}")
                continue
            
            txt_content, zip_internal_path = txt_result
            stats['txt_files_found'] += 1
            
            # Create decision item
            decision_item = self._create_decision_item(
                record, txt_content, zip_internal_path, resource, download_url
            )
            
            # Apply article filter
            if not self.clusterer.should_include_article(decision_item.get('cluster_name')):
                continue
            
            # Write TXT file if requested
            if self.write_txt:
                self._write_txt_file(decision_item, txt_content)
            
            # Append to JSONL
            append_jsonl(decision_item, self.output_jsonl)
            stats['jsonl_lines_written'] += 1
            
            self.logger.debug(f"Processed decision: {decision_item.get('title', 'No title')}")
        
        return stats
    
    def _create_decision_item(self, json_record: Dict, txt_content: str, zip_internal_path: str, 
                             resource: Dict, download_url: str) -> Dict:
        """Create normalized decision item"""
        
        # Extract information from TXT content
        cluster_name, cluster_desc, article_ref = self.text_processor.extract_article_info(txt_content)
        
        # Extract case information
        title = json_record.get('titulo') or json_record.get('title') or f"Decisão {json_record.get('seqDocumento', 'Sem número')}"
        case_number = self.text_processor.extract_case_number(title)
        
        # Clean content
        clean_content = self.text_processor.clean_content(txt_content)
        
        # Extract metadata from content
        relator = self.text_processor.extract_relator(clean_content)
        partes = self.text_processor.extract_partes(clean_content)
        decision = self.text_processor.extract_decision(clean_content)
        legislacao = self.text_processor.extract_legislacao(clean_content)
        
        # Build trace information
        trace = {
            'zip_filename': resource['filename'],
            'zip_resource_id': resource['resource_id'],
            'zip_download_url': download_url,
            'zip_internal_path': zip_internal_path,
            'dataset_url': resource['dataset_url'],
            'resource_page_url': resource['resource_page_url'],
            'local_cache_dir': f"stj_scraper/temp_queue/{resource['resource_id']}/",
            'cluster_path': self.clusterer.get_cluster_path(cluster_name or 'unknown', resource['filename'])
        }
        
        # Create item
        item = {
            'cluster_name': cluster_name or 'unknown',
            'cluster_description': cluster_desc or 'Decisão sem artigo identificado',
            'article_reference': article_ref or 'N/A',
            'source': f"STJ - {resource['filename']}",
            'title': title,
            'case_number': case_number,
            'content': clean_content,
            'url': None,  # STJ decisions don't have direct URLs
            'tribunal': 'STJ',
            'legal_area': None,
            'relator': relator,
            'publication_date': None,  # Will be set by DateNormalizationPipeline
            'decision_date': None,     # Will be set by DateNormalizationPipeline
            'partes': partes,
            'decision': decision,
            'legislacao': legislacao,
            'content_quality': 0,  # Will be calculated by ValidationPipeline
            'trace': trace,
            
            # Raw fields for pipeline processing
            'raw_seq_documento': json_record.get('seqDocumento'),
            'raw_tipo_documento': json_record.get('tipoDocumento'),
            'raw_tipo_decisao': json_record.get('tipoDecisao'),
            'raw_data_publicacao': json_record.get('dataPublicacao'),
            'raw_data_decisao': json_record.get('dataDecisao'),
        }
        
        return item
    
    def _write_txt_file(self, decision_item: Dict, txt_content: str):
        """Write TXT file to disk (optional feature)"""
        if not self.write_txt:
            return
        
        trace = decision_item.get('trace', {})
        cluster_path = trace.get('cluster_path', 'data/unknown/')
        
        # Create directory structure
        txt_dir = self.project_root / cluster_path
        txt_dir.mkdir(parents=True, exist_ok=True)
        
        # Write TXT file
        seq_doc = decision_item.get('raw_seq_documento', 'unknown')
        txt_filename = f"{seq_doc}.txt"
        txt_path = txt_dir / txt_filename
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(txt_content)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue processing status"""
        if not self.queue_file.exists():
            return {
                'total_resources': 0,
                'remaining_resources': 0,
                'completed_resources': 0,
                'failed_resources': 0,
                'progress_percentage': 0,
            }
        
        queue_state = load_json(self.queue_file) or {}
        
        total = queue_state.get('total_resources', 0)
        current_index = queue_state.get('current_index', 0)
        completed = len(queue_state.get('processed', []))
        failed = len(queue_state.get('failed', []))
        
        remaining = max(0, total - current_index)
        progress = (current_index / total * 100) if total > 0 else 0
        
        # Get next few resource names
        resources = queue_state.get('resources', [])
        next_resources = []
        for i in range(current_index, min(current_index + 5, len(resources))):
            next_resources.append(resources[i].get('filename', f'Resource {i}'))
        
        return {
            'total_resources': total,
            'remaining_resources': remaining,
            'completed_resources': completed,
            'failed_resources': failed,
            'progress_percentage': progress,
            'next_resources': next_resources,
            'stats': queue_state.get('stats', {})
        }
    
    def cleanup_queue_files(self):
        """Clean up queue state and lock files"""
        if self.queue_file.exists():
            self.queue_file.unlink()
        if self.lock_file.exists():
            self.lock_file.unlink()
        
        # Clean up temp directory
        temp_dir = self.project_root / 'temp_queue'
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
            temp_dir.mkdir(exist_ok=True)