# TRF 4ª Região Scraper Middlewares - Simplified for queue-based processing

from scrapy import signals
from itemadapter import ItemAdapter


class TRF4SpiderMiddleware:
    """Basic spider middleware for TRF 4ª Região scrapers"""
    
    def spider_opened(self, spider):
        spider.logger.info(f"TRF 4ª Região Spider opened: {spider.name}")


class TRF4DownloaderMiddleware:
    """Basic downloader middleware for TRF 4ª Região scrapers"""
    
    def spider_opened(self, spider):
        spider.logger.info(f"TRF 4ª Região Downloader middleware initialized for: {spider.name}")
