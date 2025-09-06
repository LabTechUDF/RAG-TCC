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
    """Validate scraped legal documents and assess content quality"""
    
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
        
        # Assess content quality based on key fields
        quality_score = self.calculate_content_quality(adapter)
        adapter['content_quality'] = quality_score
        
        # Drop items with very low quality
        if quality_score < 30:
            raise DropItem(f"Content quality too low ({quality_score}/100): {adapter.get('title', 'No title')}")
        
        return item
    
    def calculate_content_quality(self, adapter):
        """Calculate content quality based on URL, relator, title with legal acronyms, and content"""
        score = 0
        
        # URL quality (25 points) - Must be jurisprudencia.stf.jus.br
        url = adapter.get('url', '')
        if 'jurisprudencia.stf.jus.br' in url:
            score += 25
        elif 'stf.jus.br' in url:
            score += 15
        elif url.startswith('https://'):
            score += 10
        elif url.startswith('http://'):
            score += 5
        
        # Relator quality (25 points) - Judge name present and valid
        relator = adapter.get('relator', '')
        if relator:
            if len(relator) > 5 and any(char.isupper() for char in relator):
                score += 25
            elif len(relator) > 2:
                score += 15
            else:
                score += 5
        
        # Title quality (25 points) - Must contain legal decision acronyms
        title = adapter.get('title', '')
        legal_acronyms = ['HC', 'ARE', 'RE', 'RHC', 'MC']
        if title:
            # Check if title contains any legal acronyms
            title_upper = title.upper()
            has_acronym = any(acronym in title_upper for acronym in legal_acronyms)
            
            if has_acronym and len(title) > 15:
                score += 25
            elif has_acronym and len(title) > 5:
                score += 20
            elif len(title) > 30:
                score += 15
            elif len(title) > 15:
                score += 10
            elif len(title) > 5:
                score += 5
        
        # Content quality (25 points) - Real content present, not placeholder
        content = adapter.get('content', '')
        if content:
            content_clean = content.strip()
            # Check for meaningful content length and structure
            if len(content_clean) > 500 and 'Relator' in content and 'Julgamento' in content:
                score += 25
            elif len(content_clean) > 200 and any(word in content for word in ['Decisão', 'Relator', 'Min.']):
                score += 20
            elif len(content_clean) > 100:
                score += 15
            elif len(content_clean) > 50:
                score += 10
            elif len(content_clean) > 10:
                score += 5
        
        return min(score, 100)
    
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


class DateNormalizationPipeline:
    """Convert Brazilian DD/MM/YYYY dates to ISO format YYYY-MM-DD"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Convert publication_date from DD/MM/YYYY to YYYY-MM-DD
        pub_date = adapter.get('publication_date')
        if pub_date and self.is_brazilian_date_format(pub_date):
            adapter['publication_date'] = self.convert_to_iso_date(pub_date)
        
        # Convert decision_date from DD/MM/YYYY to YYYY-MM-DD
        dec_date = adapter.get('decision_date')
        if dec_date and self.is_brazilian_date_format(dec_date):
            adapter['decision_date'] = self.convert_to_iso_date(dec_date)
        
        return item
    
    def is_brazilian_date_format(self, date_str):
        """Check if date is in DD/MM/YYYY format"""
        return bool(re.match(r'^\d{2}/\d{2}/\d{4}$', date_str))
    
    def convert_to_iso_date(self, date_str):
        """Convert DD/MM/YYYY to YYYY-MM-DD"""
        try:
            day, month, year = date_str.split('/')
            return f"{year}-{month}-{day}"
        except Exception as e:
            self.logger.warning(f"Failed to convert date {date_str}: {e}")
            return date_str  # Return original if conversion fails


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
            'items_by_classe': {},
            'items_with_relator': 0,
            'items_with_content': 0,
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
        self.logger.info(f"Items by classe processual: {self.stats['items_by_classe']}")
        self.logger.info(f"Items with relator: {self.stats['items_with_relator']}")
        self.logger.info(f"Items with content: {self.stats['items_with_content']}")
        
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
        
        # Count by quality score
        quality_score = adapter.get('content_quality', 0)
        if quality_score >= 80:
            self.stats['items_by_quality']['high'] += 1
        elif quality_score >= 60:
            self.stats['items_by_quality']['medium'] += 1
        else:
            self.stats['items_by_quality']['low'] += 1
        
        # Count by classe processual
        classe = adapter.get('classe_processual_unificada', 'unknown')
        self.stats['items_by_classe'][classe] = self.stats['items_by_classe'].get(classe, 0) + 1
        
        # Count items with relator
        if adapter.get('relator'):
            self.stats['items_with_relator'] += 1
            
        # Count items with meaningful content
        content = adapter.get('content', '')
        if content and len(content.strip()) > 50:
            self.stats['items_with_content'] += 1
        
        return item
