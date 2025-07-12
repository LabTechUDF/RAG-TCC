"""
Main entry point for the Brazilian Legal Content Scraper.
Orchestrates theme-based scraping and provides CLI interface.
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

from utils.helpers import (
    setup_logging, get_theme_list, print_scraping_summary
)

# Import theme scrapers
from themes.direito_penal.scraper import run_scraper as run_direito_penal
from themes.jurisprudencia.scraper import run_scraper as run_jurisprudencia
from themes.sumulas_stf.scraper import run_scraper as run_sumulas_stf
from themes.normativas_stj.scraper import run_scraper as run_normativas_stj
from themes.tribunais_estaduais.scraper import run_scraper as run_tribunais_estaduais

logger = logging.getLogger(__name__)


class BrazilianLegalScraper:
    """Main scraper orchestrator for Brazilian legal content."""
    
    def __init__(self):
        self.theme_scrapers = {
            'direito_penal': run_direito_penal,
            'jurisprudencia': run_jurisprudencia,
            'sumulas_stf': run_sumulas_stf,
            'normativas_stj': run_normativas_stj,
            'tribunais_estaduais': run_tribunais_estaduais
        }
        
    async def run_theme(self, theme_name: str) -> Dict[str, Any]:
        """
        Run scraper for a specific theme.
        
        Args:
            theme_name: Name of the theme to scrape
            
        Returns:
            Dictionary with scraping results
        """
        if theme_name not in self.theme_scrapers:
            raise ValueError(f"Unknown theme: {theme_name}")
            
        logger.info(f"Starting scraper for theme: {theme_name}")
        
        try:
            scraper_func = self.theme_scrapers[theme_name]
            result = await scraper_func()
            
            logger.info(f"Completed scraping for theme: {theme_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error scraping theme {theme_name}: {e}")
            raise
            
    async def run_multiple_themes(self, theme_names: List[str]) -> Dict[str, Any]:
        """
        Run scrapers for multiple themes.
        
        Args:
            theme_names: List of theme names to scrape
            
        Returns:
            Dictionary with aggregated results
        """
        results = {}
        total_items = 0
        successful_themes = 0
        
        for theme_name in theme_names:
            try:
                logger.info(f"Starting theme: {theme_name}")
                result = await self.run_theme(theme_name)
                results[theme_name] = result
                
                if result.get('success', False):
                    successful_themes += 1
                    total_items += result.get('total_items', 0)
                    
            except Exception as e:
                logger.error(f"Failed to scrape theme {theme_name}: {e}")
                results[theme_name] = {
                    'success': False,
                    'error': str(e),
                    'total_items': 0
                }
                
        return {
            'themes_results': results,
            'summary': {
                'total_themes_attempted': len(theme_names),
                'successful_themes': successful_themes,
                'total_items_scraped': total_items,
                'success_rate': successful_themes / len(theme_names) if theme_names else 0
            }
        }
        
    async def run_all_themes(self) -> Dict[str, Any]:
        """
        Run scrapers for all available themes.
        
        Returns:
            Dictionary with aggregated results
        """
        all_themes = list(self.theme_scrapers.keys())
        logger.info(f"Running all themes: {all_themes}")
        
        return await self.run_multiple_themes(all_themes)


def create_cli_parser() -> argparse.ArgumentParser:
    """Create command line interface parser."""
    parser = argparse.ArgumentParser(
        description='Brazilian Legal Content Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --theme direito_penal
  python main.py --theme jurisprudencia sumulas_stf
  python main.py --all
  python main.py --list-themes
        """
    )
    
    parser.add_argument(
        '--theme', '-t',
        nargs='+',
        help='Theme(s) to scrape'
    )
    
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Run all available themes'
    )
    
    parser.add_argument(
        '--list-themes', '-l',
        action='store_true',
        help='List available themes'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scraped without actually scraping'
    )
    
    return parser


def print_welcome_message():
    """Print welcome message."""
    print("\n" + "="*70)
    print("🇧🇷 BRAZILIAN LEGAL CONTENT SCRAPER")
    print("="*70)
    print("Modular web scraper for Brazilian legal documents")
    print("Supports: STF, STJ, State Courts, Criminal Law, Jurisprudence")
    print("Configured for Portuguese locale and Brazilian websites")
    print("="*70 + "\n")


def print_theme_list():
    """Print available themes."""
    themes = get_theme_list()
    
    print("\n📁 AVAILABLE THEMES:")
    print("-" * 30)
    
    if not themes:
        print("No themes found. Please check the themes directory.")
        return
        
    theme_descriptions = {
        'direito_penal': 'Brazilian Criminal Law content and decisions',
        'jurisprudencia': 'Court decisions and case law from various courts',
        'sumulas_stf': 'Supreme Court (STF) binding and non-binding precedents',
        'normativas_stj': 'Superior Court of Justice (STJ) normative acts',
        'tribunais_estaduais': 'State courts decisions and jurisprudence'
    }
    
    for theme in themes:
        description = theme_descriptions.get(theme, 'No description available')
        print(f"  • {theme:<20} - {description}")
    
    print(f"\nTotal: {len(themes)} themes available\n")


async def main():
    """Main function."""
    parser = create_cli_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Print welcome message
    print_welcome_message()
    
    # Handle list themes
    if args.list_themes:
        print_theme_list()
        return
        
    # Validate arguments
    if not args.theme and not args.all:
        print("❌ Error: Please specify --theme, --all, or --list-themes")
        parser.print_help()
        sys.exit(1)
        
    # Handle dry run
    if args.dry_run:
        if args.all:
            themes = list(BrazilianLegalScraper().theme_scrapers.keys())
        else:
            themes = args.theme
            
        print("🔍 DRY RUN - Would scrape the following themes:")
        for theme in themes:
            print(f"  • {theme}")
        print(f"\nTotal themes: {len(themes)}")
        return
        
    # Initialize scraper
    scraper = BrazilianLegalScraper()
    
    try:
        start_time = datetime.now()
        
        # Run scraping
        if args.all:
            print("🚀 Starting scraping for ALL themes...")
            results = await scraper.run_all_themes()
        else:
            themes = args.theme
            print(f"🚀 Starting scraping for themes: {', '.join(themes)}")
            results = await scraper.run_multiple_themes(themes)
            
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Print results summary
        print("\n" + "="*70)
        print("📊 SCRAPING COMPLETED")
        print("="*70)
        
        if 'summary' in results:
            summary = results['summary']
            print(f"Total Themes Attempted: {summary['total_themes_attempted']}")
            print(f"Successful Themes: {summary['successful_themes']}")
            print(f"Total Items Scraped: {summary['total_items_scraped']}")
            print(f"Success Rate: {summary['success_rate']:.1%}")
            print(f"Total Duration: {duration}")
            
            # Print individual theme results
            if 'themes_results' in results:
                print(f"\n📋 THEME RESULTS:")
                print("-" * 50)
                
                for theme_name, theme_result in results['themes_results'].items():
                    status = "✅" if theme_result.get('success', False) else "❌"
                    items = theme_result.get('total_items', 0)
                    print(f"{status} {theme_name:<20} - {items} items")
                    
                    if not theme_result.get('success', False) and 'error' in theme_result:
                        print(f"    Error: {theme_result['error']}")
        
        print("="*70)
        print("✅ All scraping tasks completed!")
        print("📁 Check the 'scraper/data/' directory for scraped content")
        print("📄 Check the 'scraper/logs/' directory for detailed logs")
        print("="*70 + "\n")
        
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 