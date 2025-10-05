"""
STJ Jurisprudência Spider - Extracts decision texts from STJ SCON system
"""

import re
import json
import scrapy
import os
from datetime import datetime
from pathlib import Path
from scrapy.exceptions import CloseSpider
from scrapy_playwright.page import PageMethod
from stj_scraper.items import (
    JurisprudenciaItem, 
    get_classe_processual_from_url,
    extract_relator_from_content,
    extract_publication_date_from_content,
    extract_decision_date_from_content,
    extract_partes_from_content
)
from stj_scraper.utils.stj_selectors import (
    TEXTAREA_XPATH,
    TEXTAREA_CSS,
    DECISION_LINK_SELECTORS,
    NEXT_PAGE_SELECTORS
)
from stj_scraper.utils.stj_parsers import (
    extract_case_number_from_content,
    clean_textarea_content,
    is_valid_stj_decision
)


class StjJurisprudenciaSpider(scrapy.Spider):
    """STJ SCON spider for extracting decision texts from textarea elements"""

    name = 'stj_jurisprudencia'
    allowed_domains = ['scon.stj.jus.br']

    def load_query_array(self):
        """Load query array from JSON file"""
        # Check if custom query file is provided via settings
        custom_query_file = getattr(self, 'query_file', None)
        
        if custom_query_file:
            query_file = Path(custom_query_file)
        else:
            # Default query file path
            query_file = Path(__file__).parent.parent.parent / 'data' / 'simple_query_spider' / 'query_links.json'
        
        if not query_file.exists():
            self.logger.error(f"Query file not found: {query_file}")
            return []
        
        try:
            with open(query_file, 'r', encoding='utf-8') as f:
                query_array = json.load(f)
            self.logger.info(f"Loaded {len(query_array)} queries from {query_file}")
            return query_array
        except Exception as e:
            self.logger.error(f"Error loading query file: {e}")
            return []

    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["font", "media"],  # Allow images and stylesheets for stealth
        'DOWNLOAD_DELAY': 5,
        'RANDOMIZE_DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Stealth mode - single request
        'CONCURRENT_REQUESTS': 1,  # Stealth mode - single request
        'RETRY_TIMES': 5,  # More retries for 403 errors
        'ROBOTSTXT_OBEY': False,
        'RETRY_HTTP_CODES': [403, 429, 500, 502, 503, 504, 408],  # Retry 403 errors
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load query array from JSON file
        self.query_array = self.load_query_array()
        self.current_query_info = None
        
        # Generate start_urls from query array, but adapt for STJ SCON
        self.start_urls = self.adapt_urls_for_stj(self.query_array)
        
        # Check if we're in development mode
        self.dev_mode = (
            kwargs.get('dev_mode', '').lower() in ['true', '1', 'yes'] or
            os.getenv('SPIDER_DEV_MODE', '').lower() in ['true', '1', 'yes'] or
            os.getenv('ENV', '').lower() in ['dev', 'development']
        )
        
        if self.dev_mode:
            self.items_extracted = 0
            self.max_items = 5
            self.logger.info("🚧 Running in DEVELOPMENT mode - limited to 5 items")
            self.custom_settings['CLOSESPIDER_ITEMCOUNT'] = 5
        else:
            self.items_extracted = 0
            self.max_items = None  # No limit in production
            self.logger.info("🚀 Running in PRODUCTION mode - no item limit")
            if 'CLOSESPIDER_ITEMCOUNT' in self.custom_settings:
                del self.custom_settings['CLOSESPIDER_ITEMCOUNT']

    def adapt_urls_for_stj(self, query_array):
        """Adapt STF URLs to STJ SCON URLs with proper search parameters"""
        stj_urls = []
        
        for query_info in query_array:
            query_text = query_info['query']
            artigo = query_info['artigo']
            
            # Encode query for URL (replace spaces with +, handle special chars)
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query_text)
            
            # Build STJ SCON search URL with the required parameters
            # Base URL structure: https://scon.stj.jus.br/SCON/pesquisar.jsp
            stj_url = (
                f"https://scon.stj.jus.br/SCON/pesquisar.jsp?"
                f"b=DTXT&"
                f"numDocsPagina=50&"
                f"i=1&"
                f"O=&"
                f"ref=&"
                f"processo=&"
                f"ementa=&"
                f"nota=&"
                f"filtroPorNota=&"
                f"orgao=&"
                f"relator=&"
                f"uf=&"
                f"classe=&"
                f"data=&"
                f"dtpb=&"
                f"dtde=&"
                f"tp=T&"
                f"operador=e&"
                f"livre={encoded_query}"
            )
            
            # Update query_info with STJ URL
            query_info['stj_url'] = stj_url
            stj_urls.append(stj_url)
            
            self.logger.info(f"Adapted Article {artigo}: {stj_url}")
        
        return stj_urls

    def start_requests(self):
        """Generate requests with STJ SCON-optimized Playwright settings"""
        # First, test access to STJ main page to check for blocks
        yield scrapy.Request(
            url="https://scon.stj.jus.br/SCON/",
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'test_access': True,
                'playwright_page_methods': [
                    PageMethod('wait_for_load_state', 'networkidle'),
                ],
                'playwright_context_kwargs': {
                    'ignore_https_errors': True,
                    'extra_http_headers': {
                        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        'Referer': 'https://www.stj.jus.br/',
                    },
                },
            },
            callback=self.test_stj_access,
            errback=self.handle_error,
            dont_filter=True
        )
    
    def start_search_requests(self):
        """Generate actual search requests after confirming STJ access"""
        for i, query_info in enumerate(self.query_array):
            if i < len(self.start_urls):
                url = self.start_urls[i]
                yield scrapy.Request(
                    url=url,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'query_info': query_info,  # Pass query info to the request
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                            # Wait for STJ SCON results to load
                            PageMethod('wait_for_function', '''
                                () => {
                                    // Wait for any of these indicators that results have loaded
                                    return document.querySelector('table') ||
                                           document.querySelector('.resultado') ||
                                           document.querySelector('.sem-resultado') ||
                                           document.querySelector('.loading') === null ||
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
                    callback=self.parse_stj_listing,
                    errback=self.handle_error
                )

    async def test_stj_access(self, response):
        """Test access to STJ main page before proceeding"""
        page = response.meta.get("playwright_page")
        
        try:
            self.logger.info(f"Testing STJ access: {response.url} - Status: {response.status}")
            
            if response.status == 200:
                self.logger.info("✅ STJ access test successful - proceeding with searches")
                
                # Add some stealth behaviors
                if page:
                    # Simulate human behavior
                    await page.wait_for_timeout(2000)  # Wait 2 seconds
                    await page.evaluate("window.scrollTo(0, 100)")  # Small scroll
                    await page.wait_for_timeout(1000)
                
                # Now start the actual search requests
                for request in self.start_search_requests():
                    yield request
                    
            else:
                self.logger.error(f"❌ STJ access test failed with status {response.status}")
                raise CloseSpider(f"STJ site access blocked (status {response.status})")
                
        except Exception as e:
            self.logger.error(f"Error in STJ access test: {e}")
            raise CloseSpider(f"STJ access test failed: {e}")
            
        finally:
            if page:
                await page.close()

    async def parse_stj_listing(self, response):
        """Parse STJ SCON search results page"""
        page = response.meta.get("playwright_page")
        query_info = response.meta.get("query_info")
        
        # Store current query info for this request
        self.current_query_info = query_info

        try:
            self.logger.info(f"Parsing STJ SCON listing for Article {query_info['artigo']}: {response.url}")

            # Wait for page to be fully interactive
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('table') ||
                            document.querySelector('.sem-resultado') ||
                            document.querySelector('.loading') === null);
                }
            ''', timeout=15000)

            # Log page title for debugging
            page_title = await page.title()
            self.logger.info(f"Page title: {page_title}")

            # Look for results in STJ SCON format (usually in tables)
            # STJ SCON typically shows results in a table with links to decisions
            result_links = []
            
            # Try multiple selectors for STJ SCON decision links
            decision_selectors = [
                'a[href*="verDecisao.asp"]',
                'a[href*="texto="]',
                'td.texto a',
                'table a[href*="texto"]',
                'a[onclick*="javascript:"]'
            ]
            
            for selector in decision_selectors:
                links = response.css(selector + '::attr(href)').getall()
                if links:
                    result_links.extend(links)
                    self.logger.info(f"Found {len(links)} decision links with selector: {selector}")
                    break
            
            if not result_links:
                # Check for "no results" message
                no_results_indicators = [
                    'sem resultado', 'nenhum documento', 'não foram encontrados',
                    'sem documentos', 'consulta não retornou'
                ]
                
                page_text = await page.text_content('body')
                page_text_lower = page_text.lower() if page_text else ""
                
                has_no_results = any(indicator in page_text_lower for indicator in no_results_indicators)
                
                if has_no_results:
                    self.logger.warning(f"No results found for Article {query_info['artigo']}")
                else:
                    self.logger.warning(f"No decision links found - might need different selectors. Page length: {len(page_text_lower) if page_text else 0}")
                
                return

            # Process each decision link
            self.logger.info(f"Processing {len(result_links)} decision links")
            
            for i, link in enumerate(result_links):
                # Check if we've reached the maximum number of items (only in dev mode)
                if self.dev_mode and self.max_items is not None and self.items_extracted >= self.max_items:
                    self.logger.info(f"🛑 DEV MODE: Reached maximum items limit ({self.max_items}). Stopping spider.")
                    break
                
                if self.dev_mode:
                    self.logger.info(f"Processing decision {i+1}/{len(result_links)} (DEV MODE: {self.items_extracted}/{self.max_items})")
                else:
                    self.logger.info(f"Processing decision {i+1}/{len(result_links)} (PROD MODE: {self.items_extracted} extracted)")

                # Build full URL for decision
                decision_url = response.urljoin(link)
                
                # Create initial item data
                item_data = {
                    'title': f"STJ Decision {i+1} - Article {query_info['artigo']}",
                    'source_url': response.url,
                    'decision_url': decision_url,
                    'scraped_at': datetime.now().isoformat(),
                    'item_index': i+1,
                    'current_article': query_info.get('artigo', 'unknown'),
                    'query_text': query_info.get('query', ''),
                }

                # Follow decision URL to extract text from textarea
                self.logger.info(f"Following decision URL {i+1}: {decision_url}")
                
                yield scrapy.Request(
                    url=decision_url,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                            PageMethod('wait_for_function', '''
                                () => {
                                    return document.readyState === 'complete' &&
                                           (document.querySelector('#textSemformatacao1') ||
                                            document.querySelector('textarea') ||
                                            document.querySelector('.texto'));
                                }
                            ''', timeout=30000),
                        ],
                        'item_data': item_data,
                    },
                    callback=self.parse_decision_text,
                    errback=self.handle_error
                )

            # Handle pagination - look for "Próxima" link
            await self.handle_pagination(page, response, query_info)

        finally:
            if page:
                await page.close()

    async def parse_decision_text(self, response):
        """Parse the decision page to extract text from textarea #textSemformatacao1"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})

        try:
            self.logger.info(f"Parsing decision text page: {response.url}")

            # Wait for textarea to be present
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('#textSemformatacao1') ||
                            document.querySelector('textarea'));
                }
            ''', timeout=15000)

            # Extract text from the specific textarea using multiple methods
            raw_text = None
            raw_container_html = None
            
            # Method 1: Try XPath
            try:
                textarea_element = await page.query_selector(TEXTAREA_XPATH)
                if textarea_element:
                    raw_text = await textarea_element.get_property('value')
                    raw_text = await raw_text.json_value() if raw_text else None
                    raw_container_html = await textarea_element.get_property('outerHTML')
                    raw_container_html = await raw_container_html.json_value() if raw_container_html else None
                    self.logger.info(f"✅ Method 1 (XPath): Extracted {len(raw_text or '')} characters")
            except Exception as e:
                self.logger.debug(f"Method 1 (XPath) failed: {e}")

            # Method 2: Try CSS selector if XPath failed
            if not raw_text:
                try:
                    textarea_element = await page.query_selector(TEXTAREA_CSS)
                    if textarea_element:
                        raw_text = await textarea_element.get_property('value')
                        raw_text = await raw_text.json_value() if raw_text else None
                        raw_container_html = await textarea_element.get_property('outerHTML')
                        raw_container_html = await raw_container_html.json_value() if raw_container_html else None
                        self.logger.info(f"✅ Method 2 (CSS): Extracted {len(raw_text or '')} characters")
                except Exception as e:
                    self.logger.debug(f"Method 2 (CSS) failed: {e}")

            # Method 3: Try any textarea if specific ID failed
            if not raw_text:
                try:
                    textarea_elements = await page.query_selector_all('textarea')
                    for i, textarea in enumerate(textarea_elements):
                        text = await textarea.get_property('value')
                        text = await text.json_value() if text else None
                        if text and len(text.strip()) > 100:  # Minimum content length
                            raw_text = text
                            raw_container_html = await textarea.get_property('outerHTML')
                            raw_container_html = await raw_container_html.json_value() if raw_container_html else None
                            self.logger.info(f"✅ Method 3 (Textarea {i+1}): Extracted {len(raw_text)} characters")
                            break
                except Exception as e:
                    self.logger.debug(f"Method 3 (Any textarea) failed: {e}")

            # Method 4: Fallback to text content if textarea not found
            if not raw_text:
                try:
                    # Look for text content in common STJ decision containers
                    content_selectors = ['.texto', '.decisao', '.conteudo', 'main', 'body']
                    for selector in content_selectors:
                        element = await page.query_selector(selector)
                        if element:
                            raw_text = await element.text_content()
                            if raw_text and len(raw_text.strip()) > 200:
                                self.logger.info(f"✅ Method 4 (Fallback {selector}): Extracted {len(raw_text)} characters")
                                break
                except Exception as e:
                    self.logger.debug(f"Method 4 (Fallback) failed: {e}")

            # Process extracted text
            if raw_text:
                # Clean and validate the content
                cleaned_text = clean_textarea_content(raw_text)
                
                if is_valid_stj_decision(cleaned_text):
                    item_data['raw_text'] = cleaned_text
                    item_data['content'] = cleaned_text  # Also set as content for compatibility
                    item_data['raw_container_html'] = raw_container_html
                    item_data['extraction_method'] = 'textarea_value'
                    item_data['success'] = True
                    item_data['errors'] = None
                    
                    # Extract metadata from content
                    item_data['case_number'] = extract_case_number_from_content(cleaned_text)
                    item_data['relator'] = extract_relator_from_content(cleaned_text)
                    item_data['publication_date'] = extract_publication_date_from_content(cleaned_text)
                    item_data['decision_date'] = extract_decision_date_from_content(cleaned_text)
                    item_data['partes'] = extract_partes_from_content(cleaned_text)
                    
                    self.logger.info(f"✅ Successfully extracted and validated STJ decision text ({len(cleaned_text)} chars)")
                else:
                    item_data['raw_text'] = cleaned_text
                    item_data['content'] = cleaned_text
                    item_data['extraction_method'] = 'textarea_value_unvalidated'
                    item_data['success'] = False
                    item_data['errors'] = 'Content validation failed - does not appear to be a valid STJ decision'
                    self.logger.warning("❌ Extracted text failed STJ decision validation")
            else:
                # No text could be extracted
                item_data['raw_text'] = ""
                item_data['content'] = ""
                item_data['extraction_method'] = 'failed'
                item_data['success'] = False
                item_data['errors'] = 'No textarea or text content found on page'
                self.logger.error("❌ No text could be extracted from decision page")

            # Add timestamps and metadata
            item_data['captured_at_utc'] = datetime.utcnow().isoformat() + 'Z'
            item_data['input_url'] = self.current_query_info.get('stj_url', '') if self.current_query_info else ''

            yield self.create_item(item_data)

        except Exception as e:
            self.logger.error(f"Error parsing decision text: {e}")
            # Still yield an item with error information
            item_data['raw_text'] = ""
            item_data['content'] = f"Error extracting decision text: {str(e)}"
            item_data['extraction_method'] = 'error'
            item_data['success'] = False
            item_data['errors'] = str(e)
            item_data['captured_at_utc'] = datetime.utcnow().isoformat() + 'Z'
            yield self.create_item(item_data)

        finally:
            if page:
                await page.close()

    async def handle_pagination(self, page, response, query_info):
        """Handle pagination for STJ SCON results"""
        try:
            # Look for "Próxima" or next page links
            next_selectors = [
                'a:has-text("Próxima")',
                'a:has-text("próxima")',
                'a[href*="pagina="]',
                'input[value="Próxima"]',
                '.paginacao a:last-child'
            ]
            
            next_link = None
            for selector in next_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        href = await element.get_attribute('href')
                        if href and href != '#':
                            next_link = response.urljoin(href)
                            self.logger.info(f"Found next page link: {next_link}")
                            break
                except Exception as e:
                    self.logger.debug(f"Next page selector {selector} failed: {e}")
            
            if next_link and not self.dev_mode:  # Skip pagination in dev mode
                self.logger.info(f"Following next page: {next_link}")
                yield scrapy.Request(
                    url=next_link,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'query_info': query_info,
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                            PageMethod('wait_for_function', '''
                                () => {
                                    return document.readyState === 'complete' &&
                                           (document.querySelector('table') ||
                                            document.querySelector('.sem-resultado'));
                                }
                            ''', timeout=30000),
                        ],
                    },
                    callback=self.parse_stj_listing,
                    errback=self.handle_error
                )
            
        except Exception as e:
            self.logger.error(f"Error handling pagination: {e}")

    def create_item(self, item_data):
        """Create a STJ jurisprudence item"""
        item = JurisprudenciaItem()

        # Map data to item fields with STJ-specific naming
        if self.current_query_info:
            article_number = self.current_query_info.get('artigo', 'unknown')
            query_text = self.current_query_info.get('query', '')
            
            item['cluster_name'] = f"art_{article_number}"
            item['cluster_description'] = f"{query_text} (art. {article_number} do Código Penal)"
            item['article_reference'] = f"CP art. {article_number}"
            item['source'] = f"stj_scraper"  # Changed from STF to indicate STJ origin
        else:
            item['cluster_name'] = 'stj_jurisprudencia'
            item['cluster_description'] = 'Jurisprudência STJ'
            item['article_reference'] = 'N/A'
            item['source'] = 'stj_scraper'
            
        item['title'] = item_data.get('title', f"STJ Item {item_data.get('item_index', 'Unknown')}")
        item['case_number'] = item_data.get('case_number', '')
        item['content'] = item_data.get('content', '') or item_data.get('raw_text', '')
        item['url'] = item_data.get('decision_url', '') or item_data.get('source_url', '')
        item['tribunal'] = 'STJ'  # Changed from STF to STJ
        item['legal_area'] = 'Penal'  # Based on search query
        
        # Extract classe processual from URL or content
        current_url = self.current_query_info.get('stj_url', '') if self.current_query_info else ''
        item['classe_processual_unificada'] = get_classe_processual_from_url(current_url) or get_classe_processual_from_url(item_data.get('content', ''))

        # STJ-specific fields
        item['raw_text'] = item_data.get('raw_text', '')
        item['raw_container_html'] = item_data.get('raw_container_html', '')
        item['captured_at_utc'] = item_data.get('captured_at_utc', datetime.utcnow().isoformat() + 'Z')
        item['success'] = item_data.get('success', False)
        item['errors'] = item_data.get('errors', '')
        item['input_url'] = item_data.get('input_url', '')
        item['decision_url'] = item_data.get('decision_url', '')

        # Extract fields from content if present
        content = item_data.get('raw_text', '') or item_data.get('content', '')
        if content:
            item['relator'] = item_data.get('relator', '') or extract_relator_from_content(content)
            item['publication_date'] = item_data.get('publication_date', '') or extract_publication_date_from_content(content)
            item['decision_date'] = item_data.get('decision_date', '') or extract_decision_date_from_content(content)
            item['partes'] = item_data.get('partes', '') or extract_partes_from_content(content)

        # Increment the items counter
        self.items_extracted += 1
        
        if self.dev_mode:
            self.logger.info(f"✅ DEV MODE: Created STJ item {self.items_extracted}/{self.max_items}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        else:
            self.logger.info(f"✅ PROD MODE: Created STJ item {self.items_extracted}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")