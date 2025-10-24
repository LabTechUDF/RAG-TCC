#!/usr/bin/env python3
"""
Programmatic runner for the TRF4 spider using CrawlerProcess so project settings
from `trf4_scraper.settings` are applied (including scrapy-playwright handlers).

Usage:
  PYTHONPATH=. python3 run_trf4_process.py --query "texto" [--show-browser]
"""

import argparse
import sys
from scrapy.crawler import CrawlerProcess


def load_settings_module():
    import trf4_scraper.settings as mod
    settings = {k: v for k, v in mod.__dict__.items() if k.isupper()}
    return settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--show-browser', action='store_true')
    args = parser.parse_args()

    settings = load_settings_module()
    if args.show_browser:
        # Ensure Playwright runs headful
        settings['PLAYWRIGHT_LAUNCH_OPTIONS'] = {
            'headless': False,
            'args': ['--no-sandbox', '--disable-dev-shm-usage']
        }

    process = CrawlerProcess(settings=settings)

    from trf4_scraper.spiders.trf4_jurisprudencia import Trf4JurisprudenciaSpider

    process.crawl(Trf4JurisprudenciaSpider, query=args.query)
    process.start()


if __name__ == '__main__':
    main()
