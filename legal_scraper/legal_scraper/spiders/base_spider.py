"""
Base spider for Brazilian legal content scraping
"""

import scrapy
import json
import logging
from datetime import datetime
from pathlib import Path
from scrapy_playwright.page import PageMethod
from legal_scraper.items import LegalDocumentItem
from itemloaders import ItemLoader


class BrazilianLegalSpiderBase(scrapy.Spider):
    """Base spider for Brazilian legal sites with Playwright integration"""
    
    # Default settings that can be overridden
    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'RETRY_TIMES': 3,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = self.load_config()
        self.scraped_urls = set()
        
    def load_config(self):
        """Load theme-specific configuration"""
        config_path = Path(__file__).parent.parent.parent / 'configs' / self.name / 'config.json'
        
        if not config_path.exists():
            self.logger.error(f"Configuration file not found: {config_path}")
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.info(f"Loaded configuration for {self.name}: {config.get('name', 'Unknown')}")
                return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return {}
    
    def start_requests(self):
        """Generate initial requests with Brazilian legal site optimization"""
        urls = []
        
        # Add main start URL
        if self.config.get('start_url'):
            urls.append(self.config['start_url'])
        
        # Add fallback URLs
        if self.config.get('fallback_urls'):
            urls.extend(self.config['fallback_urls'])
        
        # If no config URLs, use spider's start_urls
        if not urls and hasattr(self, 'start_urls'):
            urls = self.start_urls
        
        for url in urls:
            yield scrapy.Request(
                url=url,
                meta=self.get_playwright_meta(),
                callback=self.parse_listing,
                errback=self.handle_error
            )
    
    def get_playwright_meta(self, extra_methods=None):
        """Get standard Playwright meta configuration for Brazilian legal sites"""
        methods = [
            PageMethod('wait_for_load_state', 'domcontentloaded'),
            PageMethod('wait_for_timeout', self.config.get('delays', {}).get('page_load', 3000)),
            # Handle LGPD consent banners common in Brazilian sites
            PageMethod('evaluate', '''
                // Handle common LGPD consent banners
                const consentSelectors = [
                    '[data-consent="accept"]',
                    '.accept-cookies',
                    '.lgpd-accept',
                    '.cookie-accept',
                    '[onclick*="accept"]',
                    'button[id*="consent"]',
                    'button[class*="accept"]'
                ];
                
                for (const selector of consentSelectors) {
                    const btn = document.querySelector(selector);
                    if (btn && btn.offsetParent !== null) {
                        btn.click();
                        break;
                    }
                }
                
                // Wait a bit for consent processing
                await new Promise(resolve => setTimeout(resolve, 1000));
            '''),
        ]
        
        # Add extra methods if provided
        if extra_methods:
            methods.extend(extra_methods)
        
        return {
            'playwright': True,
            'playwright_context': 'default',
            'playwright_page_methods': methods,
            'playwright_context_kwargs': {
                'locale': 'pt-BR',
                'timezone_id': 'America/Sao_Paulo',
                'ignore_https_errors': True,
            },
            'playwright_include_page': True,
        }
    
    async def parse_listing(self, response):
        """Parse listing page and extract document links"""
        page = response.meta.get("playwright_page")
        
        try:
            self.logger.info(f"Parsing listing page: {response.url}")
            
            # Get selectors from config
            selectors = self.config.get('selectors', {})
            container_sel = selectors.get('container', 'body')
            item_sel = selectors.get('item', '.item')
            
            # Wait for content to load
            try:
                await page.wait_for_selector(container_sel, timeout=10000)
            except Exception as e:
                self.logger.warning(f"Container selector not found: {container_sel}")
            
            # Extract items
            items = response.css(item_sel)
            self.logger.info(f"Found {len(items)} items on page {response.url}")
            
            for item in items:
                for result in self.parse_item_preview(item, response, selectors):
                    yield result
            
            # Handle pagination
            pagination_request = self.handle_pagination(response, page)
            if pagination_request:
                yield pagination_request
            
        finally:
            # Always close the page
            if page:
                await page.close()
    
    def parse_item_preview(self, item, response, selectors):
        """Parse individual item preview and decide whether to follow detail link"""
        # Extract basic info
        title = self.extract_with_fallback(item, selectors.get('title', ''))
        link = self.extract_with_fallback(item, selectors.get('link', ''))
        
        if not title:
            self.logger.warning(f"No title found for item on {response.url}")
            return
        
        # Create basic item data
        item_data = {
            'theme': self.name,
            'source_site': response.url,
            'title': title,
            'scraped_at': datetime.now().isoformat(),
        }
        
        # Extract additional preview data
        for field, selector in selectors.items():
            if field not in ['container', 'item', 'title', 'link']:
                value = self.extract_with_fallback(item, selector)
                if value:
                    item_data[field] = value
        
        # If we have a detail link, follow it
        if link:
            detail_url = response.urljoin(link)
            if detail_url not in self.scraped_urls:
                self.scraped_urls.add(detail_url)
                yield scrapy.Request(
                    url=detail_url,
                    meta={
                        **self.get_playwright_meta(),
                        'item_data': item_data,
                    },
                    callback=self.parse_detail,
                    errback=self.handle_error
                )
        else:
            # No detail link, yield the preview data as final item
            yield self.create_item(item_data)
    
    async def parse_detail(self, response):
        """Parse individual document detail page"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})
        
        try:
            self.logger.debug(f"Parsing detail page: {response.url}")
            
            # Update URL to detail page
            item_data['url'] = response.url
            
            # Extract content from detail page
            selectors = self.config.get('selectors', {})
            
            # Extract full content if available
            content_selector = selectors.get('content', selectors.get('summary', ''))
            if content_selector:
                content = self.extract_with_fallback(response, content_selector)
                if content:
                    item_data['content'] = content
            
            # Extract additional fields specific to detail pages
            detail_fields = ['case_number', 'relator', 'type', 'origem', 'temas']
            for field in detail_fields:
                if field in selectors:
                    value = self.extract_with_fallback(response, selectors[field])
                    if value:
                        item_data[field] = value
            
            # Extract PDF links if available
            pdf_selector = selectors.get('pdf_link', '')
            if pdf_selector:
                pdf_link = self.extract_with_fallback(response, pdf_selector)
                if pdf_link:
                    item_data['pdf_url'] = response.urljoin(pdf_link)
            
            yield self.create_item(item_data)
            
        finally:
            # Always close the page
            if page:
                await page.close()
    
    def handle_pagination(self, response, page):
        """Handle pagination for listing pages"""
        pagination_config = self.config.get('pagination', {})
        if not pagination_config:
            return None
        
        max_pages = pagination_config.get('max_pages', 10)
        current_page = response.meta.get('page_number', 1)
        
        if current_page >= max_pages:
            self.logger.info(f"Reached maximum pages limit: {max_pages}")
            return None
        
        # Find next page link
        next_selector = pagination_config.get('selector', '')
        if next_selector:
            next_link = response.css(next_selector + '::attr(href)').get()
            if next_link:
                next_url = response.urljoin(next_link)
                return scrapy.Request(
                    url=next_url,
                    meta={
                        **self.get_playwright_meta(),
                        'page_number': current_page + 1,
                    },
                    callback=self.parse_listing,
                    errback=self.handle_error
                )
            else:
                self.logger.info(f"No next page link found on {response.url}")
        
        return None
    
    def extract_with_fallback(self, selector_obj, selectors):
        """Extract text with fallback selectors"""
        if not selectors:
            return None
        
        # Handle multiple selectors separated by comma
        if isinstance(selectors, str):
            selectors = [s.strip() for s in selectors.split(',')]
        elif not isinstance(selectors, list):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                # Try with ::text first
                text = selector_obj.css(f"{selector}::text").get()
                if text and text.strip():
                    return text.strip()
                
                # Try without ::text (get innerHTML)
                text = selector_obj.css(selector).get()
                if text and text.strip():
                    # Clean HTML if present
                    from w3lib.html import remove_tags
                    return remove_tags(text).strip()
                    
            except Exception as e:
                self.logger.debug(f"Error with selector '{selector}': {e}")
                continue
        
        return None
    
    def create_item(self, item_data):
        """Create appropriate item type based on theme"""
        # Import here to avoid circular imports
        from legal_scraper.items import (
            JurisprudenciaItem, SumulaItem, NormativaItem, 
            DireitoPenalItem, TribunalEstadualItem, LegalDocumentItem
        )
        
        # Map theme to item class
        item_classes = {
            'jurisprudencia': JurisprudenciaItem,
            'sumulas_stf': SumulaItem,
            'normativas_stj': NormativaItem,
            'direito_penal': DireitoPenalItem,
            'tribunais_estaduais': TribunalEstadualItem,
        }
        
        ItemClass = item_classes.get(self.name, LegalDocumentItem)
        item = ItemClass()
        
        # Populate item with data
        for key, value in item_data.items():
            if hasattr(item, key):
                item[key] = value
        
        return item
    
    async def handle_error(self, failure):
        """Handle request errors"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")
        
        # Close page if exists
        page = failure.request.meta.get("playwright_page")
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.warning(f"Error closing page: {e}") 