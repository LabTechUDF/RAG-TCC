# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from scrapy.exceptions import NotConfigured
import logging


class STJSpiderMiddleware:
    """Spider middleware for STJ dataset scraping"""

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool("STJ_SPIDER_MIDDLEWARE_ENABLED", True):
            raise NotConfigured("STJ Spider Middleware is disabled")
        
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        """Called for each response that goes through the spider middleware"""
        return None

    def process_spider_output(self, response, result, spider):
        """Called with the results returned from the Spider"""
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        """Called when a spider or process_spider_input() method raises an exception"""
        logging.getLogger(__name__).error(f"Spider exception in {response.url}: {exception}")

    def spider_opened(self, spider):
        """Called when spider is opened"""
        logging.getLogger(__name__).info(f"STJ Spider opened: {spider.name}")


class STJDownloaderMiddleware:
    """Downloader middleware for STJ dataset scraping"""

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool("STJ_DOWNLOADER_MIDDLEWARE_ENABLED", True):
            raise NotConfigured("STJ Downloader Middleware is disabled")
        
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        """Called for each request that goes through the downloader middleware"""
        
        # Add custom headers for STJ requests
        if 'dadosabertos.web.stj.jus.br' in request.url:
            request.headers.setdefault('User-Agent', spider.settings.get('USER_AGENT'))
            request.headers.setdefault('Accept-Language', 'pt-BR,pt;q=0.9,en;q=0.8')
        
        return None

    def process_response(self, request, response, spider):
        """Called with the response returned from the downloader"""
        
        # Log successful responses for monitoring
        if response.status == 200:
            logging.getLogger(__name__).debug(f"Successful response from {request.url}")
        elif response.status >= 400:
            logging.getLogger(__name__).warning(f"HTTP {response.status} from {request.url}")
        
        return response

    def process_exception(self, request, exception, spider):
        """Called when a download handler or a process_request() raises an exception"""
        logging.getLogger(__name__).error(f"Download exception for {request.url}: {exception}")

    def spider_opened(self, spider):
        """Called when spider is opened"""
        logging.getLogger(__name__).info(f"STJ Downloader middleware opened for: {spider.name}")