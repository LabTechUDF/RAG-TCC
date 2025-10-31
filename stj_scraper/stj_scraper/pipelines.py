# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import re
import json
import os
from datetime import datetime
from pathlib import Path
import logging


class STJJsonLinesPipeline:
    """Pipeline to write items to a single JSONL file"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.file = None
        self.items_count = 0
        
    def open_spider(self, spider):
        """Initialize when spider opens"""
        output_file = getattr(spider, 'output_jsonl', None)
        if not output_file:
            output_file = 'data/stj_decisoes_monocraticas.jsonl'
        
        # Ensure directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        self.file = open(output_file, 'w', encoding='utf-8')
        self.logger.info(f"Opened output file: {output_file}")
        
    def close_spider(self, spider):
        """Close file when spider closes"""
        if self.file:
            self.file.close()
        self.logger.info(f"Total items written to JSONL: {self.items_count}")
            
    def process_item(self, item, spider):
        """Process each item and write to JSONL file"""
        adapter = ItemAdapter(item)
        
        # Write item to file as single JSON line
        line = json.dumps(dict(adapter), ensure_ascii=False) + '\n'
        self.file.write(line)
        self.file.flush()  # Ensure data is written immediately
        
        self.items_count += 1
        
        return item


class ValidationPipeline:
    """Validate scraped STJ decisions and assess content quality"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Validate required fields
        if not adapter.get('raw_seq_documento'):
            raise DropItem(f"Missing seqDocumento in {item}")
        
        if not adapter.get('content'):
            raise DropItem(f"Missing content (TXT file) in {item}")
        
        # Validate content length (should be meaningful)
        content = adapter.get('content', '')
        if len(content.strip()) < 100:
            raise DropItem(f"Content too short ({len(content)} chars): {adapter.get('title', 'No title')}")
        
        # Assess content quality
        quality_score = self.calculate_content_quality(adapter)
        adapter['content_quality'] = quality_score
        
        # Drop items with very low quality
        if quality_score < 40:
            raise DropItem(f"Content quality too low ({quality_score}/100): {adapter.get('title', 'No title')}")
        
        return item
    
    def calculate_content_quality(self, adapter):
        """Calculate content quality based on various factors"""
        score = 0
        
        # Content quality (30 points) - Length and structure
        content = adapter.get('content', '')
        if content:
            content_clean = content.strip()
            if len(content_clean) > 2000:
                score += 30
            elif len(content_clean) > 1000:
                score += 25
            elif len(content_clean) > 500:
                score += 20
            elif len(content_clean) > 200:
                score += 15
            elif len(content_clean) > 100:
                score += 10
        
        # Title quality (20 points) - Legal case patterns
        title = adapter.get('title', '')
        if title:
            legal_patterns = ['REsp', 'HC', 'ARE', 'RE', 'RHC', 'MC', 'AgRg', 'EDcl']
            title_upper = title.upper()
            has_legal_pattern = any(pattern.upper() in title_upper for pattern in legal_patterns)
            
            if has_legal_pattern and len(title) > 10:
                score += 20
            elif has_legal_pattern:
                score += 15
            elif len(title) > 20:
                score += 10
            elif len(title) > 5:
                score += 5
        
        # Trace quality (20 points) - Complete provenance
        trace = adapter.get('trace', {})
        if isinstance(trace, dict):
            required_trace_fields = [
                'zip_filename', 'zip_resource_id', 'zip_download_url', 
                'zip_internal_path', 'dataset_url'
            ]
            trace_completeness = sum(1 for field in required_trace_fields if trace.get(field))
            score += (trace_completeness / len(required_trace_fields)) * 20
        
        # Date quality (15 points) - Valid dates
        pub_date = adapter.get('publication_date')
        dec_date = adapter.get('decision_date')
        
        if pub_date and self.is_valid_date(pub_date):
            score += 8
        if dec_date and self.is_valid_date(dec_date):
            score += 7
        
        # Metadata quality (15 points) - Additional fields
        metadata_fields = ['relator', 'partes', 'decision', 'legislacao']
        metadata_count = sum(1 for field in metadata_fields if adapter.get(field))
        score += (metadata_count / len(metadata_fields)) * 15
        
        return min(score, 100)
    
    def is_valid_date(self, date_str):
        """Check if date string is valid YYYY-MM-DD format"""
        if not date_str:
            return False
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False


class DateNormalizationPipeline:
    """Convert epoch timestamps to ISO date format"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Convert raw publication date
        raw_pub_date = adapter.get('raw_data_publicacao')
        if raw_pub_date:
            iso_date = self.convert_epoch_to_iso(raw_pub_date)
            if iso_date:
                adapter['publication_date'] = iso_date
        
        # Convert raw decision date
        raw_dec_date = adapter.get('raw_data_decisao')
        if raw_dec_date:
            iso_date = self.convert_epoch_to_iso(raw_dec_date)
            if iso_date:
                adapter['decision_date'] = iso_date
        
        return item
    
    def convert_epoch_to_iso(self, timestamp):
        """Convert epoch timestamp to YYYY-MM-DD format"""
        if not timestamp:
            return None
        
        try:
            # Handle string or numeric input
            if isinstance(timestamp, str):
                timestamp = int(timestamp)
            
            # Convert milliseconds to seconds if necessary
            if timestamp > 9999999999:  # Likely milliseconds
                timestamp = timestamp / 1000
            
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d')
        except (ValueError, OSError) as e:
            self.logger.warning(f"Failed to convert timestamp {timestamp}: {e}")
            return None


class DuplicatesPipeline:
    """Remove duplicate items based on seqDocumento"""
    
    def __init__(self):
        self.seq_docs_seen = set()
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        seq_doc = adapter.get('raw_seq_documento')
        
        if seq_doc in self.seq_docs_seen:
            self.logger.info(f"Duplicate seqDocumento found: {seq_doc}")
            raise DropItem(f"Duplicate seqDocumento: {seq_doc}")
        else:
            self.seq_docs_seen.add(seq_doc)
            return item


class StatisticsPipeline:
    """Collect statistics about scraped items"""
    
    def __init__(self):
        self.stats = {}
        self.logger = logging.getLogger(__name__)
    
    def open_spider(self, spider):
        """Initialize statistics"""
        self.stats = {
            'total_items': 0,
            'items_by_article': {},
            'items_by_quality': {'high': 0, 'medium': 0, 'low': 0},
            'items_with_dates': {'publication': 0, 'decision': 0},
            'items_with_metadata': {
                'relator': 0, 'partes': 0, 'decision': 0, 'legislacao': 0
            },
            'content_length_stats': {'min': float('inf'), 'max': 0, 'total': 0},
            'start_time': datetime.now()
        }
    
    def close_spider(self, spider):
        """Log final statistics"""
        self.stats['end_time'] = datetime.now()
        self.stats['duration'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        if self.stats['total_items'] > 0:
            avg_content_length = self.stats['content_length_stats']['total'] / self.stats['total_items']
        else:
            avg_content_length = 0
        
        self.logger.info("=== STJ SCRAPING STATISTICS ===")
        self.logger.info(f"Total items scraped: {self.stats['total_items']}")
        self.logger.info(f"Duration: {self.stats['duration']:.2f} seconds")
        self.logger.info(f"Items by article: {self.stats['items_by_article']}")
        self.logger.info(f"Items by quality: {self.stats['items_by_quality']}")
        self.logger.info(f"Items with dates: {self.stats['items_with_dates']}")
        self.logger.info(f"Items with metadata: {self.stats['items_with_metadata']}")
        self.logger.info(f"Content length - min: {self.stats['content_length_stats']['min']}, max: {self.stats['content_length_stats']['max']}, avg: {avg_content_length:.0f}")
        
        # Save statistics to file
        stats_file = Path("data/stj_scraping_stats.json")
        stats_file.parent.mkdir(exist_ok=True)
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            stats_dict = dict(self.stats)
            stats_dict['start_time'] = self.stats['start_time'].isoformat()
            stats_dict['end_time'] = self.stats['end_time'].isoformat()
            stats_dict['avg_content_length'] = avg_content_length
            json.dump(stats_dict, f, ensure_ascii=False, indent=2)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Update counters
        self.stats['total_items'] += 1
        
        # Count by article
        cluster_name = adapter.get('cluster_name', 'unknown')
        self.stats['items_by_article'][cluster_name] = self.stats['items_by_article'].get(cluster_name, 0) + 1
        
        # Count by quality score
        quality_score = adapter.get('content_quality', 0)
        if quality_score >= 80:
            self.stats['items_by_quality']['high'] += 1
        elif quality_score >= 60:
            self.stats['items_by_quality']['medium'] += 1
        else:
            self.stats['items_by_quality']['low'] += 1
        
        # Count items with dates
        if adapter.get('publication_date'):
            self.stats['items_with_dates']['publication'] += 1
        if adapter.get('decision_date'):
            self.stats['items_with_dates']['decision'] += 1
        
        # Count items with metadata
        for field in self.stats['items_with_metadata']:
            if adapter.get(field):
                self.stats['items_with_metadata'][field] += 1
        
        # Track content length
        content = adapter.get('content', '')
        content_len = len(content)
        if content_len > 0:
            self.stats['content_length_stats']['min'] = min(
                self.stats['content_length_stats']['min'], content_len
            )
            self.stats['content_length_stats']['max'] = max(
                self.stats['content_length_stats']['max'], content_len
            )
            self.stats['content_length_stats']['total'] += content_len
        
        return item