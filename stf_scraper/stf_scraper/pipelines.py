# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import re
import json
import os
from datetime import datetime
from pathlib import Path
import logging


class ValidationPipeline:
    """Validate scraped legal documents"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Validate required fields
        if not adapter.get('title'):
            raise DropItem(f"Missing title in {item}")
        
        if not adapter.get('url'):
            raise DropItem(f"Missing URL in {item}")
        
        # Validate URL format
        url = adapter.get('url')
        if url and not self.is_valid_url(url):
            raise DropItem(f"Invalid URL format: {url}")
        
        # Validate Brazilian legal case number if present
        case_number = adapter.get('case_number')
        if case_number and not self.validate_case_number(case_number):
            self.logger.warning(f"Invalid case number format: {case_number}")
        
        # Validate content quality
        content = adapter.get('content', '')
        title = adapter.get('title', '')
        
        if len(content) < 50 and len(title) < 10:
            raise DropItem(f"Content too short, might be extraction error")
        
        # Add content quality score
        adapter['content_quality'] = self.calculate_quality_score(adapter)
        
        return item
    
    def is_valid_url(self, url):
        """Validate URL format"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    def validate_case_number(self, case_number):
        """Validate Brazilian legal case number format"""
        if not case_number:
            return False
        # Pattern: 0000000-00.0000.0.00.0000
        pattern = r'^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$'
        return bool(re.match(pattern, case_number))
    
    def calculate_quality_score(self, adapter):
        """Calculate content quality score (0-100)"""
        score = 0
        
        # Title quality (20 points)
        title = adapter.get('title', '')
        if len(title) > 20:
            score += 10
        if len(title) > 50:
            score += 10
        
        # Content quality (40 points)
        content = adapter.get('content', '')
        if len(content) > 100:
            score += 10
        if len(content) > 500:
            score += 10
        if len(content) > 1000:
            score += 10
        if len(content) > 2000:
            score += 10
        
        # Metadata quality (40 points)
        if adapter.get('publication_date'):
            score += 10
        if adapter.get('case_number'):
            score += 10
        if adapter.get('tribunal'):
            score += 10
        if adapter.get('legal_area'):
            score += 10
        
        return min(score, 100)


class DuplicatesPipeline:
    """Remove duplicate items based on URL"""
    
    def __init__(self):
        self.urls_seen = set()
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get('url')
        
        if url in self.urls_seen:
            self.logger.info(f"Duplicate item found: {url}")
            raise DropItem(f"Duplicate item found: {item}")
        else:
            self.urls_seen.add(url)
            return item


class BrazilianDatePipeline:
    """Process and normalize Brazilian date formats"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.month_names = {
            'janeiro': '01', 'jan': '01',
            'fevereiro': '02', 'fev': '02',
            'março': '03', 'mar': '03',
            'abril': '04', 'abr': '04',
            'maio': '05', 'mai': '05',
            'junho': '06', 'jun': '06',
            'julho': '07', 'jul': '07',
            'agosto': '08', 'ago': '08',
            'setembro': '09', 'set': '09',
            'outubro': '10', 'out': '10',
            'novembro': '11', 'nov': '11',
            'dezembro': '12', 'dez': '12',
        }
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Process publication_date
        pub_date = adapter.get('publication_date')
        if pub_date:
            adapter['publication_date'] = self.normalize_date(pub_date)
        
        # Process decision_date
        dec_date = adapter.get('decision_date')
        if dec_date:
            adapter['decision_date'] = self.normalize_date(dec_date)
        
        # Add scraped_at timestamp
        adapter['scraped_at'] = datetime.now().isoformat()
        
        return item
    
    def normalize_date(self, date_str):
        """Normalize Brazilian date formats to ISO format"""
        if not date_str:
            return None
        
        # Clean the date string
        date_str = date_str.strip().lower()
        
        # Try different date patterns
        patterns = [
            # DD/MM/YYYY
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
            # DD-MM-YYYY
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
            # DD de MONTH de YYYY
            (r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', self.parse_textual_date),
            # YYYY-MM-DD (already ISO)
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        ]
        
        for pattern, converter in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return converter(match)
                except Exception as e:
                    self.logger.warning(f"Error parsing date '{date_str}': {e}")
                    continue
        
        self.logger.warning(f"Could not parse date: {date_str}")
        return date_str  # Return original if can't parse
    
    def parse_textual_date(self, match):
        """Parse textual date like '15 de dezembro de 2023'"""
        day = match.group(1).zfill(2)
        month_name = match.group(2).lower()
        year = match.group(3)
        
        month = self.month_names.get(month_name)
        if not month:
            raise ValueError(f"Unknown month: {month_name}")
        
        return f"{year}-{month}-{day}"


class JsonWriterPipeline:
    """Write items to JSON files organized by theme"""
    
    def __init__(self):
        self.files = {}
        self.exporters = {}
        self.logger = logging.getLogger(__name__)
    
    def open_spider(self, spider):
        """Initialize JSON exporters for each theme"""
        pass
    
    def close_spider(self, spider):
        """Close all open files"""
        for exporter in self.exporters.values():
            exporter.finish_exporting()
        for file in self.files.values():
            file.close()
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        theme = adapter.get('theme', 'unknown')
        
        # Create directory if it doesn't exist
        data_dir = Path(f"data/{theme}")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = data_dir / f"{theme}_{timestamp}.jsonl"
        
        # Write item to JSONL file
        with open(filename, 'a', encoding='utf-8') as f:
            item_dict = dict(adapter)
            json.dump(item_dict, f, ensure_ascii=False, default=str)
            f.write('\n')
        
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
            'items_by_theme': {},
            'items_by_quality': {'high': 0, 'medium': 0, 'low': 0},
            'start_time': datetime.now()
        }
    
    def close_spider(self, spider):
        """Log final statistics"""
        self.stats['end_time'] = datetime.now()
        self.stats['duration'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        self.logger.info("=== SCRAPING STATISTICS ===")
        self.logger.info(f"Total items scraped: {self.stats['total_items']}")
        self.logger.info(f"Duration: {self.stats['duration']:.2f} seconds")
        self.logger.info(f"Items by theme: {self.stats['items_by_theme']}")
        self.logger.info(f"Items by quality: {self.stats['items_by_quality']}")
        
        # Save statistics to file
        stats_file = Path("data/scraping_stats.json")
        stats_file.parent.mkdir(exist_ok=True)
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            stats_dict = dict(self.stats)
            stats_dict['start_time'] = self.stats['start_time'].isoformat()
            stats_dict['end_time'] = self.stats['end_time'].isoformat()
            json.dump(stats_dict, f, ensure_ascii=False, indent=2)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Update counters
        self.stats['total_items'] += 1
        
        # Count by theme
        theme = adapter.get('theme', 'unknown')
        self.stats['items_by_theme'][theme] = self.stats['items_by_theme'].get(theme, 0) + 1
        
        # Count by quality
        quality_score = adapter.get('content_quality', 0)
        if quality_score >= 80:
            self.stats['items_by_quality']['high'] += 1
        elif quality_score >= 60:
            self.stats['items_by_quality']['medium'] += 1
        else:
            self.stats['items_by_quality']['low'] += 1
        
        return item
