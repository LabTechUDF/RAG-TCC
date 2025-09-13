#!/usr/bin/env python3
"""
Management script for Brazilian Legal Content Scrapers
"""

import argparse
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime


class STFScraperManager:
    """Manager for STF legal content scrapers"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.available_spiders = [
            'stf_jurisprudencia', 
            'simple_query_spider',
        ]
    
    def list_spiders(self):
        """List all available spiders"""
        print("📚 Available STF Legal Scrapers:")
        print("=" * 50)
        
        for spider in self.available_spiders:
            config_file = self.project_root / 'configs' / spider / 'config.json'
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    description = config.get('description', 'No description')
                    print(f"  🕷️  {spider:<20} - {description}")
                except Exception as e:
                    print(f"  🕷️  {spider:<20} - Error loading config: {e}")
            else:
                print(f"  🕷️  {spider:<20} - Config not found")
        print()
    
    def run_spider(self, spider_name, dry_run=False, max_pages=None, output_format='json', show_browser=False):
        """Run a specific spider"""
        if spider_name not in self.available_spiders:
            print(f"❌ Error: Spider '{spider_name}' not found.")
            print(f"Available spiders: {', '.join(self.available_spiders)}")
            return False
        
        print(f"🚀 Running {spider_name} spider...")
        if dry_run:
            print("🔍 DRY RUN MODE - No data will be saved")
        if show_browser:
            print("👀 BROWSER VISIBLE - You can watch the scraping process")
        
        # Build scrapy command
        cmd = ['poetry', 'run', 'scrapy', 'crawl', spider_name]
        
        # Add custom settings
        if dry_run:
            cmd.extend(['-s', 'ITEM_PIPELINES={}'])
        
        if max_pages:
            cmd.extend(['-s', f'CLOSESPIDER_PAGECOUNT={max_pages}'])
        
        # Control browser visibility
        if show_browser:
            cmd.extend(['-s', 'PLAYWRIGHT_LAUNCH_OPTIONS={"headless":false}'])
        
        # Set output format
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/{spider_name}/scraped_{timestamp}.{output_format}"
        
        if not dry_run:
            cmd.extend(['-o', output_file])
        
        # Add verbose logging
        cmd.extend(['-L', 'INFO'])
        
        try:
            # Change to project directory
            result = subprocess.run(cmd, cwd=self.project_root, check=True)
            
            if result.returncode == 0:
                print(f"✅ Successfully completed {spider_name} spider!")
                if not dry_run:
                    print(f"📄 Data saved to: {output_file}")
                return True
            else:
                print(f"❌ Spider {spider_name} failed with return code {result.returncode}")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Error running spider {spider_name}: {e}")
            return False
        except KeyboardInterrupt:
            print(f"\n⏹️  Spider {spider_name} interrupted by user")
            return False
    
    def run_all_spiders(self, dry_run=False, max_pages=None, show_browser=False):
        """Run all available spiders"""
        print("🚀 Running ALL Brazilian Legal Scrapers...")
        print("=" * 50)
        
        results = {}
        start_time = datetime.now()
        
        for spider in self.available_spiders:
            print(f"\n📋 Starting {spider}...")
            success = self.run_spider(spider, dry_run=dry_run, max_pages=max_pages, show_browser=show_browser)
            results[spider] = success
        
        # Print summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "=" * 50)
        print("📊 SCRAPING SUMMARY")
        print("=" * 50)
        
        successful = sum(results.values())
        total = len(results)
        
        print(f"⏱️  Total time: {duration}")
        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}/{total}")
        
        print("\nDetailed results:")
        for spider, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {spider}")
        
        return successful == total
    
    def show_stats(self):
        """Show statistics from recent scraping runs"""
        stats_file = self.project_root / 'data' / 'scraping_stats.json'
        
        if not stats_file.exists():
            print("📊 No statistics available. Run some scrapers first!")
            return
        
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
            
            print("📊 LATEST SCRAPING STATISTICS")
            print("=" * 50)
            print(f"Total items scraped: {stats.get('total_items', 0)}")
            print(f"Duration: {stats.get('duration', 0):.2f} seconds")
            print(f"Start time: {stats.get('start_time', 'Unknown')}")
            
            print("\nItems by theme:")
            for theme, count in stats.get('items_by_theme', {}).items():
                print(f"  📝 {theme}: {count}")
            
            print("\nQuality distribution:")
            quality_stats = stats.get('items_by_quality', {})
            print(f"  🌟 High quality: {quality_stats.get('high', 0)}")
            print(f"  ⭐ Medium quality: {quality_stats.get('medium', 0)}")
            print(f"  📋 Low quality: {quality_stats.get('low', 0)}")
            
        except Exception as e:
            print(f"❌ Error reading statistics: {e}")
    
    def clean_data(self):
        """Clean up old data files"""
        data_dir = self.project_root / 'data'
        if not data_dir.exists():
            print("🗂️  No data directory found.")
            return
        
        print("🧹 Cleaning up old data files...")
        
        # Count files before cleanup
        total_files = sum(1 for _ in data_dir.rglob('*.json*'))
        
        # Ask for confirmation
        response = input(f"Are you sure you want to delete {total_files} data files? (y/N): ")
        if response.lower() != 'y':
            print("❌ Cleanup cancelled.")
            return
        
        # Remove data files
        deleted_count = 0
        for file_path in data_dir.rglob('*.json*'):
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        
        print(f"✅ Deleted {deleted_count} files.")
    
    def check_config(self, spider_name=None):
        """Check configuration for spiders"""
        if spider_name:
            spiders_to_check = [spider_name] if spider_name in self.available_spiders else []
            if not spiders_to_check:
                print(f"❌ Spider '{spider_name}' not found.")
                return
        else:
            spiders_to_check = self.available_spiders
        
        print("🔧 CONFIGURATION CHECK")
        print("=" * 50)
        
        for spider in spiders_to_check:
            config_file = self.project_root / 'configs' / spider / 'config.json'
            print(f"\n📋 {spider}:")
            
            if not config_file.exists():
                print(f"  ❌ Config file not found: {config_file}")
                continue
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Check required fields
                required_fields = ['name', 'start_url', 'selectors']
                for field in required_fields:
                    if field in config:
                        print(f"  ✅ {field}: {config[field] if field != 'selectors' else 'configured'}")
                    else:
                        print(f"  ❌ Missing {field}")
                
                # Check URLs
                if 'start_url' in config:
                    print(f"  🌐 Start URL: {config['start_url']}")
                
                if 'fallback_urls' in config:
                    print(f"  🔗 Fallback URLs: {len(config['fallback_urls'])} configured")
                
            except Exception as e:
                print(f"  ❌ Error reading config: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='🇧🇷 Brazilian Legal Content Scraper Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                          # List all available spiders
  %(prog)s run jurisprudencia           # Run jurisprudencia spider
  %(prog)s run-all --dry-run            # Test all spiders without saving
  %(prog)s run direito_penal --max-pages 5  # Limit to 5 pages
  %(prog)s stats                        # Show scraping statistics
  %(prog)s check-config                 # Check all configurations
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all available spiders')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a specific spider')
    run_parser.add_argument('spider', choices=['jurisprudencia', 'stf_jurisprudencia', 'sumulas_stf', 'normativas_stj', 'direito_penal', 'tribunais_estaduais', 'simple_query_spider'])
    run_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    run_parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape')
    run_parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format')
    run_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Run all command
    run_all_parser = subparsers.add_parser('run-all', help='Run all spiders')
    run_all_parser.add_argument('--dry-run', action='store_true', help='Run without saving data')
    run_all_parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape per spider')
    run_all_parser.add_argument('--show-browser', action='store_true', help='Show browser window (disable headless mode)')
    
    # Stats command
    subparsers.add_parser('stats', help='Show scraping statistics')
    
    # Clean command
    subparsers.add_parser('clean', help='Clean up old data files')
    
    # Check config command
    check_parser = subparsers.add_parser('check-config', help='Check spider configurations')
    check_parser.add_argument('spider', nargs='?', help='Specific spider to check')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = STFScraperManager()
    
    try:
        if args.command == 'list':
            manager.list_spiders()
        
        elif args.command == 'run':
            manager.run_spider(
                args.spider, 
                dry_run=args.dry_run,
                max_pages=args.max_pages,
                output_format=args.format,
                show_browser=args.show_browser
            )
        
        elif args.command == 'run-all':
            manager.run_all_spiders(
                dry_run=args.dry_run,
                max_pages=args.max_pages,
                show_browser=args.show_browser
            )
        
        elif args.command == 'stats':
            manager.show_stats()
        
        elif args.command == 'clean':
            manager.clean_data()
        
        elif args.command == 'check-config':
            manager.check_config(args.spider)
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 