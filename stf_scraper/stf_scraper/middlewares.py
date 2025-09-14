# STF Scraper Middlewares - Simplified for queue-based processing

from scrapy import signals
from itemadapter import ItemAdapter


class STFSpiderMiddleware:
    """Basic spider middleware for STF scrapers"""
    
    def spider_opened(self, spider):
        spider.logger.info(f"STF Spider opened: {spider.name}")


class STFDownloaderMiddleware:
    """Basic downloader middleware for STF scrapers"""
    
    def spider_opened(self, spider):
        spider.logger.info(f"STF Downloader middleware initialized for: {spider.name}")
