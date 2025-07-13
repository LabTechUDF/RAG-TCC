# Scrapy settings for legal_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os
from pathlib import Path

BOT_NAME = 'legal_scraper'

SPIDER_MODULES = ['legal_scraper.spiders']
NEWSPIDER_MODULE = 'legal_scraper.spiders'

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
    'headless': True,
    'locale': 'pt-BR',
    'timezone_id': 'America/Sao_Paulo',
    'args': [
        '--lang=pt-BR',
        '--accept-lang=pt-BR,pt;q=0.9,en;q=0.8',
        '--disable-blink-features=AutomationControlled',
        '--disable-web-security',
        '--ignore-certificate-errors',
        '--no-sandbox',
        '--disable-dev-shm-usage',
    ]
}

# Playwright timeouts and optimization
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 seconds
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 4
PLAYWRIGHT_MAX_CONTEXTS = 8

# Browser contexts for different legal sites
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport": {"width": 1280, "height": 800},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
    "stf": {
        "viewport": {"width": 1280, "height": 800},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
}

# Abort requests for non-essential resources to speed up scraping
PLAYWRIGHT_ABORT_REQUEST = lambda request: request.resource_type in ["image", "stylesheet", "font", "media"]

# ========================================
# BRAZILIAN LEGAL SITES POLITENESS
# ========================================

# Obey robots.txt rules for Brazilian legal sites
ROBOTSTXT_OBEY = True

# Configure a delay for requests (be respectful to legal sites)
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = 0.5

# Limit concurrent requests to avoid overwhelming legal sites
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# ========================================
# USER AGENT AND HEADERS
# ========================================

# User agent for Brazilian legal content scraping
USER_AGENT = 'legal_scraper (+https://exemplo.com.br/bot)'

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
    'legal_scraper.middlewares.LegalScraperSpiderMiddleware': 543,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'legal_scraper.middlewares.LegalScraperDownloaderMiddleware': 543,
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

# Configure item pipelines
ITEM_PIPELINES = {
    'legal_scraper.pipelines.ValidationPipeline': 300,
    'legal_scraper.pipelines.DuplicatesPipeline': 400,
    'legal_scraper.pipelines.BrazilianDatePipeline': 500,
    'legal_scraper.pipelines.JsonWriterPipeline': 600,
    'legal_scraper.pipelines.StatisticsPipeline': 700,
}

# ========================================
# AUTOTHROTTLE CONFIGURATION
# ========================================

# Enable AutoThrottle for adaptive delays
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
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
