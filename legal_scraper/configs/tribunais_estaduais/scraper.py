"""
Tribunais Estaduais scraper for Brazilian state courts.
Scrapes decisions and jurisprudence from multiple state courts (TJSP, TJRJ, TJMG, etc.).
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


class TribunaisEstaduaisScraper:
    """Scraper for Brazilian state courts decisions."""
    
    def __init__(self):
        self.theme_name = "tribunais_estaduais"
        self.config = load_theme_config(self.theme_name)
        self.scraped_data: List[Dict[str, Any]] = []
        
    async def run_scraper(self) -> Dict[str, Any]:
        """
        Main method to run the state courts scraper.
        
        Returns:
            Dictionary with scraping results and metrics
        """
        start_time = datetime.now()
        logger.info(f"Starting {self.config['name']} scraper")
        
        try:
            async with BrazilianBrowser() as browser:
                # Scrape multiple state courts
                await self._scrape_multiple_courts(browser)
                
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            
        finally:
            end_time = datetime.now()
            await self._finalize_scraping(start_time, end_time)
            
        return await self._get_results()
        
    async def _scrape_multiple_courts(self, browser: BrazilianBrowser) -> None:
        """Scrape multiple state courts."""
        target_courts = self.config.get('target_courts', {})
        
        # If specific courts are configured, scrape them
        if target_courts:
            for court_name, court_config in target_courts.items():
                try:
                    logger.info(f"Scraping {court_name}")
                    await self._scrape_specific_court(browser, court_name, court_config)
                except Exception as e:
                    logger.error(f"Error scraping {court_name}: {e}")
        else:
            # Fallback to general scraping
            page = await browser.new_page()
            success = await self._navigate_to_start_page(browser, page)
            if success:
                await self._scrape_content(page)
            await page.close()
            
    async def _scrape_specific_court(self, browser: BrazilianBrowser, 
                                   court_name: str, court_config: Dict[str, Any]) -> None:
        """Scrape a specific state court."""
        page = await browser.new_page()
        
        try:
            # Navigate to court-specific URL
            if await browser.navigate_with_retry(page, court_config['url']):
                logger.info(f"Successfully navigated to {court_name}")
                
                # Wait for page to load
                await page.wait_for_timeout(self.config['delays']['page_load'])
                
                # Scrape content using court-specific selectors
                await self._scrape_court_content(page, court_name, court_config)
                
        except Exception as e:
            logger.error(f"Error scraping {court_name}: {e}")
        finally:
            await page.close()
            
    async def _navigate_to_start_page(self, browser: BrazilianBrowser, page: Page) -> bool:
        """Navigate to the start page with fallback URLs."""
        urls_to_try = [self.config['start_url']] + self.config.get('fallback_urls', [])
        
        for url in urls_to_try:
            if await browser.navigate_with_retry(page, url):
                logger.info(f"Successfully navigated to {url}")
                await page.wait_for_timeout(self.config['delays']['page_load'])
                return True
                
        return False
        
    async def _scrape_content(self, page: Page) -> None:
        """Scrape content from the current page using general selectors."""
        try:
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Get page content
            html_content = await page.content()
            parser = BrazilianLegalParser(html_content)
            
            # Extract items using general selectors
            items = await self._extract_general_items(page, parser)
            
            logger.info(f"Extracted {len(items)} items from current page")
            self.scraped_data.extend(items)
            
        except Exception as e:
            logger.error(f"Error scraping content: {e}")
            
    async def _scrape_court_content(self, page: Page, court_name: str, 
                                  court_config: Dict[str, Any]) -> None:
        """Scrape content from a specific court using its configuration."""
        try:
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Get page content
            html_content = await page.content()
            parser = BrazilianLegalParser(html_content)
            
            # Extract items using court-specific selectors
            items = await self._extract_court_items(page, parser, court_name, court_config)
            
            logger.info(f"Extracted {len(items)} items from {court_name}")
            self.scraped_data.extend(items)
            
        except Exception as e:
            logger.error(f"Error scraping {court_name} content: {e}")
            
    async def _extract_general_items(self, page: Page, parser: BrazilianLegalParser) -> List[Dict[str, Any]]:
        """Extract items using general selectors."""
        items = []
        selectors = self.config['selectors']
        
        # Find all item elements
        item_elements = parser.soup.select(selectors.get('item', '.item-resultado'))
        
        for element in item_elements:
            try:
                # Extract jurisprudence information
                item_data = parser.extract_jurisprudencia(element)
                
                # Add theme-specific fields
                item_data.update({
                    'theme': self.theme_name,
                    'court_type': 'State Court',
                    'scraped_at': datetime.now().isoformat(),
                    'source_url': page.url
                })
                
                # Normalize URLs
                if item_data.get('link'):
                    item_data['link'] = normalize_url(item_data['link'], page.url)
                if item_data.get('pdf_link'):
                    item_data['pdf_link'] = normalize_url(item_data['pdf_link'], page.url)
                
                # Apply filtering
                if self._is_valid_state_court_item(item_data):
                    items.append(item_data)
                    
            except Exception as e:
                logger.warning(f"Error extracting general item: {e}")
                continue
                
        return items
        
    async def _extract_court_items(self, page: Page, parser: BrazilianLegalParser,
                                 court_name: str, court_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract items using court-specific selectors."""
        items = []
        selectors = court_config.get('selectors', {})
        
        # Find all item elements using court-specific selector
        item_selector = selectors.get('item', '.item-resultado')
        item_elements = parser.soup.select(item_selector)
        
        for element in item_elements:
            try:
                # Extract using court-specific selectors
                item_data = {
                    'title': self._extract_text_by_selector(element, selectors.get('title')),
                    'date': self._extract_text_by_selector(element, selectors.get('date')),
                    'case_number': self._extract_text_by_selector(element, selectors.get('case_number')),
                    'relator': self._extract_text_by_selector(element, selectors.get('relator')),
                    'court': court_name,
                    'link': self._extract_link(element),
                    'pdf_link': self._extract_pdf_link(element)
                }
                
                # Add theme-specific fields
                item_data.update({
                    'theme': self.theme_name,
                    'court_type': 'State Court',
                    'specific_court': court_name,
                    'scraped_at': datetime.now().isoformat(),
                    'source_url': page.url
                })
                
                # Normalize URLs
                if item_data.get('link'):
                    item_data['link'] = normalize_url(item_data['link'], page.url)
                if item_data.get('pdf_link'):
                    item_data['pdf_link'] = normalize_url(item_data['pdf_link'], page.url)
                
                # Apply filtering
                if self._is_valid_state_court_item(item_data):
                    items.append(item_data)
                    
            except Exception as e:
                logger.warning(f"Error extracting {court_name} item: {e}")
                continue
                
        return items
        
    def _extract_text_by_selector(self, element, selector: Optional[str]) -> Optional[str]:
        """Extract text using a specific selector."""
        if not selector:
            return None
            
        found = element.select_one(selector)
        if found:
            return found.get_text().strip()
        return None
        
    def _extract_link(self, element) -> Optional[str]:
        """Extract main link from element."""
        link = element.find('a', href=True)
        if link:
            return link['href']
        return None
        
    def _extract_pdf_link(self, element) -> Optional[str]:
        """Extract PDF link from element."""
        pdf_link = element.find('a', href=lambda x: x and '.pdf' in x.lower())
        if pdf_link:
            return pdf_link['href']
        return None
        
    def _is_valid_state_court_item(self, item_data: Dict[str, Any]) -> bool:
        """Check if the item is a valid state court decision."""
        # Must have title or case number
        if not item_data.get('title') and not item_data.get('case_number'):
            return False
            
        # Check for state court keywords
        search_terms = self.config['filters']['search_terms']
        content_to_check = (
            (item_data.get('title', '') + ' ' + 
             item_data.get('summary', '') + ' ' +
             item_data.get('type', '')).lower()
        )
        
        # Allow if it contains relevant legal terms or if no specific terms are required
        if not search_terms:
            return True
            
        return any(term.lower() in content_to_check for term in search_terms)
        
    async def _finalize_scraping(self, start_time: datetime, end_time: datetime) -> None:
        """Finalize scraping and save data."""
        if self.scraped_data:
            # Save scraped data
            await save_data_async(
                self.scraped_data, 
                self.theme_name, 
                'tribunais_estaduais_data',
                self.config['output']['format']
            )
            
            # Validate data quality
            metrics = validate_scraped_data(
                self.scraped_data, 
                self.config['output']['fields'][:3]
            )
            
            # Create and save report
            report = create_scraping_report(self.theme_name, start_time, end_time, metrics)
            await save_scraping_report(report, self.theme_name)
            
            logger.info(f"State Courts scraping completed. {len(self.scraped_data)} items collected")
        else:
            logger.warning("No state court data was scraped")
            
    async def _get_results(self) -> Dict[str, Any]:
        """Get scraping results summary."""
        # Count by court
        court_counts = {}
        for item in self.scraped_data:
            court = item.get('specific_court') or item.get('court', 'Unknown')
            court_counts[court] = court_counts.get(court, 0) + 1
            
        return {
            'theme': self.theme_name,
            'total_items': len(self.scraped_data),
            'success': len(self.scraped_data) > 0,
            'court_breakdown': court_counts,
            'data_sample': self.scraped_data[:3] if self.scraped_data else []
        }


async def run_scraper() -> Dict[str, Any]:
    """
    Entry point for running the state courts scraper.
    
    Returns:
        Dictionary with scraping results
    """
    scraper = TribunaisEstaduaisScraper()
    return await scraper.run_scraper()


async def parse_page(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content for state court data.
    
    Args:
        html_content: HTML content to parse
        
    Returns:
        List of parsed state court dictionaries
    """
    parser = BrazilianLegalParser(html_content)
    config = load_theme_config("tribunais_estaduais")
    selectors = config['selectors']
    
    items = []
    item_elements = parser.soup.select(selectors.get('item', '.item-resultado'))
    
    for element in item_elements:
        item_data = parser.extract_jurisprudencia(element)
        item_data.update({
            'theme': 'tribunais_estaduais',
            'parsed_at': datetime.now().isoformat()
        })
        items.append(item_data)
        
    return items


async def save_data(data: List[Dict[str, Any]], filename: str = None) -> None:
    """
    Save state court data to file.
    
    Args:
        data: List of data dictionaries to save
        filename: Custom filename (optional)
    """
    filename = filename or 'tribunais_estaduais_data'
    await save_data_async(data, "tribunais_estaduais", filename, 'json') 