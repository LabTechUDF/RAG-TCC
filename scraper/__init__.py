"""
Brazilian Legal Content Scraper

A modular web scraping framework for Brazilian legal documents using 
Playwright and BeautifulSoup with Portuguese locale support.

Themes:
- direito_penal: Criminal law decisions and legislation
- jurisprudencia: Court decisions and case law  
- sumulas_stf: Supreme Court binding precedents
- normativas_stj: Superior Court normative acts
- tribunais_estaduais: State court decisions

Author: Brazilian Legal Content Scraper Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Brazilian Legal Content Scraper Team"

from .main import BrazilianLegalScraper

__all__ = ["BrazilianLegalScraper"] 