# Scrapy settings for stj_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os
from pathlib import Path

BOT_NAME = 'stj_scraper'

SPIDER_MODULES = ['stj_scraper.spiders']
NEWSPIDER_MODULE = 'stj_scraper.spiders'

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
        '--exclude-switches=["enable-automation"]',
        '--disable-web-security',
        '--ignore-certificate-errors',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--allow-running-insecure-content',
        '--disable-features=VizDisplayCompositor',
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
}

# Playwright context options (applied to all contexts)
PLAYWRIGHT_DEFAULT_CONTEXT_OPTIONS = {
    "accept_downloads": True,
    "bypass_csp": True,
    "ignore_https_errors": True,
}

# Playwright timeouts and optimization for STJ SCON
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 seconds
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 1  # Use only 1 page per context
PLAYWRIGHT_MAX_CONTEXTS = 3  # Allow 3 contexts for 3 workers

# Browser contexts for STJ SCON (stealth mode)
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport": {"width": 1366, "height": 768},  # Common screen resolution
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "extra_http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        },
        "permissions": ["clipboard-read", "clipboard-write"],
        "accept_downloads": True,
        "java_script_enabled": True,
        "has_touch": False,
        "is_mobile": False,
    },
}

# Abort requests for non-essential resources to speed up scraping
PLAYWRIGHT_ABORT_REQUEST = lambda request: request.resource_type in ["image", "stylesheet", "font", "media"]

# ========================================
# BRAZILIAN LEGAL SITES POLITENESS
# ========================================

# Obey robots.txt rules for Brazilian legal sites (disabled for legal research)
ROBOTSTXT_OBEY = False

# Configure a delay for requests (be respectful to STJ SCON and avoid detection)
DOWNLOAD_DELAY = 5
RANDOMIZE_DOWNLOAD_DELAY = 1.0

# Enable concurrent requests for 3 workers (reduced for stealth)
CONCURRENT_REQUESTS = 1  # Temporarily reduced to avoid detection
CONCURRENT_REQUESTS_PER_DOMAIN = 1  # Single request per domain for stealth mode

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
    'stj_scraper.middlewares.STJSpiderMiddleware': 543,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'stj_scraper.middlewares.STJDownloaderMiddleware': 543,
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
    'stj_scraper.pipelines.ValidationPipeline': 300,
    'stj_scraper.pipelines.ArticleBasedJsonWriterPipeline': 400,
    'stj_scraper.pipelines.StatisticsPipeline': 800,
}

# ========================================
# AUTOTHROTTLE CONFIGURATION
# ========================================

# Enable AutoThrottle for adaptive delays
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 3.0
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