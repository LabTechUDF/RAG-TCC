"""
STJ Dataset Spider for CKAN portal scraping
"""
import scrapy
from urllib.parse import urljoin
import logging

from ..items import STJDecisionItem
from ..utils.ckan_utils import CKANPortalScraper
from ..utils.text_extraction import LegalTextProcessor


class STJDatasetSpider(scrapy.Spider):
    """Spider for scraping STJ dataset from CKAN portal"""
    
    name = 'stj_dataset'
    allowed_domains = ['dadosabertos.web.stj.jus.br']
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 1,  # Be conservative with government sites
        'USER_AGENT': 'RAG-TCC/stj_scraper (Academic Research; Contact: tcc@udf.edu.br)',
    }
    
    def __init__(self, dataset_url=None, limit=None, article_filter=None, 
                 cluster_order='article', output_jsonl=None, *args, **kwargs):
        super(STJDatasetSpider, self).__init__(*args, **kwargs)
        
        # Default dataset URL
        self.dataset_url = dataset_url or "https://dadosabertos.web.stj.jus.br/dataset/integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica"
        self.limit = int(limit) if limit else None
        self.article_filter = article_filter.split(',') if article_filter else None
        self.cluster_order = cluster_order
        self.output_jsonl = output_jsonl
        
        # Initialize utilities
        self.text_processor = LegalTextProcessor()
        
        self.logger.info(f"🎯 STJ Dataset Spider initialized")
        self.logger.info(f"   Dataset URL: {self.dataset_url}")
        self.logger.info(f"   Limit: {self.limit or 'No limit'}")
        self.logger.info(f"   Article filter: {self.article_filter or 'All articles'}")
        self.logger.info(f"   Output JSONL: {self.output_jsonl or 'Default location'}")
    
    def start_requests(self):
        """Generate initial requests"""
        yield scrapy.Request(
            url=self.dataset_url,
            callback=self.parse_dataset_page,
            meta={'dont_cache': True}
        )
    
    def parse_dataset_page(self, response):
        """Parse the main dataset page to find resources"""
        self.logger.info(f"📄 Parsing dataset page: {response.url}")
        
        # Extract resource items using CSS selectors (more reliable than XPath)
        resource_items = response.css('li.resource-item')
        
        if not resource_items:
            self.logger.error("❌ No resource items found on dataset page")
            return
        
        self.logger.info(f"🔍 Found {len(resource_items)} resource items")
        
        processed_count = 0
        for resource_item in resource_items:
            # Apply limit if specified
            if self.limit and processed_count >= self.limit:
                self.logger.info(f"⏹️ Reached limit of {self.limit} resources")
                break
            
            # Extract resource ID
            resource_id = resource_item.css('::attr(data-id)').get()
            if not resource_id:
                self.logger.warning("⚠️ Resource item without data-id, skipping")
                continue
            
            # Extract heading link and title
            heading_link = resource_item.css('a.heading')
            if not heading_link:
                self.logger.warning(f"⚠️ No heading link found for resource {resource_id}")
                continue
            
            resource_href = heading_link.css('::attr(href)').get()
            resource_title = heading_link.css('::attr(title)').get() or heading_link.css('::text').get()
            
            if not resource_href:
                self.logger.warning(f"⚠️ No href found for resource {resource_id}")
                continue
            
            # Check if it's a ZIP file (basic filter)
            if resource_title and not resource_title.lower().endswith('.zip'):
                self.logger.debug(f"⏭️ Skipping non-ZIP resource: {resource_title}")
                continue
            
            # Construct full URL
            resource_page_url = urljoin(response.url, resource_href)
            
            self.logger.info(f"📦 Processing resource {processed_count + 1}: {resource_title}")
            
            # Request the resource page to get download link
            yield scrapy.Request(
                url=resource_page_url,
                callback=self.parse_resource_page,
                meta={
                    'resource_id': resource_id,
                    'resource_title': resource_title,
                    'dataset_url': response.url,
                    'dont_cache': True
                }
            )
            
            processed_count += 1
    
    def parse_resource_page(self, response):
        """Parse individual resource page to get download URL"""
        resource_id = response.meta['resource_id']
        resource_title = response.meta['resource_title']
        
        self.logger.debug(f"📋 Parsing resource page for: {resource_title}")
        
        # Look for download button/link with multiple selectors
        download_selectors = [
            'a.resource-url-analytics[href*="/download/"]',
            'a[href*="/download/"]',
            'a:contains("Baixar")',
            '.btn-group a[href*="/download/"]'
        ]
        
        download_url = None
        for selector in download_selectors:
            download_links = response.css(selector)
            if download_links:
                download_href = download_links[0].css('::attr(href)').get()
                if download_href:
                    download_url = urljoin(response.url, download_href)
                    break
        
        if not download_url:
            self.logger.error(f"❌ No download URL found for resource: {resource_title}")
            return
        
        self.logger.info(f"⬇️ Found download URL for {resource_title}: {download_url}")
        
        # For now, we'll yield a placeholder item since the actual processing
        # should be done by the queue manager for better control
        # This spider serves as a discovery mechanism
        
        yield {
            'resource_id': resource_id,
            'resource_title': resource_title,
            'resource_page_url': response.url,
            'download_url': download_url,
            'dataset_url': response.meta['dataset_url']
        }