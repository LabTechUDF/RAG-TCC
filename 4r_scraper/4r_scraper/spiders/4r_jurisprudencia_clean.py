"""
TRF 4ª Região Jurisprudência Spider - Clean version focused on groups system with 3 workers
"""

import re
import json
import scrapy
import os
import threading
import queue
import time
from datetime import datetime
from pathlib import Path
from scrapy.exceptions import CloseSpider
from scrapy_playwright.page import PageMethod
from fr_scraper.items import (
    JurisprudenciaItem, 
    get_classe_processual_from_url,
    extract_relator_from_content,
    extract_publication_date_from_content,
    extract_decision_date_from_content,
    extract_partes_from_content
)


class Trf4JurisprudenciaSpider(scrapy.Spider):
    """Clean spider for TRF 4ª Região jurisprudência content using groups system"""

    name = 'trf4_jurisprudencia_clean'
    # TODO: Update to TRF 4ª Região domain when available
    allowed_domains = ['jurisprudencia.trf4.jus.br']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_workers = 3  # Fixed to 3 workers/browsers
        self.parallel_groups_count = self.num_workers
        self.temp_queue_dir = Path(__file__).parent.parent.parent / 'temp_queue'
        self.temp_queue_dir.mkdir(exist_ok=True)
        self.processed_items = 0
        self.max_items = 50
        self.current_page = 1
        self.total_pages = None
        self.pages_with_zero_results = 0
        self.max_consecutive_zero_pages = 3

    def load_query_array(self):
        """Load query array from JSON file or group file"""
        # Check if group file is provided (for worker-specific processing)
        group_file = getattr(self, 'group_file', None)
        
        if group_file:
            return self.load_group_file(group_file)
        
        # Check if custom query file is provided via settings
        custom_query_file = getattr(self, 'query_file', None)
        
        if custom_query_file:
            query_file = Path(custom_query_file)
        else:
            # Default query file path
            query_file = Path(__file__).parent.parent.parent / 'data' / 'simple_query_spider' / 'query_links.json'
        
        # Load and validate query file
        if not query_file.exists():
            self.logger.error(f"Query file not found: {query_file}")
            return []
        
        try:
            with open(query_file, 'r', encoding='utf-8') as f:
                queries = json.load(f)
                self.logger.info(f"Loaded {len(queries)} queries from {query_file.name}")
                return queries
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading query file: {e}")
            return []

    def load_group_file(self, group_file_path):
        """Load URLs from a specific group file for worker processing"""
        try:
            group_path = Path(group_file_path)
            with open(group_path, 'r', encoding='utf-8') as f:
                group_data = json.load(f)
            
            # Extract URLs from group data
            urls = []
            for url_item in group_data.get('urls', []):
                urls.append({
                    'url': url_item['url'],
                    'page_number': url_item['page_number'],
                    'article': group_data.get('article', 'unknown'),
                    'query': group_data.get('query', '')
                })
            
            self.logger.info(f"Worker loaded group {group_data.get('group_id', 'unknown')}: {len(urls)} pages")
            return urls
            
        except Exception as e:
            self.logger.error(f"Error loading group file {group_file_path}: {e}")
            return []

    def start_requests(self):
        """Generate initial scrapy requests from query array"""
        queries = self.load_query_array()
        
        if not queries:
            self.logger.error("No queries loaded - stopping spider")
            return
        
        # Process each query to generate requests
        for query in queries:
            if isinstance(query, dict) and 'url' in query:
                # Group file format - direct URLs
                yield scrapy.Request(
                    url=query['url'],
                    callback=self.parse_jurisprudencia_page,
                    meta={
                        'page_number': query.get('page_number', 1),
                        'article': query.get('article', 'unknown'),
                        'query': query.get('query', ''),
                        'playwright': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_timeout', 2000),
                        ]
                    }
                )
            else:
                # Regular query format - initial discovery
                # TODO: Update to TRF 4ª Região URL when available
                base_url = "https://jurisprudencia.trf4.jus.br/pages/search"
                initial_url = f"{base_url}?base=acordaos&pesquisa_livre_filtro=ementario&pesquisa_livre={query}&ordenacao=data&tipo_decisao=acordaos"
                
                yield scrapy.Request(
                    url=initial_url,
                    callback=self.parse_initial_page,
                    meta={
                        'query_info': {'artigo': query, 'query': query},
                        'base_url': base_url,
                        'playwright': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_timeout', 3000),
                        ]
                    }
                )

    def parse_initial_page(self, response):
        """Parse initial search page to determine total pages and create groups"""
        try:
            # Extract total pages from pagination
            pagination_info = response.css('div[data-cy="pagination-info"]::text').get()
            
            if pagination_info:
                # Try to extract total count from "Mostrando X de Y resultados"
                match = re.search(r'(\d+)\s+de\s+(\d+)\s+resultados?', pagination_info)
                if match:
                    total_results = int(match.group(2))
                    results_per_page = 10  # TRF 4ª Região typically shows 10 results per page
                    total_pages = (total_results + results_per_page - 1) // results_per_page
                    
                    self.logger.info(f"📊 Found {total_results} results, {total_pages} pages")
                    
                    # Create groups for parallel processing
                    groups = self.save_groups_to_json(
                        total_pages=total_pages,
                        base_url=response.meta['base_url'],
                        query_info=response.meta['query_info']
                    )
                    
                    self.logger.info(f"📁 Created {len(groups)} groups for parallel processing")
                    return
            
            self.logger.warning("Could not determine total pages - processing single page")
            
        except Exception as e:
            self.logger.error(f"Error parsing initial page: {e}")

    def save_groups_to_json(self, total_pages, base_url, query_info):
        """Save groups to JSON files for worker distribution"""
        # Calculate pages per group
        pages_per_group = total_pages // self.num_workers
        extra_pages = total_pages % self.num_workers
        
        groups = []
        start_page = 1
        
        for group_id in range(self.num_workers):
            # Calculate end page for this group
            group_pages = pages_per_group + (1 if group_id < extra_pages else 0)
            end_page = start_page + group_pages - 1
            
            # Generate URLs for this group
            group_urls = []
            for page_num in range(start_page, end_page + 1):
                url = f"{base_url}?base=acordaos&pesquisa_livre_filtro=ementario&pesquisa_livre={query_info.get('query', '')}&ordenacao=data&tipo_decisao=acordaos&page={page_num}"
                group_urls.append({
                    "page_number": page_num,
                    "url": url
                })
            
            # Create group data
            group_data = {
                "group_id": group_id + 1,
                "article": query_info.get('artigo', 'unknown'),
                "query": query_info.get('query', ''),
                "total_pages_in_group": len(group_urls),
                "start_page": start_page,
                "end_page": end_page,
                "urls": group_urls,
                "created_at": datetime.now().isoformat()
            }
            
            groups.append(group_data)
            
            # Save group to individual JSON file
            group_file = self.temp_queue_dir / f"group_{group_id + 1}_article_{query_info.get('artigo', 'unknown')}.json"
            with open(group_file, 'w', encoding='utf-8') as f:
                json.dump(group_data, f, indent=2, ensure_ascii=False)
            
            start_page = end_page + 1
        
        return groups

    def parse_jurisprudencia_page(self, response):
        """Parse jurisprudência page and extract decision items"""
        try:
            # Extract all decision items from page
            decisao_items = response.css('div.resultado-pesquisa')
            items_found = len(decisao_items)
            
            if items_found == 0:
                self.pages_with_zero_results += 1
                self.logger.warning(f"Page {response.meta.get('page_number', '?')} has 0 results")
                
                if self.pages_with_zero_results >= self.max_consecutive_zero_pages:
                    self.logger.error(f"Too many consecutive pages with zero results ({self.pages_with_zero_results})")
                    raise CloseSpider("Too many pages with zero results")
                return
            
            # Reset zero results counter
            self.pages_with_zero_results = 0
            
            # Process each decision item
            for i, decisao in enumerate(decisao_items):
                if self.processed_items >= self.max_items:
                    self.logger.info(f"Maximum items limit reached ({self.max_items})")
                    raise CloseSpider("Maximum items limit reached")
                
                # Extract decision data
                item = self.extract_decision_item(decisao, response)
                if item:
                    self.processed_items += 1
                    yield item
            
            self.logger.info(f"📄 Page {response.meta.get('page_number', '?')}: {items_found} items processed")
            
        except Exception as e:
            self.logger.error(f"Error parsing jurisprudência page: {e}")

    def extract_decision_item(self, decisao, response):
        """Extract individual decision item data"""
        try:
            # Extract basic decision info
            processo_link = decisao.css('h5 a::attr(href)').get()
            if not processo_link:
                return None
            
            processo_link = response.urljoin(processo_link)
            
            # Extract decision details
            item = JurisprudenciaItem()
            item['processo_link'] = processo_link
            item['numero_processo'] = decisao.css('h5 a::text').get() or ""
            item['classe_processual'] = get_classe_processual_from_url(processo_link)
            
            # Extract content details
            content_div = decisao.css('div.conteudo')
            content_text = ' '.join(content_div.css('*::text').getall())
            
            item['relator'] = extract_relator_from_content(content_text)
            item['data_publicacao'] = extract_publication_date_from_content(content_text)
            item['data_decisao'] = extract_decision_date_from_content(content_text)
            item['partes'] = extract_partes_from_content(content_text)
            item['ementa'] = content_text.strip()
            
            # Add scraping metadata
            item['scraped_at'] = datetime.now().isoformat()
            item['page_number'] = response.meta.get('page_number', 1)
            item['article'] = response.meta.get('article', 'unknown')
            item['query'] = response.meta.get('query', '')
            
            return item
            
        except Exception as e:
            self.logger.error(f"Error extracting decision item: {e}")
            return None