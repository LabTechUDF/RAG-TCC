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
# REQUEST FINGERPRINTING IMPLEMENTATION
# ========================================
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# ========================================
# POLITENESS AND DELAYS
# ========================================

# Obey robots.txt rules (disabled for legal research)
ROBOTSTXT_OBEY = False

# Configure delays and concurrency for STJ portal
DOWNLOAD_DELAY = 2  # 2 seconds between requests to be respectful
RANDOMIZE_DOWNLOAD_DELAY = 0.5  # Add randomization

# Enable concurrent requests
CONCURRENT_REQUESTS = 2  # Conservative concurrency for government sites
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# ========================================
# USER AGENT AND HEADERS
# ========================================

# Identifiable user agent for STJ scraping
USER_AGENT = 'RAG-TCC/stj_scraper (Academic Research; Contact: tcc@udf.edu.br)'

# Default request headers for Brazilian legal sites
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

# Retry failed requests for government sites
RETRY_TIMES = 5
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403, 404]
RETRY_PRIORITY_ADJUST = -1

# ========================================
# PIPELINE CONFIGURATION
# ========================================

# Configure pipelines for STJ dataset processing
ITEM_PIPELINES = {
    'stj_scraper.pipelines.ValidationPipeline': 300,
    'stj_scraper.pipelines.DateNormalizationPipeline': 350,
    'stj_scraper.pipelines.DuplicatesPipeline': 400,
    'stj_scraper.pipelines.STJJsonLinesPipeline': 500,
    'stj_scraper.pipelines.StatisticsPipeline': 800,
}

# ========================================
# AUTOTHROTTLE CONFIGURATION
# ========================================

# Enable AutoThrottle for adaptive delays
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2  # Start with 2 second delay
AUTOTHROTTLE_MAX_DELAY = 15  # Allow up to 15 seconds delay if needed
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5  # Target 1.5 concurrent requests
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
LOG_FILE = 'logs/app.log'

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)

# ========================================
# CUSTOM SETTINGS
# ========================================

# Data output directory
DATA_DIR = 'data'
Path(DATA_DIR).mkdir(exist_ok=True)

# Temp queue directory
TEMP_QUEUE_DIR = 'temp_queue'
Path(TEMP_QUEUE_DIR).mkdir(exist_ok=True)

# Download timeout for large files (zips)
DOWNLOAD_TIMEOUT = 180  # 3 minutes for zip downloads

# ========================================
# TELNET CONSOLE
# ========================================

# Telnet Console (for debugging)
TELNETCONSOLE_ENABLED = False