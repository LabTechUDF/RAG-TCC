"""
Utility modules for the Brazilian Legal Content Scraper.

Modules:
- browser: Playwright browser management with Brazilian locale
- parser: BeautifulSoup parsing for Brazilian legal content  
- helpers: Helper functions for logging, data validation, and file operations
"""

from .browser import BrazilianBrowser
from .parser import BrazilianLegalParser
from .helpers import (
    setup_logging,
    load_theme_config,
    save_data_async,
    validate_scraped_data,
    create_scraping_report,
    normalize_url,
    get_theme_list
)

__all__ = [
    "BrazilianBrowser",
    "BrazilianLegalParser", 
    "setup_logging",
    "load_theme_config",
    "save_data_async",
    "validate_scraped_data",
    "create_scraping_report",
    "normalize_url",
    "get_theme_list"
] 