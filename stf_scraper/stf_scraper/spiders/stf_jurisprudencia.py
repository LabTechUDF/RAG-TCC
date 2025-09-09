"""
STF Jurisprudência Spider - Focused on extracting clipboard content and PDFs from STF decisões
"""

import scrapy
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from scrapy.exceptions import CloseSpider
from scrapy_playwright.page import PageMethod
from ..items import (
    JurisprudenciaItem,
    get_classe_processual_from_url,
    extract_relator_from_content,
    extract_publication_date_from_content,
    extract_decision_date_from_content,
    extract_partes_from_content
)


class StfJurisprudenciaSpider(scrapy.Spider):
    """Focused spider for STF jurisprudência content and PDF extraction"""

    name = 'stf_jurisprudencia'
    allowed_domains = ['jurisprudencia.stf.jus.br']

    # Base URL for building search queries
    base_search_url = 'https://jurisprudencia.stf.jus.br/pages/search'

    # Default search parameters
    default_search_params = {
        'base': 'decisoes',
        'pesquisa_inteiro_teor': 'false',
        'sinonimo': 'true',
        'plural': 'true',
        'radicais': 'false',
        'buscaExata': 'true',
        'page': '1',
        'pageSize': '250',
        'sort': '_score',
        'sortBy': 'desc'
    }

    # Default query if none provided
    default_query = '"estelionato previdenciário" "(artigo ou art) 171 §3"~3 natureza'

    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,  # Be gentle with STF
        'CONCURRENT_REQUESTS': 1,  # Ensure only one request at a time to avoid browser conflicts
        'RETRY_TIMES': 3,
        'ROBOTSTXT_OBEY': False,
        # Note: CLOSESPIDER_ITEMCOUNT will be set dynamically in __init__ based on dev mode
    }

    def __init__(self, query=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set the search queries from command line parameter or use default
        if query:
            # Split multiple queries by comma and clean whitespace
            self.queries = [q.strip() for q in query.split(',') if q.strip()]
        else:
            self.queries = [self.default_query]

        self.logger.info(f"🔍 Search queries ({len(self.queries)}): {self.queries}")

        # Check if we're in development mode
        # Can be set via environment variable or spider argument
        self.dev_mode = (
            kwargs.get('dev_mode', '').lower() in ['true', '1', 'yes'] or
            os.getenv('SPIDER_DEV_MODE', '').lower() in ['true', '1', 'yes'] or
            os.getenv('ENV', '').lower() in ['dev', 'development']
        )

        if self.dev_mode:
            self.items_extracted = 0
            self.max_items = 5
            self.logger.info("🚧 Running in DEVELOPMENT mode - limited to 5 items")
            # Set the Scrapy built-in item count limit as backup
            self.custom_settings['CLOSESPIDER_ITEMCOUNT'] = 5
        else:
            self.items_extracted = 0
            self.max_items = None  # No limit in production
            self.logger.info("🚀 Running in PRODUCTION mode - no item limit")
            # Remove any item count limit
            if 'CLOSESPIDER_ITEMCOUNT' in self.custom_settings:
                del self.custom_settings['CLOSESPIDER_ITEMCOUNT']

    def build_search_url(self, query):
        """Build the search URL with proper encoding"""
        params = self.default_search_params.copy()
        params['queryString'] = query

        # Build URL with properly encoded parameters
        param_string = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
        return f"{self.base_search_url}?{param_string}"

    def yield_item_with_limit_check(self, item_data):
        """Yield an item and check if we've reached the extraction limit (only in dev mode)"""
        item = self.create_item(item_data)

        # Only check limit in development mode
        if self.dev_mode and self.max_items is not None:
            if self.items_extracted >= self.max_items:
                self.logger.info(f"🏁 DEV MODE: Reached maximum items limit ({self.max_items}). Closing spider.")
                raise CloseSpider(f"DEV MODE: Reached maximum items limit: {self.max_items}")

        return item

    def start_requests(self):
        """Generate requests with STF-optimized Playwright settings for multiple queries"""
        # Process each query separately
        for query in self.queries:
            search_url = self.build_search_url(query)
            self.logger.info(f"🌐 Generated search URL for query '{query}': {search_url}")

            yield scrapy.Request(
                url=search_url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        # Try multiple selectors that might indicate loaded results
                        PageMethod('wait_for_function', '''
                            () => {
                                // Wait for any of these indicators that results have loaded
                                return document.querySelector('div[id^="result-index-"]') ||
                                       document.querySelector('.resultado-pesquisa') ||
                                       document.querySelector('.search-results') ||
                                       document.querySelector('.no-results') ||
                                       document.querySelector('.loading') === null;
                            }
                        ''', timeout=30000),
                    ],
                    'playwright_context_kwargs': {
                        'ignore_https_errors': True,
                        'extra_http_headers': {
                            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        },
                    },
                    'query': query  # Pass current query in meta for tracking
                },
                callback=self.parse_stf_listing,
                errback=self.handle_error
            )

    async def parse_stf_listing(self, response):
        """Parse STF search results page"""
        page = response.meta.get("playwright_page")
        query = response.meta.get('query')

        try:
            self.logger.info(f"Parsing STF listing for query '{query}': {response.url}")

            # Wait for page to be fully interactive and check what we actually have
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('div[id^="result-index-"]') ||
                            document.querySelector('.no-results') ||
                            document.querySelector('.loading') === null);
                }
            ''', timeout=15000)

            # Log page title and basic info for debugging
            page_title = await page.title()
            self.logger.info(f"Page title: {page_title}")

            # Try multiple possible selectors for result items
            result_selectors = [
                'div[id^="result-index-"]'
            ]

            result_items = []
            for selector in result_selectors:
                result_items = response.css(selector)
                if result_items:
                    self.logger.info(f"Found {len(result_items)} items with selector: {selector}")
                    break

            if not result_items:
                # Check if there's a "no results" message or if we need to wait more
                no_results = response.css('.no-results, .sem-resultados, .empty-results').get()
                if no_results:
                    self.logger.warning(f"No results found for query '{query}' - empty result set")
                else:
                    # Let's see what's actually on the page
                    page_content = await page.content()
                    self.logger.warning(f"No result items found for query '{query}'. Page content length: {len(page_content)}")

                return

            # Process each result item
            for i, item in enumerate(result_items):
                # Check if we've reached the maximum number of items (only in dev mode)
                if self.dev_mode and self.max_items is not None and self.items_extracted >= self.max_items:
                    self.logger.info(f"🛑 DEV MODE: Reached maximum items limit ({self.max_items}). Stopping spider.")
                    break

                if self.dev_mode:
                    self.logger.info(f"Processing item {i+1}/{len(result_items)} (DEV MODE: {self.items_extracted}/{self.max_items})")
                else:
                    self.logger.info(f"Processing item {i+1}/{len(result_items)} (PROD MODE: {self.items_extracted} extracted)")

                # Extract the main decision data link and title
                decision_data_link = None
                title = None
                case_number_from_url = None

                # Extract decision data link with title
                decision_link_selector = 'a[mattooltip="Dados completos"]'
                decision_element = item.css(decision_link_selector)

                if decision_element:
                    # Get the href for complete decision data
                    decision_data_link = decision_element.css('::attr(href)').get()
                    if decision_data_link:
                        decision_data_link = decision_data_link.strip()
                        self.logger.info(f"✅ Found decision data link: {decision_data_link}")

                        # Extract case number from URL pattern /pages/search/%case_number%/false
                        url_match = re.search(r'/pages/search/([^/]+)/false', decision_data_link)
                        if url_match:
                            case_number_from_url = url_match.group(1)
                            self.logger.info(f"✅ Extracted case number from URL: {case_number_from_url}")

                    # Get the title from h4 inside the link
                    title_element = decision_element.css('div.ng-star-inserted h4.ng-star-inserted::text').get()
                    if title_element:
                        title = title_element.strip()
                        self.logger.info(f"✅ Found title: {title}")

                # Fallback selectors if the main structure is not found
                if not title:
                    title_selectors = ['h2::text', 'h3::text', 'h4::text', '.titulo::text', '.ementa::text', '.title::text']
                    for selector in title_selectors:
                        title = item.css(selector).get()
                        if title:
                            title = title.strip()
                            self.logger.debug(f"Found title with fallback selector {selector}: {title[:50]}...")
                            break

                # Create initial item data
                item_data = {
                    'title': title or f"Item {i+1}",
                    'case_number': case_number_from_url,
                    'source_url': response.url,
                    'scraped_at': datetime.now().isoformat(),
                    'item_index': i+1,
                    'query': query  # Store the query used
                }

                # If we have a decision data link, follow it to get detailed content
                if decision_data_link:
                    detail_url = response.urljoin(decision_data_link)
                    self.logger.info(f"Following detail URL for item {i+1}: {detail_url}")

                    yield scrapy.Request(
                        url=detail_url,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_methods': [
                                PageMethod('wait_for_load_state', 'networkidle'),
                                PageMethod('wait_for_function', '''
                                    () => {
                                        return document.readyState === 'complete' &&
                                               (document.querySelector('#decisaoTexto') ||
                                                document.querySelector('.header-icons') ||
                                                document.querySelector('.mat-icon') !== null);
                                    }
                                ''', timeout=30000),
                            ],
                            'item_data': item_data,
                        },
                        callback=self.parse_decision_detail,
                        errback=self.handle_error
                    )
                else:
                    self.logger.warning(f"❌ Item {i+1}: No decision data link found, skipping detailed extraction")
                    # Still yield a basic item
                    item_data['content'] = f"STF Item {i+1} - No decision data link available"
                    item_data['extraction_method'] = 'no-detail-link'
                    yield self.yield_item_with_limit_check(item_data)

        finally:
            if page:
                await page.close()

    async def parse_decision_detail(self, response):
        """Parse the detailed decision page to extract full content"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})

        try:
            self.logger.info(f"Parsing decision detail page: {response.url}")

            # Wait for page to be fully loaded
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('#decisaoTexto') ||
                            document.querySelector('.header-icons') ||
                            document.querySelector('.mat-icon') !== null);
                }
            ''', timeout=15000)

            # Extract full content using the clipboard button
            clipboard_content = await page.evaluate('''
                (async () => {
                    // Look for the clipboard button in header-icons section
                    const headerIcons = document.querySelector('.header-icons.hide-in-print');
                    let clipboardBtn = null;
                    
                    if (headerIcons) {
                        // Try to find the clipboard icon by different methods
                        clipboardBtn = headerIcons.querySelector('mat-icon[mattooltip*="Copiar"]') ||
                                     headerIcons.querySelector('mat-icon:contains("file_copy")') ||
                                     headerIcons.querySelector('mat-icon.clipboard-result') ||
                                     Array.from(headerIcons.querySelectorAll('mat-icon')).find(icon => 
                                         icon.textContent.trim() === 'file_copy' || 
                                         icon.getAttribute('mattooltip')?.includes('Copiar')
                                     );
                    }
                    
                    if (!clipboardBtn) {
                        console.log('No clipboard button found');
                        return null;
                    }
                    
                    // Store original clipboard content
                    let originalClipboard = '';
                    try {
                        originalClipboard = await navigator.clipboard.readText();
                    } catch(e) {
                        console.log('Could not read original clipboard:', e);
                    }
                    
                    // Click the clipboard button
                    console.log('Clicking clipboard button...');
                    clipboardBtn.click();
                    
                    // Wait for clipboard to be populated
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    // Try to read the clipboard content
                    try {
                        const clipboardText = await navigator.clipboard.readText();
                        if (clipboardText && clipboardText !== originalClipboard) {
                            console.log('Successfully copied content to clipboard:', clipboardText.length, 'characters');
                            return {
                                content: clipboardText,
                                source: 'clipboard-detail-page'
                            };
                        }
                    } catch(e) {
                        console.log('Could not read clipboard after click:', e);
                    }
                    
                    return null;
                })();
            ''')

            # Extract specific sections from the page
            partes_elements = response.xpath('//h4[text()="Partes"]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()
            if not partes_elements:
                partes_elements = response.xpath('//h4[contains(text(), "Partes")]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()

            partes_text = ' '.join([p.strip() for p in partes_elements if p.strip()]) if partes_elements else None

            # Extract decision text from div with id="decisaoTexto"
            decision_element = response.css('#decisaoTexto ::text').getall()
            decision_text = ' '.join([d.strip() for d in decision_element if d.strip()]) if decision_element else None

            # Extract legislation
            legislacao_elements = response.xpath('//h4[text()="Legislação"]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()
            if not legislacao_elements:
                legislacao_elements = response.xpath('//h4[contains(text(), "Legislação")]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()

            legislacao_text = ' '.join([l.strip() for l in legislacao_elements if l.strip()]) if legislacao_elements else None

            # Update item data with extracted content
            if clipboard_content and clipboard_content.get('content'):
                full_content = clipboard_content['content']
                item_data['content'] = full_content
                item_data['content_length'] = len(full_content)
                item_data['extraction_method'] = 'clipboard-detail-page'
                self.logger.info(f"✅ Extracted {len(full_content)} characters from clipboard")
            else:
                # Fallback: try to extract content from visible elements
                fallback_content = response.css('main ::text, .content ::text, .decisao ::text').getall()
                fallback_text = ' '.join([c.strip() for c in fallback_content if c.strip()])[:5000]  # Limit to first 5000 chars
                item_data['content'] = fallback_text or "Content extraction failed"
                item_data['extraction_method'] = 'fallback-detail-page'
                self.logger.warning("❌ Clipboard extraction failed, using fallback content")

            # Add the new extracted fields
            item_data['partes'] = partes_text
            item_data['decision'] = decision_text
            item_data['legislacao'] = legislacao_text
            item_data['detail_url'] = response.url

            # Log what we extracted
            self.logger.info(f"Extracted details - Partes: {'✅' if partes_text else '❌'}, Decision: {'✅' if decision_text else '❌'}, Legislacao: {'✅' if legislacao_text else '❌'}")

            yield self.yield_item_with_limit_check(item_data)

        except Exception as e:
            self.logger.error(f"Error parsing decision detail: {e}")
            # Still try to yield the basic item
            item_data['content'] = f"Error extracting detailed content: {str(e)}"
            item_data['extraction_method'] = 'error'
            yield self.yield_item_with_limit_check(item_data)

        finally:
            if page:
                await page.close()

    def create_item(self, item_data):
        """Create a legal document item"""
        item = JurisprudenciaItem()

        # Map data to item fields
        item['theme'] = 'stf_jurisprudencia'
        item['title'] = item_data.get('title', f"STF Item {item_data.get('item_index', 'Unknown')}")
        item['case_number'] = item_data.get('case_number', '')
        item['content'] = item_data.get('content', '')
        item['url'] = item_data.get('detail_url', '') or item_data.get('source_url', '')
        item['tribunal'] = 'STF'
        item['legal_area'] = 'Jurisprudência'

        # Extract classe processual unificada from the search URL
        item['classe_processual_unificada'] = get_classe_processual_from_url(item_data.get('source_url', ''))

        # Extract fields from content
        content = item_data.get('content', '')
        if content:
            item['relator'] = extract_relator_from_content(content)
            item['publication_date'] = extract_publication_date_from_content(content)
            item['decision_date'] = extract_decision_date_from_content(content)

            # If partes wasn't extracted from page elements, try to extract from content
            if not item_data.get('partes'):
                item['partes'] = extract_partes_from_content(content)

        # Add new detailed fields
        item['partes'] = item_data.get('partes', '') or item.get('partes', '')
        item['decision'] = item_data.get('decision', '')
        item['legislacao'] = item_data.get('legislacao', '')

        # Add RTF-related fields
        item['numero_unico'] = item_data.get('numero_unico', '')
        item['rtf_url'] = item_data.get('rtf_url', '')
        item['rtf_file_path'] = item_data.get('rtf_file_path', '')

        # Increment the items counter
        self.items_extracted += 1

        if self.dev_mode:
            self.logger.info(f"✅ DEV MODE: Created item {self.items_extracted}/{self.max_items}: {item.get('title', 'No title')} - Query: {item_data.get('query', 'Unknown')}")
        else:
            self.logger.info(f"✅ PROD MODE: Created item {self.items_extracted}: {item.get('title', 'No title')} - Query: {item_data.get('query', 'Unknown')}")

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
