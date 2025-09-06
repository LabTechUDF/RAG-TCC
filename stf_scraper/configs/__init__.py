"""
Theme modules for the Brazilian Legal Content Scraper.

Each theme represents a category of Brazilian legal documents:

- direito_penal: Criminal law decisions, legislation, and jurisprudence
- jurisprudencia: General court decisions and case law from various courts
- sumulas_stf: Supreme Court (STF) binding and non-binding precedents
- normativas_stj: Superior Court of Justice (STJ) normative acts and regulations
- tribunais_estaduais: State court decisions and jurisprudence (TJSP, TJRJ, etc.)

Each theme contains:
- scraper.py: Main scraper implementation
- config.json: Configuration with URLs, selectors, and parsing rules
"""

# Import theme scrapers
from .direito_penal.scraper import run_scraper as run_direito_penal
from .jurisprudencia.scraper import run_scraper as run_jurisprudencia  
from .sumulas_stf.scraper import run_scraper as run_sumulas_stf
from .normativas_stj.scraper import run_scraper as run_normativas_stj
from .tribunais_estaduais.scraper import run_scraper as run_tribunais_estaduais

__all__ = [
    "run_direito_penal",
    "run_jurisprudencia", 
    "run_sumulas_stf",
    "run_normativas_stj",
    "run_tribunais_estaduais"
] 