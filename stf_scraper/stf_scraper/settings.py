# ========================================
# PAGINAÇÃO COMPARTILHADA PARA PARALELISMO
# ========================================

from pathlib import Path
# Número de navegadores paralelos (workers)
PARALLEL_BROWSER_COUNT = 1
# Diretório para persistência do estado compartilhado
SHARED_STATE_DIR = str(Path(__file__).parent.parent / '.scrapy_state')
# Scrapy settings for stf_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os
from pathlib import Path

BOT_NAME = 'stf_scraper'

SPIDER_MODULES = ['stf_scraper.spiders']
NEWSPIDER_MODULE = 'stf_scraper.spiders'

# ========================================
# SCRAPY-PLAYWRIGHT INTEGRATION
# ========================================

# Replace default download handlers with Playwright
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Required for Playwright async operations
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# ========================================
# PLAYWRIGHT CONFIGURATION FOR BRAZILIAN LEGAL SITES
# ========================================

PLAYWRIGHT_BROWSER_TYPE = 'chromium'
PLAYWRIGHT_LAUNCH_OPTIONS = {
    'headless': True,  # Can be overridden by spider settings
    'args': [
        '--lang=pt-BR',
        '--accept-lang=pt-BR,pt;q=0.9,en;q=0.8',
        '--disable-blink-features=AutomationControlled',
        '--disable-web-security',
        '--ignore-certificate-errors',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--allow-running-insecure-content',  # Allow downloads from HTTP
        '--disable-features=VizDisplayCompositor',
    ]
}

# Playwright context options (applied to all contexts)
PLAYWRIGHT_DEFAULT_CONTEXT_OPTIONS = {
    "accept_downloads": True,  # Enable downloads globally
    "bypass_csp": True,        # Bypass content security policy
    "ignore_https_errors": True,  # Ignore HTTPS errors
}


# Playwright timeouts and optimization for parallel browsers
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 seconds for safer navigation with slow government sites
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 1  # 1 page per context for isolation
PARALLEL_BROWSER_COUNT = 3  # Number of parallel browsers for shared pagination
PLAYWRIGHT_MAX_CONTEXTS = PARALLEL_BROWSER_COUNT

# Browser contexts for different legal sites
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
        "permissions": ["clipboard-read", "clipboard-write"],
        "accept_downloads": True,  # Enable file downloads
    },
}

# Abort requests for non-essential resources to speed up scraping
PLAYWRIGHT_ABORT_REQUEST = lambda request: request.resource_type in ["image", "stylesheet", "font", "media"]

# ========================================
# BRAZILIAN LEGAL SITES POLITENESS
# ========================================

# Obey robots.txt rules for Brazilian legal sites (disabled for legal research)
ROBOTSTXT_OBEY = False

# Configure a delay for requests and enable native Scrapy parallelism
DOWNLOAD_DELAY = 1  # Safer delay to avoid IP blocking (2 seconds between requests)
RANDOMIZE_DOWNLOAD_DELAY = 0.3  # Add randomization to appear more human-like

# Enable concurrent requests using native Scrapy parallelism  
CONCURRENT_REQUESTS = 3  # 3 concurrent requests for 3 parallel groups
CONCURRENT_REQUESTS_PER_DOMAIN = 3  # 3 requests per domain for safer processing

# ========================================
# USER AGENT AND HEADERS
# ========================================

# User agent for Brazilian legal content scraping (realistic browser)
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Default request headers
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# ========================================
# MIDDLEWARE CONFIGURATION
# ========================================

# Enable or disable spider middlewares
SPIDER_MIDDLEWARES = {
    'stf_scraper.middlewares.STFSpiderMiddleware': 543,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'stf_scraper.middlewares.STFDownloaderMiddleware': 543,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 550,
}

# ========================================
# RETRY CONFIGURATION
# ========================================

# Retry failed requests for unstable legal sites
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]
RETRY_PRIORITY_ADJUST = -1

# ========================================
# PIPELINE CONFIGURATION
# ========================================

# Configure pipelines
ITEM_PIPELINES = {
    'stf_scraper.pipelines.ValidationPipeline': 300,
    'stf_scraper.pipelines.ArticleBasedJsonWriterPipeline': 400,
    'stf_scraper.pipelines.StatisticsPipeline': 800,
    # 'stf_scraper.pipelines.JsonWriterPipeline': 600,  # Disabled - using ArticleBasedJsonWriterPipeline instead
}

# ========================================
# AUTOTHROTTLE CONFIGURATION
# ========================================

# Enable AutoThrottle for adaptive delays with safer concurrency
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1 # Start with 2 second delay for safety
AUTOTHROTTLE_MAX_DELAY = 10  # Allow up to 10 seconds delay if needed
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0  # Target 3 concurrent requests
AUTOTHROTTLE_DEBUG = False

# ========================================
# CACHING AND STORAGE
# ========================================

# HTTP cache settings for development
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [429, 500, 502, 503, 504]

# ========================================
# LOGGING CONFIGURATION
# ========================================

# Logging level
LOG_LEVEL = 'INFO'

# Log file
LOG_FILE = 'logs/scrapy.log'

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)

# ========================================
# CUSTOM SETTINGS
# ========================================

# Data output directory
DATA_DIR = 'data'
Path(DATA_DIR).mkdir(exist_ok=True)

# Request fingerprinting implementation
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# Telnet Console (for debugging)
TELNETCONSOLE_ENABLED = False
