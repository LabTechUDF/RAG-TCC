"""
TRF 4ª Região Jurisprudência Spider - Clean version with AJAX handling and logging
"""

import json
import scrapy
import logging
import time
from datetime import datetime
from pathlib import Path
from scrapy.exceptions import CloseSpider
from scrapy_playwright.page import PageMethod

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('trf4_scraper.log'),
        logging.StreamHandler()
    ]
)


class TRF4JurisprudenciaSpider(scrapy.Spider):
    """Spider for TRF 4ª Região jurisprudência with AJAX handling and logging"""
    
    name = 'trf4_jurisprudencia_clean'
    allowed_domains = ['jurisprudencia.trf4.jus.br']
    start_urls = ['https://jurisprudencia.trf4.jus.br/pesquisa/pesquisa.php']
    
    def __init__(self, query=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not query:
            raise CloseSpider('Query parameter is required')
            
        self.query = query
        self.results_per_page = 10  # Default value
        self.current_page = 1
        self.total_pages = None
        self.processed_items = 0
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Initializing spider with query: {query}")

    async def start_requests(self):
        """Start the scraping process"""
        self.logger.info(f"Starting TRF4 scraping process")
        
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                    ]
                }
            )

    async def parse(self, response):
        """Initial parsing and setup of the search page"""
        self.logger.info("Accessing initial search page")
        
        try:
            # Click on advanced search button
            await response.page.click('#btnPesquisaAvancada')
            self.logger.info("Opened advanced search options")
            
            # Wait for advanced search panel
            await response.page.wait_for_selector('#divPesquisaAvancada')
            
            # Click on document type selector
            await response.page.click('.filter-option-inner-inner')
            await response.page.click('div[data-original-index="1"]')  # Select "Decisão monocrática"
            self.logger.info("Selected document type: Decisão monocrática")
            
            # Input search query
            await response.page.fill('#txtPesquisa', self.query)
            self.logger.info(f"Entered search query: {self.query}")
            
            # Click search button
            await response.page.click('#btnConsultar_form_inicial')
            self.logger.info("Initiated search")
            
            # Wait for results
            await response.page.wait_for_selector('.resultado')
            
            yield scrapy.Request(
                url=response.url,
                callback=self.parse_results,
                dont_filter=True,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_timeout', 2000),
                    ]
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error in parse: {str(e)}")
            raise CloseSpider("Error in initial parsing")

    async def parse_results(self, response):
        """Parse search results and extract citations"""
        try:
            # Get total results info
            results_info = await response.page.text_content('.badge.badge-primary')
            if results_info:
                total_results = int(''.join(filter(str.isdigit, results_info)))
                self.total_pages = (total_results + self.results_per_page - 1) // self.results_per_page
                self.logger.info(f"Found {total_results} total results across {self.total_pages} pages")
            
            # Process each result on the current page
            results = response.css('.resultado')
            self.logger.info(f"Processing {len(results)} results on page {self.current_page}")
            
            for i, result in enumerate(results, 1):
                try:
                    # Click citation button for this result
                    await response.page.click(f'.resultado:nth-child({i}) .material-icons.icon-aligned.iconeComTexto.mr-1')
                    self.logger.info(f"Clicked citation button for result {i}")
                    
                    # Wait for citation content
                    await response.page.wait_for_selector('#divConteudoCitacao')
                    time.sleep(1)  # Small delay to ensure content is loaded
                    
                    # Click copy button
                    await response.page.click('#iconCopiarCitacao')
                    self.logger.info(f"Clicked copy button for result {i}")
                    
                    # Get clipboard content
                    clipboard_content = await response.page.evaluate('navigator.clipboard.readText()')
                    
                    if clipboard_content:
                        # Save citation to file
                        filename = f"citations/trf4_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.json"
                        os.makedirs('citations', exist_ok=True)
                        
                        with open(filename, 'w', encoding='utf-8') as f:
                            json.dump({
                                'query': self.query,
                                'page': self.current_page,
                                'result_number': i,
                                'citation': clipboard_content,
                                'scraped_at': datetime.now().isoformat()
                            }, f, ensure_ascii=False, indent=2)
                        
                        self.logger.info(f"Saved citation to {filename}")
                    else:
                        self.logger.warning(f"No citation content found for result {i}")
                        
                except Exception as e:
                    self.logger.error(f"Error processing result {i} on page {self.current_page}: {str(e)}")
            
            # Check if we should move to next page
            if self.current_page < self.total_pages:
                self.current_page += 1
                next_page_button = await response.page.query_selector('button.page-link[aria-label="Next"]')
                
                if next_page_button:
                    await next_page_button.click()
                    self.logger.info(f"Moving to page {self.current_page}")
                    
                    yield scrapy.Request(
                        url=response.url,
                        callback=self.parse_results,
                        dont_filter=True,
                        meta={
                            'playwright': True,
                            'playwright_page_methods': [
                                PageMethod('wait_for_timeout', 2000),
                            ]
                        }
                    )
                else:
                    self.logger.warning(f"Next page button not found on page {self.current_page}")
            else:
                self.logger.info("Finished processing all pages")
                
        except Exception as e:
            self.logger.error(f"Error in parse_results: {str(e)}")
            raise CloseSpider("Error processing results")