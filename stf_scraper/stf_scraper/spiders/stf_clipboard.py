"""
STF Clipboard & PDF Spider - Focused on extracting clipboard content and PDFs from STF decisões
"""

import re
import json
import scrapy
from datetime import datetime
from pathlib import Path
from scrapy_playwright.page import PageMethod
from stf_scraper.items import LegalDocumentItem
# from pdb import set_trace


class StfClipboardSpider(scrapy.Spider):
    """Focused spider for STF clipboard content and PDF extraction"""

    name = 'stf_clipboard'
    allowed_domains = ['jurisprudencia.stf.jus.br']

    # Direct STF URL from config
    start_urls = [
        'https://jurisprudencia.stf.jus.br/pages/search?base=decisoes&pesquisa_inteiro_teor=false&sinonimo=true&plural=true&radicais=false&buscaExata=true&page=1&pageSize=250&queryString=%22estelionato%20previdenci%C3%A1rio%22%20%22(artigo%20ou%20art)%20171%20%C2%A73%22~3%20natureza&sort=_score&sortBy=desc'
    ]

    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 3,
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
                },
                callback=self.parse_stf_listing,
                errback=self.handle_error
            )

    async def parse_stf_listing(self, response):
        """Parse STF search results page"""
        page = response.meta.get("playwright_page")

        try:
            self.logger.info(f"Parsing STF listing: {response.url}")

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
                # set_trace()
                if result_items:
                    self.logger.info(f"Found {len(result_items)} items with selector: {selector}")
                    break

            if not result_items:
                # Check if there's a "no results" message or if we need to wait more
                no_results = response.css('.no-results, .sem-resultados, .empty-results').get()
                if no_results:
                    self.logger.warning("No results found - empty result set")
                else:
                    # Let's see what's actually on the page
                    page_content = await page.content()
                    self.logger.warning(f"No result items found. Page content length: {len(page_content)}")

                    # Try to find any clickable links that might be results
                    all_links = response.css('a[href]::attr(href)').getall()
                    self.logger.info(f"Found {len(all_links)} total links on page")

                    # Look for clipboard-like or processo-like links
                    clipboard_links = [link for link in all_links if 'clipboard' in link.lower()]
                    processo_links = [link for link in all_links if 'processo' in link.lower()]

                    self.logger.info(f"Found {len(clipboard_links)} clipboard-like links")
                    self.logger.info(f"Found {len(processo_links)} processo-like links")

                return

            # Process each result item
            for i, item in enumerate(result_items):
                self.logger.info(f"Processing item {i+1}/{len(result_items)}")

                # First, let's debug what elements we actually have in each item
                item_html = item.get()
                self.logger.debug(f"Item {i+1} HTML length: {len(item_html)}")
                
                # Log all links in this item for debugging
                all_item_links = item.css('a::attr(href)').getall()
                self.logger.info(f"Item {i+1} has {len(all_item_links)} links")
                
                # Extract clipboard button with multiple possible selectors
                clipboard_selectors = [
                    'a[id^="clipboard-despacho"]',
                    'a[id^="clipboard-"]',
                    'a[class*="clipboard"]',
                    'button[id^="clipboard-"]',
                    'button[class*="clipboard"]',
                    '[onclick*="clipboard"]',
                    '[title*="copiar"]',
                    '[title*="clipboard"]'
                ]

                clipboard_element = None
                clipboard_selector_used = None
                for selector in clipboard_selectors:
                    clipboard_element = item.css(selector).get()
                    if clipboard_element:
                        clipboard_selector_used = selector
                        self.logger.info(f"✅ Found clipboard element with selector: {selector}")
                        break
                    else:
                        self.logger.debug(f"No match for selector: {selector}")

                # Extract basic info regardless of clipboard button
                title_selectors = ['h2::text', 'h3::text', '.titulo::text', '.ementa::text', '.title::text']
                title = None
                for selector in title_selectors:
                    title = item.css(selector).get()
                    if title:
                        title = title.strip()
                        self.logger.debug(f"Found title with selector {selector}: {title[:50]}...")
                        break

                case_number_selectors = ['.numero-processo::text', '.processo::text', '.case-number::text', '[class*="numero"]::text']
                case_number = None
                for selector in case_number_selectors:
                    case_number = item.css(selector).get()
                    if case_number:
                        case_number = case_number.strip()
                        self.logger.debug(f"Found case number: {case_number}")
                        break

                # Extract processo detail link for PDF extraction later
                processo_selectors = [
                    'a[href*="processos/listarProcessos.asp"]::attr(href)',
                    'a[href*="processo"]::attr(href)',
                    'a[href*="detalhe"]::attr(href)'
                ]

                processo_link = None
                for selector in processo_selectors:
                    processo_link = item.css(selector).get()
                    if processo_link:
                        self.logger.debug(f"Found processo link: {processo_link}")
                        break

                # Create item data even if no clipboard button (for debugging)
                item_data = {
                    'title': title or f"Item {i+1}",
                    'case_number': case_number,
                    'processo_link': response.urljoin(processo_link) if processo_link else None,
                    'source_url': response.url,
                    'scraped_at': datetime.now().isoformat(),
                    'item_index': i+1,
                    'has_clipboard_button': bool(clipboard_element)
                }

                # If no clipboard button found, still try to extract some content and save the item
                if not clipboard_element:
                    self.logger.warning(f"❌ Item {i+1}: No clipboard button found, extracting available content")
                    
                    # Extract whatever content we can find
                    content_selectors = ['.ementa::text', '.resumo::text', '.abstract::text', '.texto::text']
                    content = None
                    for selector in content_selectors:
                        content = item.css(selector).get()
                        if content:
                            content = content.strip()
                            if len(content) > 20:
                                break
                    
                    item_data['clipboard_content'] = content or f"STF Item {i+1} - No content extracted from fallback selectors"
                    item_data['content_length'] = len(content) if content else 0
                    item_data['extraction_method'] = 'fallback-no-clipboard'
                    
                    # Yield the item even without clipboard
                    yield self.create_item(item_data)
                    continue

                # Now click the clipboard button and extract the content directly
                self.logger.info(f"Attempting to click clipboard button for item {i+1}")
                
                try:
                    # Click the clipboard button and capture the content
                    clipboard_content = await page.evaluate(f'''
                        (async () => {{
                            // Find the clipboard button in this specific result item
                            const resultItems = document.querySelectorAll('div[id^="result-index-"]');
                            const currentItem = resultItems[{i}];
                            
                            if (!currentItem) {{
                                console.log('Could not find result item {i}');
                                return null;
                            }}
                            
                            // Find clipboard button within this item
                            const clipboardSelectors = [
                                'a[id^="clipboard-despacho"]',
                                'a[id^="clipboard-"]', 
                                'a[class*="clipboard"]',
                                'button[id^="clipboard-"]',
                                '[onclick*="clipboard"]'
                            ];
                            
                            let clipboardBtn = null;
                            for (const selector of clipboardSelectors) {{
                                clipboardBtn = currentItem.querySelector(selector);
                                if (clipboardBtn) {{
                                    console.log('Found clipboard button with selector:', selector);
                                    break;
                                }}
                            }}
                            
                            if (!clipboardBtn) {{
                                console.log('No clipboard button found in item {i+1}');
                                return null;
                            }}
                            
                            // Store original clipboard content if any
                            let originalClipboard = '';
                            try {{
                                originalClipboard = await navigator.clipboard.readText();
                            }} catch(e) {{
                                console.log('Could not read original clipboard:', e);
                            }}
                            
                            // Click the clipboard button
                            console.log('Clicking clipboard button...');
                            clipboardBtn.click();
                            
                            // Wait a moment for clipboard to be populated
                            await new Promise(resolve => setTimeout(resolve, 1000));
                            
                            // Try to read the clipboard content
                            try {{
                                const clipboardText = await navigator.clipboard.readText();
                                if (clipboardText && clipboardText !== originalClipboard) {{
                                    console.log('Successfully copied content to clipboard:', clipboardText.length, 'characters');
                                    return {{
                                        content: clipboardText,
                                        source: 'clipboard-copy',
                                        button_selector: clipboardBtn.tagName.toLowerCase() + (clipboardBtn.id ? '#' + clipboardBtn.id : '')
                                    }};
                                }}
                            }} catch(e) {{
                                console.log('Could not read clipboard after click:', e);
                            }}
                            
                            // Fallback: try to extract content from nearby text elements
                            const nearbyText = currentItem.querySelector('.ementa, .decisao-texto, .inteiro-teor, pre');
                            if (nearbyText && nearbyText.innerText.length > 50) {{
                                console.log('Using nearby text as fallback:', nearbyText.innerText.length, 'characters');
                                return {{
                                    content: nearbyText.innerText.trim(),
                                    source: 'nearby-text-fallback'
                                }};
                            }}
                            
                            return null;
                        }})();
                    ''')
                    
                    item_data = {
                        'title': title or f"Item {i+1}",
                        'case_number': case_number,
                        'processo_link': response.urljoin(processo_link) if processo_link else None,
                        'source_url': response.url,
                        'scraped_at': datetime.now().isoformat(),
                        'item_index': i+1,
                    }
                    
                    if clipboard_content and clipboard_content.get('content'):
                        content_text = clipboard_content['content']
                        item_data['clipboard_content'] = content_text
                        item_data['content_length'] = len(content_text)
                        item_data['extraction_method'] = clipboard_content.get('source', 'unknown')
                        item_data['button_info'] = clipboard_content.get('button_selector', 'unknown')
                        self.logger.info(f"✅ Item {i+1}: Extracted {len(content_text)} characters via {clipboard_content.get('source')}")
                    else:
                        self.logger.warning(f"❌ Item {i+1}: No clipboard content extracted")
                        item_data['clipboard_content'] = f"STF Item {i+1} - No clipboard content available. Please check original source."
                        item_data['content_length'] = 0
                        item_data['extraction_method'] = 'failed'
                    
                    # Always yield the item - validation pipeline will handle quality filtering
                    yield self.create_item(item_data)
                    
                except Exception as e:
                    self.logger.error(f"Error processing clipboard for item {i+1}: {e}")
                    continue

        finally:
            if page:
                await page.close()

    async def extract_pdf_links(self, response):
        """Extract PDF download links from STF processo page"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})

        try:
            self.logger.info(f"Extracting PDF links: {response.url}")

            # Wait for the page to be fully loaded
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('a[href*="pdf"]') ||
                            document.querySelector('a[href*="downloadPeca"]') ||
                            document.querySelector('.no-pdfs') ||
                            document.links.length > 0);
                }
            ''', timeout=15000)

            # Extract PDF links with multiple strategies
            pdf_selectors = [
                'a[href$=".pdf"]::attr(href)',
                'a[title*="PDF"]::attr(href)',
                'a[title*="pdf"]::attr(href)',
                'a[title*="Pdf"]::attr(href)',
                'a[href*="pdf"]::attr(href)',
                'a[href*="PDF"]::attr(href)',
                'a[href*="downloadPeca.asp"]::attr(href)',
                'a[class*="pdf"]::attr(href)',
                'a[class*="PDF"]::attr(href)',
                'a[onclick*="pdf"]::attr(href)',
                'a[onclick*="PDF"]::attr(href)'
            ]

            pdf_links = []
            for selector in pdf_selectors:
                found_links = response.css(selector).getall()
                if found_links:
                    self.logger.debug(f"Found {len(found_links)} PDF links with selector: {selector}")
                    pdf_links.extend(found_links)

            # Remove duplicates and convert to absolute URLs
            pdf_links = list(set(pdf_links))  # Remove duplicates
            if pdf_links:
                absolute_pdf_links = [response.urljoin(link) for link in pdf_links]
                item_data['pdf_links'] = absolute_pdf_links
                item_data['pdf_count'] = len(absolute_pdf_links)
                self.logger.info(f"Found {len(absolute_pdf_links)} PDF links")
            else:
                self.logger.warning("No PDF links found")
                item_data['pdf_links'] = []
                item_data['pdf_count'] = 0

            # Extract additional metadata from processo page with flexible selectors
            relator_selectors = ['.relator::text', '.ministro::text', '.judge::text', '[class*="relator"]::text']
            for selector in relator_selectors:
                relator = response.css(selector).get()
                if relator:
                    item_data['relator'] = relator.strip()
                    break

            date_selectors = ['.data-julgamento::text', '.data-decisao::text', '.date::text', '[class*="data"]::text']
            for selector in date_selectors:
                decision_date = response.css(selector).get()
                if decision_date:
                    item_data['decision_date'] = decision_date.strip()
                    break

            yield self.create_item(item_data)

        except Exception as e:
            self.logger.error(f"Error extracting PDF links: {e}")
            # Still yield the item even if PDF extraction failed
            yield self.create_item(item_data)

        finally:
            if page:
                await page.close()

    def create_item(self, item_data):
        """Create a legal document item"""
        item = LegalDocumentItem()

        # Map data to item fields
        item['theme'] = 'stf_clipboard'
        item['title'] = item_data.get('title', f"STF Item {item_data.get('item_index', 'Unknown')}")
        item['case_number'] = item_data.get('case_number', '')
        item['content'] = item_data.get('clipboard_content', '')
        item['url'] = item_data.get('processo_link', '') or item_data.get('source_url', '')
        item['source_site'] = item_data.get('source_url', '')
        item['tribunal'] = 'STF'
        item['court_level'] = 'Supremo Tribunal Federal'
        item['document_type'] = 'Decisão'
        item['legal_area'] = 'Penal'  # Based on search query
        item['scraped_at'] = item_data.get('scraped_at')

        # Add STF-specific metadata
        if item_data.get('pdf_links'):
            item['keywords'] = item_data['pdf_links']  # Store PDF links in keywords field

        if item_data.get('relator'):
            item['judge_rapporteur'] = item_data['relator']

        if item_data.get('decision_date'):
            item['publication_date'] = item_data['decision_date']

        # Add content quality indicator
        content_length = item_data.get('content_length', 0)
        if content_length > 1000:
            item['content_quality'] = 90
        elif content_length > 500:
            item['content_quality'] = 70
        elif content_length > 100:
            item['content_quality'] = 50
        else:
            item['content_quality'] = 20

        self.logger.info(f"Created item: {item.get('title', 'No title')}")
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
