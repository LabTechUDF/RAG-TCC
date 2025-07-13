"""
Direito Penal scraper for Brazilian criminal law content.
Scrapes decisions, legislation, and jurisprudence related to criminal law.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from playwright.async_api import Page

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.browser import BrazilianBrowser
from utils.parser import BrazilianLegalParser
from utils.helpers import (
    load_theme_config, save_data_async, validate_scraped_data,
    create_scraping_report, save_scraping_report, normalize_url
)

logger = logging.getLogger(__name__)


class DireitoPenalScraper:
    """Scraper for Brazilian criminal law content."""
    
    def __init__(self):
        self.theme_name = "direito_penal"
        self.config = load_theme_config(self.theme_name)
        self.scraped_data: List[Dict[str, Any]] = []
        
    async def run_scraper(self) -> Dict[str, Any]:
        """
        Main method to run the criminal law scraper.
        
        Returns:
            Dictionary with scraping results and metrics
        """
        start_time = datetime.now()
        logger.info(f"Starting {self.config['name']} scraper")
        
        try:
            async with BrazilianBrowser() as browser:
                page = await browser.new_page()
                
                # Navigate to start URL with fallback
                success = await self._navigate_to_start_page(browser, page)
                if not success:
                    raise Exception("Failed to navigate to any start URL")
                
                # Perform the scraping
                await self._scrape_content(page)
                
                # Process pagination if configured
                if self.config['pagination']['type'] != 'none':
                    await self._handle_pagination(page)
                
                await page.close()
                
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            
        finally:
            end_time = datetime.now()
            await self._finalize_scraping(start_time, end_time)
            
        return await self._get_results()
        
    async def _navigate_to_start_page(self, browser: BrazilianBrowser, page: Page) -> bool:
        """Navigate to the start page with fallback URLs."""
        urls_to_try = [self.config['start_url']] + self.config.get('fallback_urls', [])
        
        for url in urls_to_try:
            if await browser.navigate_with_retry(page, url):
                logger.info(f"Successfully navigated to {url}")
                
                # Wait for page to load
                await page.wait_for_timeout(self.config['delays']['page_load'])
                
                # Check if we can find content containers
                container_selector = self.config['selectors']['container']
                if await browser.wait_for_content(page, container_selector, timeout=10000):
                    return True
                    
        return False
        
    async def _scrape_content(self, page: Page) -> None:
        """Scrape content from the current page."""
        try:
            # Get page content
            html_content = await page.content()
            parser = BrazilianLegalParser(html_content)
            
            # Extract items using configured selectors
            items = await self._extract_items(page, parser)
            
            logger.info(f"Extracted {len(items)} items from current page")
            self.scraped_data.extend(items)
            
        except Exception as e:
            logger.error(f"Error scraping content: {e}")
            
    async def _extract_items(self, page: Page, parser: BrazilianLegalParser) -> List[Dict[str, Any]]:
        """Extract individual items from the page."""
        items = []
        selectors = self.config['selectors']
        
        # Find all item elements
        item_elements = parser.soup.select(selectors['item'])
        
        for element in item_elements:
            try:
                # Extract standard legal document info
                item_data = parser.extract_legal_document_info(element)
                
                # Add theme-specific fields
                item_data.update({
                    'theme': self.theme_name,
                    'scraped_at': datetime.now().isoformat(),
                    'source_url': page.url
                })
                
                # Normalize URLs
                if item_data.get('link'):
                    item_data['link'] = normalize_url(item_data['link'], page.url)
                if item_data.get('pdf_link'):
                    item_data['pdf_link'] = normalize_url(item_data['pdf_link'], page.url)
                
                # Apply criminal law specific filtering
                if self._is_criminal_law_relevant(item_data):
                    items.append(item_data)
                    
            except Exception as e:
                logger.warning(f"Error extracting item: {e}")
                continue
                
        return items
        
    def _is_criminal_law_relevant(self, item_data: Dict[str, Any]) -> bool:
        """Check if the item is relevant to criminal law."""
        if not item_data.get('title') and not item_data.get('summary'):
            return False
            
        # Check for criminal law keywords
        criminal_keywords = self.config['filters']['search_terms']
        content_to_check = (
            (item_data.get('title', '') + ' ' + 
             item_data.get('summary', '') + ' ' +
             item_data.get('type', '')).lower()
        )
        
        return any(keyword.lower() in content_to_check for keyword in criminal_keywords)
        
    async def _handle_pagination(self, page: Page) -> None:
        """Handle pagination to scrape multiple pages."""
        max_pages = self.config['pagination']['max_pages']
        current_page = 1
        
        while current_page < max_pages:
            try:
                # Look for pagination element
                pagination_selector = self.config['pagination']['selector']
                next_button = page.locator(pagination_selector).first
                
                if not await next_button.is_visible():
                    logger.info("No more pages to scrape")
                    break
                    
                logger.info(f"Navigating to page {current_page + 1}")
                
                # Click next page
                await next_button.click()
                await page.wait_for_timeout(self.config['delays']['between_requests'])
                
                # Scrape content from new page
                await self._scrape_content(page)
                
                current_page += 1
                
            except Exception as e:
                logger.warning(f"Error handling pagination: {e}")
                break
                
    async def _finalize_scraping(self, start_time: datetime, end_time: datetime) -> None:
        """Finalize scraping and save data."""
        if self.scraped_data:
            # Save scraped data
            await save_data_async(
                self.scraped_data, 
                self.theme_name, 
                'direito_penal_data',
                self.config['output']['format']
            )
            
            # Validate data quality
            metrics = validate_scraped_data(
                self.scraped_data, 
                self.config['output']['fields'][:3]  # Check key fields
            )
            
            # Create and save report
            report = create_scraping_report(self.theme_name, start_time, end_time, metrics)
            await save_scraping_report(report, self.theme_name)
            
            logger.info(f"Scraping completed. {len(self.scraped_data)} items collected")
        else:
            logger.warning("No data was scraped")
            
    async def _get_results(self) -> Dict[str, Any]:
        """Get scraping results summary."""
        return {
            'theme': self.theme_name,
            'total_items': len(self.scraped_data),
            'success': len(self.scraped_data) > 0,
            'data_sample': self.scraped_data[:3] if self.scraped_data else []
        }


async def run_scraper() -> Dict[str, Any]:
    """
    Entry point for running the criminal law scraper.
    
    Returns:
        Dictionary with scraping results
    """
    scraper = DireitoPenalScraper()
    return await scraper.run_scraper()


async def parse_page(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content for criminal law data.
    
    Args:
        html_content: HTML content to parse
        
    Returns:
        List of parsed data dictionaries
    """
    parser = BrazilianLegalParser(html_content)
    config = load_theme_config("direito_penal")
    selectors = config['selectors']
    
    items = []
    item_elements = parser.soup.select(selectors['item'])
    
    for element in item_elements:
        item_data = parser.extract_legal_document_info(element)
        item_data.update({
            'theme': 'direito_penal',
            'parsed_at': datetime.now().isoformat()
        })
        items.append(item_data)
        
    return items


async def save_data(data: List[Dict[str, Any]], filename: str = None) -> None:
    """
    Save criminal law data to file.
    
    Args:
        data: List of data dictionaries to save
        filename: Custom filename (optional)
    """
    filename = filename or 'direito_penal_data'
    await save_data_async(data, "direito_penal", filename, 'json') 