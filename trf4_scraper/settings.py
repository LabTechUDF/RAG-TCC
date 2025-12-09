# Minimal settings for trf4_scraper reusing Playwright setup from stf_scraper
from pathlib import Path

BOT_NAME = 'trf4_scraper'

SPIDER_MODULES = ['trf4_scraper.spiders']
NEWSPIDER_MODULE = 'trf4_scraper.spiders'

# Shared pagination/persistence directory
PARALLEL_BROWSER_COUNT = 3
SHARED_STATE_DIR = str(Path(__file__).parent.parent / '.scrapy_state')

# Playwright integration
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = 'chromium'
PLAYWRIGHT_LAUNCH_OPTIONS = {
    'headless': True,
    'args': ['--lang=pt-BR', '--no-sandbox', '--disable-dev-shm-usage'],
}

PLAYWRIGHT_DEFAULT_CONTEXT_OPTIONS = {
    "accept_downloads": True,
    "bypass_csp": True,
    "ignore_https_errors": True,
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = 1
CONCURRENT_REQUESTS = 3
CONCURRENT_REQUESTS_PER_DOMAIN = 3

LOG_LEVEL = 'INFO'
