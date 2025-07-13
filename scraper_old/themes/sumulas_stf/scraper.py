"""
Súmulas STF scraper for Brazilian Supreme Court binding precedents.
Scrapes both binding (vinculante) and non-binding precedents from STF.
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


class SumulasSTFScraper:
    """Scraper for STF Súmulas (binding and non-binding precedents)."""
    
    def __init__(self):
        self.theme_name = "sumulas_stf"
        self.config = load_theme_config(self.theme_name)
        self.scraped_data: List[Dict[str, Any]] = []
        
    async def run_scraper(self) -> Dict[str, Any]:
        """
        Main method to run the STF Súmulas scraper.
        
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
                
                # Scrape Súmulas content
                await self._scrape_sumulas(page)
                
                # Try to get both binding and non-binding Súmulas
                await self._scrape_different_types(browser, page)
                
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
                await page.wait_for_timeout(self.config['delays']['page_load'])
                return True
                
        return False
        
    async def _scrape_sumulas(self, page: Page) -> None:
        """Scrape Súmulas content from the current page."""
        try:
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Get page content
            html_content = await page.content()
            parser = BrazilianLegalParser(html_content)
            
            # Extract Súmulas items
            items = await self._extract_sumula_items(page, parser)
            
            logger.info(f"Extracted {len(items)} Súmulas from current page")
            self.scraped_data.extend(items)
            
        except Exception as e:
            logger.error(f"Error scraping Súmulas: {e}")
            
    async def _extract_sumula_items(self, page: Page, parser: BrazilianLegalParser) -> List[Dict[str, Any]]:
        """Extract individual Súmula items from the page."""
        items = []
        selectors = self.config['selectors']
        
        # Try different approaches to find Súmulas
        # 1. Look for configured selectors
        item_elements = parser.soup.select(selectors.get('item', '.sumula-item'))
        
        # 2. If no items found, look for alternative patterns
        if not item_elements:
            alternative_selectors = [
                'tr',  # Table rows
                '.texto',  # Text blocks
                'p',  # Paragraphs
                'div[id*="sumula"]',  # Divs with sumula in ID
                'li'  # List items
            ]
            
            for alt_selector in alternative_selectors:
                item_elements = parser.soup.select(alt_selector)
                if item_elements:
                    logger.info(f"Found Súmulas using alternative selector: {alt_selector}")
                    break
        
        for element in item_elements:
            try:
                # Extract Súmula-specific information
                item_data = parser.extract_sumula(element)
                
                # Skip if no meaningful content
                if not item_data.get('numero') and not item_data.get('texto'):
                    continue
                
                # Add theme-specific fields
                item_data.update({
                    'theme': self.theme_name,
                    'scraped_at': datetime.now().isoformat(),
                    'source_url': page.url
                })
                
                # Normalize URLs
                if item_data.get('link'):
                    item_data['link'] = normalize_url(item_data['link'], page.url)
                
                # Apply Súmula filtering
                if self._is_valid_sumula(item_data):
                    items.append(item_data)
                    
            except Exception as e:
                logger.warning(f"Error extracting Súmula item: {e}")
                continue
                
        return items
        
    def _is_valid_sumula(self, item_data: Dict[str, Any]) -> bool:
        """Check if the item is a valid Súmula."""
        # Must have either number or text
        if not item_data.get('numero') and not item_data.get('texto'):
            return False
            
        # Check if text contains Súmula indicators
        text_content = (item_data.get('texto', '') + ' ' + str(item_data.get('numero', ''))).lower()
        
        # Filter out very short content
        if len(text_content.strip()) < 10:
            return False
            
        return True
        
    async def _scrape_different_types(self, browser: BrazilianBrowser, page: Page) -> None:
        """Attempt to scrape different types of Súmulas (binding vs non-binding)."""
        try:
            # Look for links to different Súmula types
            type_links = [
                'a[href*="vinculante"]',
                'a[href*="Vinculante"]',
                'a[href*="comum"]',
                'a[href*="ordinaria"]'
            ]
            
            for link_selector in type_links:
                link = page.locator(link_selector).first
                if await link.is_visible():
                    try:
                        await link.click()
                        await page.wait_for_timeout(3000)
                        await self._scrape_sumulas(page)
                        
                        # Go back to main page
                        await page.go_back()
                        await page.wait_for_timeout(2000)
                        
                    except Exception as e:
                        logger.warning(f"Error scraping {link_selector}: {e}")
                        
        except Exception as e:
            logger.warning(f"Error scraping different Súmula types: {e}")
            
    async def _finalize_scraping(self, start_time: datetime, end_time: datetime) -> None:
        """Finalize scraping and save data."""
        if self.scraped_data:
            # Remove duplicates based on número
            seen_numbers = set()
            unique_data = []
            for item in self.scraped_data:
                numero = item.get('numero')
                if numero and numero not in seen_numbers:
                    seen_numbers.add(numero)
                    unique_data.append(item)
                elif not numero:  # Items without number
                    unique_data.append(item)
            
            self.scraped_data = unique_data
            
            # Save scraped data
            await save_data_async(
                self.scraped_data, 
                self.theme_name, 
                'sumulas_stf_data',
                self.config['output']['format']
            )
            
            # Validate data quality
            metrics = validate_scraped_data(
                self.scraped_data, 
                ['numero', 'texto', 'tipo']
            )
            
            # Create and save report
            report = create_scraping_report(self.theme_name, start_time, end_time, metrics)
            await save_scraping_report(report, self.theme_name)
            
            logger.info(f"STF Súmulas scraping completed. {len(self.scraped_data)} items collected")
        else:
            logger.warning("No STF Súmulas data was scraped")
            
    async def _get_results(self) -> Dict[str, Any]:
        """Get scraping results summary."""
        # Count by type
        type_counts = {}
        for item in self.scraped_data:
            sumula_type = item.get('tipo', 'Unknown')
            type_counts[sumula_type] = type_counts.get(sumula_type, 0) + 1
            
        return {
            'theme': self.theme_name,
            'total_items': len(self.scraped_data),
            'success': len(self.scraped_data) > 0,
            'type_breakdown': type_counts,
            'data_sample': self.scraped_data[:3] if self.scraped_data else []
        }


async def run_scraper() -> Dict[str, Any]:
    """
    Entry point for running the STF Súmulas scraper.
    
    Returns:
        Dictionary with scraping results
    """
    scraper = SumulasSTFScraper()
    return await scraper.run_scraper()


async def parse_page(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content for STF Súmulas data.
    
    Args:
        html_content: HTML content to parse
        
    Returns:
        List of parsed Súmula dictionaries
    """
    parser = BrazilianLegalParser(html_content)
    config = load_theme_config("sumulas_stf")
    selectors = config['selectors']
    
    items = []
    item_elements = parser.soup.select(selectors.get('item', '.sumula-item'))
    
    for element in item_elements:
        item_data = parser.extract_sumula(element)
        item_data.update({
            'theme': 'sumulas_stf',
            'parsed_at': datetime.now().isoformat()
        })
        items.append(item_data)
        
    return items


async def save_data(data: List[Dict[str, Any]], filename: str = None) -> None:
    """
    Save STF Súmulas data to file.
    
    Args:
        data: List of data dictionaries to save
        filename: Custom filename (optional)
    """
    filename = filename or 'sumulas_stf_data'
    await save_data_async(data, "sumulas_stf", filename, 'json') 