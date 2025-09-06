"""
Consolidated STF Legal Spider - Focused on extracting legal decisions from STF
"""

import re
import json
import scrapy
from datetime import datetime
from pathlib import Path
from scrapy_playwright.page import PageMethod
from stf_scraper.items import LegalDocumentItem


class StfLegalSpider(scrapy.Spider):
    """Consolidated spider for STF legal content extraction"""

    name = 'stf_legal'
    allowed_domains = ['jurisprudencia.stf.jus.br']

    # Default search for criminal law - estelionato previdenciário 
    default_query = '"estelionato previdenciário" "(artigo ou art) 171 §3"~3 natureza'
    
    def __init__(self, query=None, max_results=250, *args, **kwargs):
        super(StfLegalSpider, self).__init__(*args, **kwargs)
        
        # Allow custom search query
        self.search_query = query or self.default_query
        self.max_results = min(int(max_results), 250)  # STF limit
        
        # Build search URL
        base_url = 'https://jurisprudencia.stf.jus.br/pages/search'
        params = {
            'base': 'decisoes',
            'pesquisa_inteiro_teor': 'false',
            'sinonimo': 'true',
            'plural': 'true',
            'radicais': 'false',
            'buscaExata': 'true',
            'page': '1',
            'pageSize': str(self.max_results),
            'queryString': self.search_query,
            'sort': '_score',
            'sortBy': 'desc'
        }
        
        # Build URL with parameters
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        self.start_urls = [f"{base_url}?{param_string}"]
        
        self.logger.info(f"STF Legal Spider initialized")
        self.logger.info(f"Search query: {self.search_query}")
        self.logger.info(f"Max results: {self.max_results}")

    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Be gentle with STF
        'RETRY_TIMES': 3,
        'ROBOTSTXT_OBEY': False,
    }

    def start_requests(self):
        """Generate requests with STF-optimized Playwright settings"""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_function', '''
                            () => {
                                // Wait for search results to load
                                return document.querySelector('div[id^="result-index-"]') ||
                                       document.querySelector('.no-results') ||
                                       document.querySelector('.sem-resultados') ||
                                       document.readyState === 'complete';
                            }
                        ''', timeout=30000),
                    ],
                    'playwright_context_kwargs': {
                        'ignore_https_errors': True,
                        'extra_http_headers': {
                            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        },
                    },
                },
                callback=self.parse_stf_results,
                errback=self.handle_error
            )

    async def parse_stf_results(self, response):
        """Parse STF search results page"""
        page = response.meta.get("playwright_page")

        try:
            self.logger.info(f"Parsing STF results: {response.url}")

            # Wait for page to be fully loaded
            await page.wait_for_function('''
                () => document.readyState === 'complete'
            ''', timeout=10000)

            page_title = await page.title()
            self.logger.info(f"Page title: {page_title}")

            # Look for result items
            result_items = response.css('div[id^="result-index-"]')
            
            if not result_items:
                self.logger.warning("No result items found")
                return

            self.logger.info(f"Found {len(result_items)} result items")

            # Process each result item
            for i, item in enumerate(result_items):
                try:
                    # Extract basic information
                    item_data = {
                        'item_index': i + 1,
                        'scraped_at': datetime.now().isoformat(),
                        'source_url': response.url
                    }

                    # Extract clipboard content if available
                    clipboard_content = await self.extract_clipboard_content(page, item, i)
                    if clipboard_content:
                        item_data['clipboard_content'] = clipboard_content
                        item_data['content_length'] = len(clipboard_content)

                    # Extract process link
                    processo_link = item.css('a[href*="processos/listarProcessos.asp"]::attr(href)').get()
                    if processo_link:
                        item_data['processo_link'] = processo_link

                    # Extract other metadata from the item
                    self.extract_item_metadata(item, item_data)

                    # Create and yield the item
                    legal_item = self.create_legal_item(item_data)
                    yield legal_item

                except Exception as e:
                    self.logger.error(f"Error processing item {i+1}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error parsing STF results: {e}")
        finally:
            if page:
                await page.close()

    async def extract_clipboard_content(self, page, item, index):
        """Extract content from clipboard buttons"""
        try:
            # Look for clipboard buttons in the item
            clipboard_selectors = [
                f'a[id^="clipboard-despacho"][id*="{index}"]',
                f'a[id^="clipboard-"][id*="{index}"]',
                'a[id^="clipboard-despacho"]',
                'a[id^="clipboard-"]',
                'a[class*="clipboard"]',
                '[onclick*="clipboard"]'
            ]

            clipboard_element = None
            for selector in clipboard_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    # Find the element within this result item
                    for element in elements:
                        try:
                            # Check if this element is within our result item
                            parent_result = await element.evaluate('''
                                element => {
                                    let parent = element.closest('div[id^="result-index-"]');
                                    return parent ? parent.id : null;
                                }
                            ''')
                            
                            if parent_result and str(index) in parent_result:
                                clipboard_element = element
                                break
                        except:
                            continue
                        
                if clipboard_element:
                    break

            if not clipboard_element:
                return None

            # Click the clipboard button and wait for content
            await clipboard_element.click()
            await page.wait_for_timeout(2000)  # Wait for clipboard action

            # Try to get clipboard content from various possible locations
            content_selectors = [
                '#clipboard-content',
                '.clipboard-result',
                '.modal-body',
                '[id*="clipboard"] textarea',
                '[id*="clipboard"] pre'
            ]

            for selector in content_selectors:
                try:
                    content_element = await page.query_selector(selector)
                    if content_element:
                        content = await content_element.inner_text()
                        if content and len(content.strip()) > 50:
                            return content.strip()
                except:
                    continue

            return None

        except Exception as e:
            self.logger.debug(f"Could not extract clipboard for item {index}: {e}")
            return None

    def extract_item_metadata(self, item, item_data):
        """Extract metadata from a result item"""
        try:
            # Extract title/ementa
            title_selectors = ['h2', 'h3', '.titulo-decisao', '.ementa']
            for selector in title_selectors:
                title = item.css(f'{selector}::text').get()
                if title:
                    item_data['title'] = title.strip()
                    break

            # Extract case number
            case_selectors = ['.numero-processo', '.processo', '.case-number']
            for selector in case_selectors:
                case_number = item.css(f'{selector}::text').get()
                if case_number:
                    item_data['case_number'] = case_number.strip()
                    break

            # Extract relator
            relator_selectors = ['.relator', '.ministro']
            for selector in relator_selectors:
                relator = item.css(f'{selector}::text').get()
                if relator:
                    item_data['relator'] = relator.strip()
                    break

            # Extract decision date
            date_selectors = ['.data-julgamento', '.data-decisao']
            for selector in date_selectors:
                decision_date = item.css(f'{selector}::text').get()
                if decision_date:
                    item_data['decision_date'] = decision_date.strip()
                    break

        except Exception as e:
            self.logger.debug(f"Error extracting metadata: {e}")

    def create_legal_item(self, item_data):
        """Create a legal document item"""
        item = LegalDocumentItem()

        # Basic fields
        item['theme'] = 'stf_legal'
        item['title'] = item_data.get('title', f"STF Item {item_data.get('item_index', 'Unknown')}")
        item['case_number'] = item_data.get('case_number', '')
        item['content'] = item_data.get('clipboard_content', 
                                       f"STF Item {item_data.get('item_index')} - No clipboard content available. Please check original source.")
        item['url'] = item_data.get('processo_link', '') or item_data.get('source_url', '')
        item['source_site'] = item_data.get('source_url', '')
        item['tribunal'] = 'STF'
        item['court_level'] = 'Supremo Tribunal Federal'
        item['document_type'] = 'Decisão'
        item['legal_area'] = 'Penal'  # Based on default search
        item['scraped_at'] = item_data.get('scraped_at')

        # STF-specific metadata
        if item_data.get('relator'):
            item['relator'] = item_data['relator']

        if item_data.get('decision_date'):
            item['decision_date'] = item_data['decision_date']

        # Content quality score
        content_length = item_data.get('content_length', 0)
        if content_length > 1000:
            item['content_quality'] = 80
        elif content_length > 500:
            item['content_quality'] = 60
        elif content_length > 100:
            item['content_quality'] = 40
        else:
            item['content_quality'] = 20

        self.logger.info(f"Created item: {item.get('title', 'No title')[:50]}...")
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")
