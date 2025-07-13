"""
Normativas STJ scraper for Superior Court of Justice normative acts.
Scrapes regulations, instructions, and administrative acts from STJ.
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


class NormativasSTJScraper:
    """Scraper for STJ normative acts and regulations."""
    
    def __init__(self):
        self.theme_name = "normativas_stj"
        self.config = load_theme_config(self.theme_name)
        self.scraped_data: List[Dict[str, Any]] = []
        
    async def run_scraper(self) -> Dict[str, Any]:
        """
        Main method to run the STJ normative acts scraper.
        
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
                
                # Scrape normative acts
                await self._scrape_content(page)
                
                # Handle pagination
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
                await page.wait_for_timeout(self.config['delays']['page_load'])
                return True
                
        return False
        
    async def _scrape_content(self, page: Page) -> None:
        """Scrape normative acts content from the current page."""
        try:
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Get page content
            html_content = await page.content()
            parser = BrazilianLegalParser(html_content)
            
            # Extract normative acts items
            items = await self._extract_normative_items(page, parser)
            
            logger.info(f"Extracted {len(items)} normative items from current page")
            self.scraped_data.extend(items)
            
        except Exception as e:
            logger.error(f"Error scraping normative content: {e}")
            
    async def _extract_normative_items(self, page: Page, parser: BrazilianLegalParser) -> List[Dict[str, Any]]:
        """Extract individual normative act items from the page."""
        items = []
        selectors = self.config['selectors']
        
        # Find all item elements
        item_elements = parser.soup.select(selectors.get('item', '.item-publicacao'))
        
        # If no items found, try alternative selectors
        if not item_elements:
            alternative_selectors = [
                'tr',  # Table rows
                '.documento',  # Document items
                '.publicacao',  # Publication items
                'li',  # List items
                'article'  # Article elements
            ]
            
            for alt_selector in alternative_selectors:
                item_elements = parser.soup.select(alt_selector)
                if item_elements:
                    logger.info(f"Found normative acts using alternative selector: {alt_selector}")
                    break
        
        for element in item_elements:
            try:
                # Extract standard legal document info
                item_data = parser.extract_legal_document_info(element)
                
                # Extract normative-specific fields
                normative_data = {
                    'number': self._extract_document_number(element),
                    'type': self._extract_document_type(element),
                    'status': self._extract_status(element),
                }
                
                # Merge data
                item_data.update(normative_data)
                
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
                
                # Apply normative filtering
                if self._is_valid_normative(item_data):
                    items.append(item_data)
                    
            except Exception as e:
                logger.warning(f"Error extracting normative item: {e}")
                continue
                
        return items
        
    def _extract_document_number(self, element) -> Optional[str]:
        """Extract document number from element."""
        # Look for number patterns
        text = element.get_text()
        import re
        
        patterns = [
            r'(?:Resolução|Instrução)\s*(?:Normativa)?\s*n[º°]?\s*(\d+)',
            r'Portaria\s*n[º°]?\s*(\d+)',
            r'Ato\s*(?:Regulamentar)?\s*n[º°]?\s*(\d+)',
            r'n[º°]\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
        
    def _extract_document_type(self, element) -> Optional[str]:
        """Extract document type from element."""
        text = element.get_text().lower()
        
        type_keywords = {
            'resolução': 'Resolução',
            'instrução normativa': 'Instrução Normativa',
            'portaria': 'Portaria',
            'ato regulamentar': 'Ato Regulamentar',
            'regimento': 'Regimento Interno',
            'provimento': 'Provimento'
        }
        
        for keyword, doc_type in type_keywords.items():
            if keyword in text:
                return doc_type
                
        return None
        
    def _extract_status(self, element) -> Optional[str]:
        """Extract document status from element."""
        text = element.get_text().lower()
        
        if any(word in text for word in ['revogada', 'cancelada', 'superada']):
            return 'Revogada'
        elif any(word in text for word in ['vigente', 'válida', 'ativa']):
            return 'Vigente'
        else:
            return 'Desconhecido'
            
    def _is_valid_normative(self, item_data: Dict[str, Any]) -> bool:
        """Check if the item is a valid normative act."""
        # Must have title or type
        if not item_data.get('title') and not item_data.get('type'):
            return False
            
        # Check for normative keywords
        normative_keywords = self.config['filters']['document_types']
        content_to_check = (
            (item_data.get('title', '') + ' ' + 
             item_data.get('type', '') + ' ' +
             item_data.get('summary', '')).lower()
        )
        
        return any(keyword.lower() in content_to_check for keyword in normative_keywords)
        
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
                'normativas_stj_data',
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
            
            logger.info(f"STJ Normativas scraping completed. {len(self.scraped_data)} items collected")
        else:
            logger.warning("No STJ normative data was scraped")
            
    async def _get_results(self) -> Dict[str, Any]:
        """Get scraping results summary."""
        # Count by type
        type_counts = {}
        for item in self.scraped_data:
            doc_type = item.get('type', 'Unknown')
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            
        return {
            'theme': self.theme_name,
            'total_items': len(self.scraped_data),
            'success': len(self.scraped_data) > 0,
            'type_breakdown': type_counts,
            'data_sample': self.scraped_data[:3] if self.scraped_data else []
        }


async def run_scraper() -> Dict[str, Any]:
    """
    Entry point for running the STJ normative acts scraper.
    
    Returns:
        Dictionary with scraping results
    """
    scraper = NormativasSTJScraper()
    return await scraper.run_scraper()


async def parse_page(html_content: str) -> List[Dict[str, Any]]:
    """
    Parse HTML content for STJ normative data.
    
    Args:
        html_content: HTML content to parse
        
    Returns:
        List of parsed normative dictionaries
    """
    parser = BrazilianLegalParser(html_content)
    config = load_theme_config("normativas_stj")
    selectors = config['selectors']
    
    items = []
    item_elements = parser.soup.select(selectors.get('item', '.item-publicacao'))
    
    for element in item_elements:
        item_data = parser.extract_legal_document_info(element)
        item_data.update({
            'theme': 'normativas_stj',
            'parsed_at': datetime.now().isoformat()
        })
        items.append(item_data)
        
    return items


async def save_data(data: List[Dict[str, Any]], filename: str = None) -> None:
    """
    Save STJ normative data to file.
    
    Args:
        data: List of data dictionaries to save
        filename: Custom filename (optional)
    """
    filename = filename or 'normativas_stj_data'
    await save_data_async(data, "normativas_stj", filename, 'json') 