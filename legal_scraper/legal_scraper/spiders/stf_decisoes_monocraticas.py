"""
STF Decisões Monocráticas spider for Brazilian Supreme Court decisions
"""

import scrapy
import json
import re
from datetime import datetime
from pathlib import Path
from .base_spider import BrazilianLegalSpiderBase
from scrapy_playwright.page import PageMethod


class StfDecisoesMonocraticasSpider(BrazilianLegalSpiderBase):
    """Spider for scraping STF Decisões Monocráticas"""
    
    name = 'stf_decisoes_monocraticas'
    allowed_domains = ['jurisprudencia.stf.jus.br', 'portal.stf.jus.br']
    
    # Start with the specific search URL you found
    start_urls = [
        'https://jurisprudencia.stf.jus.br/pages/search?base=decisoes&pesquisa_inteiro_teor=false&sinonimo=true&plural=true&radicais=false&buscaExata=true&page=1&pageSize=250&queryString=%22estelionato%20previdenci%C3%A1rio%22%20%22(artigo%20ou%20art)%20171%20%C2%A73%22~3%20natureza&sort=_score&sortBy=desc'
    ]
    
    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'RETRY_TIMES': 3,
        'FEEDS': {
            'data/stf_decisoes/scraped_%(time)s.json': {'format': 'json'},
        }
    }
    
    def get_playwright_meta(self, extra_methods=None):
        """Get Playwright meta with STF-specific methods"""
        extra_methods = extra_methods or []
        
        # Add STF-specific page methods
        extra_methods.extend([
            # Wait for Angular/JavaScript to load the results
            PageMethod('wait_for_selector', 'div[id^="result-index-"]', timeout=30000),
            PageMethod('wait_for_timeout', 5000),  # Additional wait for content to stabilize
        ])
        
        return super().get_playwright_meta(extra_methods)
    
    async def parse_listing(self, response):
        """Parse STF jurisprudence listing page"""
        page = response.meta.get("playwright_page")
        
        try:
            self.logger.info(f"Parsing STF listing page: {response.url}")
            
            # Wait for results to load
            await page.wait_for_selector('div[id^="result-index-"]', timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Get all result items (they have IDs like result-index-0, result-index-1, etc.)
            result_items = await page.query_selector_all('div[id^="result-index-"]')
            self.logger.info(f"Found {len(result_items)} STF decision items")
            
            for i, item in enumerate(result_items):
                try:
                    # Extract clipboard content first
                    clipboard_id = f"clipboard-despacho"
                    clipboard_link = await item.query_selector(f'a[id^="{clipboard_id}"]')
                    
                    if clipboard_link:
                        # Click the clipboard link to get the content
                        clipboard_content = await self.extract_clipboard_content(page, clipboard_link)
                        
                        if clipboard_content:
                            # Extract the case number and other info from clipboard
                            decision_data = self.parse_clipboard_content(clipboard_content)
                            
                            # Get the "Acompanhamento processual" link
                            processo_link = await item.query_selector('a[href*="processos/listarProcessos.asp"]')
                            if processo_link:
                                processo_href = await processo_link.get_attribute('href')
                                
                                # Follow the processo link to get PDF download link
                                yield response.follow(
                                    processo_href,
                                    meta={
                                        **self.get_playwright_meta(),
                                        'decision_data': decision_data,
                                        'clipboard_content': clipboard_content
                                    },
                                    callback=self.parse_processo_detail,
                                    errback=self.handle_error
                                )
                            else:
                                # No processo link, save just the clipboard content
                                yield self.create_decision_item(decision_data, clipboard_content)
                                
                except Exception as e:
                    self.logger.warning(f"Error processing result item {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error parsing STF listing: {e}")
        finally:
            if page:
                await page.close()
    
    async def extract_clipboard_content(self, page, clipboard_link):
        """Extract content from clipboard by simulating click"""
        try:
            # Click the clipboard button to copy content
            await clipboard_link.click()
            await page.wait_for_timeout(1000)
            
            # Try to get clipboard content through page evaluation
            # This is a workaround since we can't access actual clipboard
            # We'll try to find the content in the DOM or extract it from the element
            
            # Look for any tooltip or popup that might contain the content
            content_elements = [
                '[mattooltip]',
                '.mat-tooltip',
                '.tooltip-content',
                '.clipboard-content'
            ]
            
            for selector in content_elements:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        content = await element.inner_text()
                        if content and len(content) > 10:
                            return content.strip()
                except:
                    continue
            
            # If we can't get clipboard content, try to extract from the item itself
            parent_item = await clipboard_link.evaluate('element => element.closest(\'div[id^="result-index-"]\').outerHTML')
            if parent_item:
                # Extract key information from the HTML
                return self.extract_info_from_html(parent_item)
                
            return None
            
        except Exception as e:
            self.logger.warning(f"Error extracting clipboard content: {e}")
            return None
    
    def extract_info_from_html(self, html_content):
        """Extract decision info from HTML when clipboard content is not available"""
        try:
            # This is a fallback method to extract basic info from the HTML
            # We'll look for common patterns in STF decision listings
            
            # Extract case number pattern (HC XXXXXX, etc.)
            case_pattern = r'(HC|RE|AI|MS|ADI|ADPF)\s*(\d+)'
            case_match = re.search(case_pattern, html_content)
            
            if case_match:
                case_type = case_match.group(1)
                case_number = case_match.group(2)
                return f"{case_type} {case_number}\nExtracted from HTML content"
            
            return "Content extracted from HTML (clipboard not available)"
            
        except Exception as e:
            self.logger.warning(f"Error extracting info from HTML: {e}")
            return None
    
    async def parse_processo_detail(self, response):
        """Parse the processo detail page to get PDF download link"""
        page = response.meta.get("playwright_page")
        decision_data = response.meta.get('decision_data', {})
        clipboard_content = response.meta.get('clipboard_content', '')
        
        try:
            self.logger.debug(f"Parsing processo detail: {response.url}")
            
            # Wait for the page to load
            await page.wait_for_load_state('domcontentloaded')
            await page.wait_for_timeout(3000)
            
            # Look for PDF download link
            pdf_selectors = [
                'a[href*="downloadPeca.asp"][href*=".pdf"]',
                'a[href*="download"][href*=".pdf"]',
                '.btn:has-text("Decisão monocrática")',
                'a:has-text("Decisão monocrática")'
            ]
            
            pdf_url = None
            for selector in pdf_selectors:
                try:
                    pdf_element = await page.query_selector(selector)
                    if pdf_element:
                        pdf_href = await pdf_element.get_attribute('href')
                        if pdf_href:
                            pdf_url = response.urljoin(pdf_href)
                            break
                except:
                    continue
            
            # Update decision data with PDF URL
            if pdf_url:
                decision_data['pdf_url'] = pdf_url
                decision_data['pdf_available'] = True
                
                # Download the PDF
                yield response.follow(
                    pdf_url,
                    meta={'decision_data': decision_data, 'clipboard_content': clipboard_content},
                    callback=self.download_pdf,
                    errback=self.handle_error
                )
            else:
                decision_data['pdf_available'] = False
                yield self.create_decision_item(decision_data, clipboard_content)
                
        except Exception as e:
            self.logger.error(f"Error parsing processo detail: {e}")
            decision_data['error'] = str(e)
            yield self.create_decision_item(decision_data, clipboard_content)
        finally:
            if page:
                await page.close()
    
    def download_pdf(self, response):
        """Download and save PDF file"""
        decision_data = response.meta.get('decision_data', {})
        clipboard_content = response.meta.get('clipboard_content', '')
        
        try:
            # Create data directory
            pdf_dir = Path('data/stf_decisoes/pdfs')
            pdf_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename from case number or use timestamp
            case_number = decision_data.get('case_number', 'unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{case_number}_{timestamp}.pdf"
            
            # Clean filename
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            
            # Save PDF
            pdf_path = pdf_dir / filename
            with open(pdf_path, 'wb') as f:
                f.write(response.body)
            
            decision_data['pdf_path'] = str(pdf_path)
            decision_data['pdf_filename'] = filename
            decision_data['pdf_size'] = len(response.body)
            decision_data['downloaded_at'] = datetime.now().isoformat()
            
            self.logger.info(f"Downloaded PDF: {filename} ({len(response.body)} bytes)")
            
        except Exception as e:
            self.logger.error(f"Error downloading PDF: {e}")
            decision_data['pdf_error'] = str(e)
        
        yield self.create_decision_item(decision_data, clipboard_content)
    
    def parse_clipboard_content(self, content):
        """Parse clipboard content to extract structured data"""
        if not content:
            return {}
        
        data = {}
        lines = content.strip().split('\n')
        
        try:
            # First line usually contains case number
            if lines:
                case_match = re.search(r'([A-Z]{1,4})\s*(\d+)', lines[0])
                if case_match:
                    data['case_type'] = case_match.group(1)
                    data['case_number'] = f"{case_match.group(1)} {case_match.group(2)}"
            
            # Look for Relator
            for line in lines:
                if 'Relator' in line:
                    data['relator'] = line.replace('Relator(a):', '').strip()
                elif 'Julgamento:' in line:
                    data['julgamento_date'] = line.replace('Julgamento:', '').strip()
                elif 'Publicação:' in line:
                    data['publicacao_date'] = line.replace('Publicação:', '').strip()
            
            # Extract decision text (usually after "Decisão" keyword)
            decision_start = content.find('Decisão')
            if decision_start != -1:
                data['decisao_text'] = content[decision_start:].strip()
            
        except Exception as e:
            self.logger.warning(f"Error parsing clipboard content: {e}")
        
        return data
    
    def create_decision_item(self, decision_data, clipboard_content):
        """Create a structured item from decision data"""
        
        item = {
            'theme': 'stf_decisoes_monocraticas',
            'source': 'STF - Decisões Monocráticas',
            'scraped_at': datetime.now().isoformat(),
            'clipboard_content': clipboard_content,
            'url': decision_data.get('pdf_url', ''),
            'pdf_path': decision_data.get('pdf_path', ''),
            'pdf_filename': decision_data.get('pdf_filename', ''),
            'case_number': decision_data.get('case_number', ''),
            'case_type': decision_data.get('case_type', ''),
            'relator': decision_data.get('relator', ''),
            'julgamento_date': decision_data.get('julgamento_date', ''),
            'publicacao_date': decision_data.get('publicacao_date', ''),
            'decisao_text': decision_data.get('decisao_text', ''),
            'pdf_available': decision_data.get('pdf_available', False),
            'pdf_size': decision_data.get('pdf_size', 0),
            'downloaded_at': decision_data.get('downloaded_at', ''),
            **decision_data  # Include any additional data
        }
        
        return item
    
    def save_clipboard_content(self, case_number, content):
        """This method is no longer needed - clipboard content goes in JSON"""
        pass
