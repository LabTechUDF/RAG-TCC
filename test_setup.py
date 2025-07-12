#!/usr/bin/env python3
"""
Test script to verify the Brazilian Legal Content Scraper setup.
Run this script to check if all components are properly configured.
"""

import sys
import asyncio
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        # Add scraper to Python path
        import sys
        from pathlib import Path
        scraper_path = Path(__file__).parent / "scraper"
        sys.path.insert(0, str(scraper_path))
        
        # Test core imports
        from utils.browser import BrazilianBrowser
        from utils.parser import BrazilianLegalParser
        from utils.helpers import setup_logging, get_theme_list
        print("✅ Core utilities imported successfully")
        
        # Test theme imports
        from themes.direito_penal.scraper import run_scraper
        from themes.jurisprudencia.scraper import run_scraper
        from themes.sumulas_stf.scraper import run_scraper
        print("✅ Theme scrapers imported successfully")
        
        # Test main scraper
        from main import BrazilianLegalScraper
        print("✅ Main scraper imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_dependencies():
    """Test if required dependencies are installed."""
    print("\n🔍 Testing dependencies...")
    
    required_packages = [
        ('playwright', 'playwright'),
        ('beautifulsoup4', 'bs4'), 
        ('aiofiles', 'aiofiles'),
        ('lxml', 'lxml')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name.replace('-', '_'))
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} - Not installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    return True


def test_directory_structure():
    """Test if directory structure is correct."""
    print("\n🔍 Testing directory structure...")
    
    required_dirs = [
        "scraper",
        "scraper/utils",
        "scraper/themes",
        "scraper/themes/direito_penal",
        "scraper/themes/jurisprudencia", 
        "scraper/themes/sumulas_stf",
        "scraper/themes/normativas_stj",
        "scraper/themes/tribunais_estaduais",
        "scraper/data",
        "scraper/logs"
    ]
    
    missing_dirs = []
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - Missing")
            missing_dirs.append(dir_path)
    
    return len(missing_dirs) == 0


def test_config_files():
    """Test if configuration files exist."""
    print("\n🔍 Testing configuration files...")
    
    config_files = [
        "scraper/themes/direito_penal/config.json",
        "scraper/themes/jurisprudencia/config.json",
        "scraper/themes/sumulas_stf/config.json", 
        "scraper/themes/normativas_stj/config.json",
        "scraper/themes/tribunais_estaduais/config.json"
    ]
    
    missing_configs = []
    
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ {config_file}")
        else:
            print(f"❌ {config_file} - Missing")
            missing_configs.append(config_file)
    
    return len(missing_configs) == 0


async def test_browser_setup():
    """Test if browser setup works."""
    print("\n🔍 Testing browser setup...")
    
    try:
        import sys
        from pathlib import Path
        scraper_path = Path(__file__).parent / "scraper"
        sys.path.insert(0, str(scraper_path))
        
        from utils.browser import BrazilianBrowser
        
        # Try to initialize browser (but don't navigate)
        browser = BrazilianBrowser()
        print("✅ BrazilianBrowser initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Browser setup failed: {e}")
        print("💡 Try: python3 -m playwright install chromium")
        return False


def test_parser():
    """Test if parser works with sample HTML."""
    print("\n🔍 Testing parser...")
    
    try:
        import sys
        from pathlib import Path
        scraper_path = Path(__file__).parent / "scraper"
        sys.path.insert(0, str(scraper_path))
        
        from utils.parser import BrazilianLegalParser
        
        # Test with sample HTML
        sample_html = """
        <div class="item">
            <h3>Sample Legal Decision</h3>
            <span class="date">15 de janeiro de 2024</span>
            <p class="summary">This is a sample legal document summary.</p>
        </div>
        """
        
        parser = BrazilianLegalParser(sample_html)
        items = parser.soup.select('.item')
        
        if items:
            print("✅ Parser working correctly")
            return True
        else:
            print("❌ Parser not extracting items")
            return False
            
    except Exception as e:
        print(f"❌ Parser test failed: {e}")
        return False


def test_helpers():
    """Test helper functions."""
    print("\n🔍 Testing helper functions...")
    
    try:
        import sys
        from pathlib import Path
        scraper_path = Path(__file__).parent / "scraper"
        sys.path.insert(0, str(scraper_path))
        
        from utils.helpers import setup_logging, get_theme_list
        
        # Test logging setup
        setup_logging('INFO')
        print("✅ Logging setup working")
        
        # Test theme list
        themes = get_theme_list()
        print(f"✅ Found {len(themes)} themes: {', '.join(themes)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Helper functions test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🇧🇷 Brazilian Legal Content Scraper - Setup Test")
    print("=" * 50)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Imports", test_imports),
        ("Directory Structure", test_directory_structure),
        ("Config Files", test_config_files),
        ("Parser", test_parser),
        ("Helper Functions", test_helpers),
        ("Browser Setup", test_browser_setup)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
            
        if result:
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your scraper is ready to use.")
        print("\n🚀 Quick start:")
        print("python scraper/main.py --list-themes")
        print("python scraper/main.py --theme jurisprudencia --dry-run")
    else:
        print("⚠️  Some tests failed. Please fix the issues before using the scraper.")
        print("\n💡 Common fixes:")
        print("- pip install -r requirements.txt")
        print("- playwright install chromium")
        print("- Check directory structure")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 