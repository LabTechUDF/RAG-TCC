"""
Browser utilities for web scraping Brazilian legal sites using Playwright.
Configured with Portuguese locale and proper headers for Brazilian websites.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


logger = logging.getLogger(__name__)


class BrazilianBrowser:
    """Browser manager for scraping Brazilian legal websites."""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize Brazilian browser configuration.
        
        Args:
            headless: Whether to run browser in headless mode
            timeout: Default timeout for page operations in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def start(self) -> None:
        """Start the browser with Brazilian locale configuration."""
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with Brazilian-specific configuration
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--lang=pt-BR'
                ]
            )
            
            # Create context with Brazilian locale and proper headers
            self.context = await self.browser.new_context(
                locale='pt-BR',
                timezone_id='America/Sao_Paulo',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive'
                }
            )
            
            logger.info("Browser started with Brazilian locale configuration")
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise
            
    async def new_page(self) -> Page:
        """
        Create a new page with Brazilian-specific settings.
        
        Returns:
            Configured page ready for Brazilian websites
        """
        if not self.context:
            raise RuntimeError("Browser context not initialized. Call start() first.")
            
        page = await self.context.new_page()
        
        # Set default timeout
        page.set_default_timeout(self.timeout)
        
        # Block unnecessary resources to speed up scraping
        await page.route('**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}', 
                        lambda route: route.abort())
        
        logger.debug("Created new page with Brazilian configuration")
        return page
        
    async def handle_consent_banner(self, page: Page) -> bool:
        """
        Handle LGPD consent banners commonly found on Brazilian websites.
        
        Args:
            page: The page to check for consent banners
            
        Returns:
            True if consent banner was handled, False otherwise
        """
        consent_selectors = [
            'button[id*="accept"]',
            'button[class*="accept"]',
            'button[id*="cookie"]',
            'button[class*="cookie"]',
            'button[id*="consent"]',
            'button[class*="consent"]',
            'a[href*="accept"]',
            '.cookie-accept',
            '.lgpd-accept',
            '#cookieAccept',
            '[data-accept="true"]'
        ]
        
        try:
            for selector in consent_selectors:
                element = page.locator(selector).first
                if await element.is_visible():
                    await element.click()
                    logger.info(f"Clicked consent banner: {selector}")
                    await page.wait_for_timeout(1000)  # Wait for banner to disappear
                    return True
                    
            logger.debug("No consent banner found")
            return False
            
        except Exception as e:
            logger.warning(f"Error handling consent banner: {e}")
            return False
            
    async def navigate_with_retry(self, page: Page, url: str, retries: int = 3) -> bool:
        """
        Navigate to URL with retry logic for Brazilian websites.
        
        Args:
            page: Page to navigate
            url: URL to navigate to
            retries: Number of retry attempts
            
        Returns:
            True if navigation successful, False otherwise
        """
        for attempt in range(retries):
            try:
                logger.info(f"Navigating to {url} (attempt {attempt + 1})")
                
                response = await page.goto(url, wait_until='domcontentloaded')
                
                if response and response.status < 400:
                    # Handle consent banners after page load
                    await self.handle_consent_banner(page)
                    logger.info(f"Successfully navigated to {url}")
                    return True
                else:
                    logger.warning(f"Bad response status: {response.status if response else 'None'}")
                    
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        logger.error(f"Failed to navigate to {url} after {retries} attempts")
        return False
        
    async def wait_for_content(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        """
        Wait for specific content to load on the page.
        
        Args:
            page: Page to wait on
            selector: CSS selector to wait for
            timeout: Timeout in milliseconds
            
        Returns:
            True if content loaded, False if timeout
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            logger.debug(f"Content loaded: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Content did not load in time: {selector} - {e}")
            return False
            
    async def close(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self.context:
                await self.context.close()
                
            if self.browser:
                await self.browser.close()
                
            if self.playwright:
                await self.playwright.stop()
                
            logger.info("Browser closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}") 