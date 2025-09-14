import scrapy
from scrapy_playwright.page import PageMethod
import json
import os
import re

class SimpleQuerySpider(scrapy.Spider):
    name = "simple_query_spider"
    allowed_domains = ["jurisprudencia.stf.jus.br"]
    start_urls = ["https://jurisprudencia.stf.jus.br/pages/search"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queries = []
        self.results = []
        self.output_file = "/home/workstation/git/RAG-TCC/stf_scraper/data/simple_query_spider/query_links.json"

    def start_requests(self):
        # Load queries from queries.txt
        with open("/home/workstation/git/RAG-TCC/stf_scraper/configs/queries.txt", "r") as f:
            self.queries = [line.strip() for line in f.readlines() if line.strip()]

        # Create single request to process all queries sequentially
        yield scrapy.Request(
            url=self.start_urls[0],
            meta={
                "playwright": True,
                "playwright_include_page": True,
            },
            callback=self.process_all_queries
        )

    async def process_all_queries(self, response):
        page = response.meta.get("playwright_page")
        if not page:
            self.logger.error("Playwright page not found in response meta.")
            return

        # Load existing results if file exists
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r") as f:
                    self.results = json.load(f)
                self.logger.info(f"Loaded {len(self.results)} existing results from {self.output_file}")
            except Exception as e:
                self.logger.warning(f"Could not load existing results: {e}")
                self.results = []

        # Configure "Decisões monocráticas" only once at the beginning
        try:
            await page.wait_for_timeout(2000)  # Wait for page to load
            
            # Try multiple selectors for "Decisões monocráticas"
            decision_selected = False
            
            # Check if already selected
            decision_element = await page.query_selector(".selected[aria-label='Decisões monocráticas']")
            if decision_element:
                decision_selected = True
                self.logger.info("'Decisões monocráticas' already selected")
            else:
                # Try different ways to select it
                selectors_to_try = [
                    "xpath=/html/body/app-root/app-home/main/search/div/div/div/div[1]/div[1]/mat-radio-group/mat-radio-button[2]/label/div[2]/div[1]/div/span[1]",
                    "mat-radio-button[value='decisoes'] label",
                    "mat-radio-button:nth-child(2) label",
                    "[aria-label='Decisões monocráticas']"
                ]
                
                for selector in selectors_to_try:
                    try:
                        if selector.startswith("xpath="):
                            await page.click(selector)
                        else:
                            await page.click(selector)
                        await page.wait_for_timeout(2000)
                        
                        # Check if it worked
                        decision_element = await page.query_selector(".selected[aria-label='Decisões monocráticas']")
                        if decision_element:
                            decision_selected = True
                            self.logger.info(f"Successfully selected 'Decisões monocráticas' using {selector}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Selector {selector} failed: {e}")
                        continue
            
            if not decision_selected:
                self.logger.warning("Could not select 'Decisões monocráticas' filter")
                
        except Exception as e:
            self.logger.warning(f"Could not configure 'Decisões monocráticas' filter: {e}")

        # Process each query sequentially
        for i, query in enumerate(self.queries):
            self.logger.info(f"Processing query {i+1}/{len(self.queries)}: '{query}'")
            
            try:
                # Clear the search field and input the new query
                await page.fill("#mat-input-0", "")  # Clear first
                await page.fill("#mat-input-0", query)

                # Click the search button
                await page.click("mat-icon[mattooltip='Pesquisar']")

                # Wait for the search to complete
                await page.wait_for_timeout(2000)

                # Get the current URL
                current_url = page.url
                
                # Replace 'acordaos' with 'decisoes' in the URL
                current_url = current_url.replace('base=acordaos', 'base=decisoes')
                
                # Extract article number from query using regex
                artigo_match = re.search(r'artigo\s+(\d+(?:-[A-Z])?)', query, re.IGNORECASE)
                artigo = artigo_match.group(1) if artigo_match else None
                
                # Append result with new structure
                result = {
                    "query": query,
                    "artigo": artigo,
                    "url": current_url
                }
                self.results.append(result)
                
                # Save results immediately (append mode)
                self.save_results()
                
                self.logger.info(f"Processed query '{query}' -> {current_url}")
                
                # Small delay between queries
                await page.wait_for_timeout(1000)
                
            except Exception as e:
                self.logger.error(f"Error processing query '{query}': {e}")
                continue

        # Close the page after processing all queries
        await page.close()

    def save_results(self):
        """Save results to JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            with open(self.output_file, "w") as f:
                json.dump(self.results, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")

    def closed(self, reason):
        # Final save and summary
        self.save_results()
        self.logger.info(f"Spider finished. Total results: {len(self.results)}")
        self.logger.info(f"Results saved to {self.output_file}")