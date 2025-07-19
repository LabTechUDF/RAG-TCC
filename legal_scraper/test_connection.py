#!/usr/bin/env python3
"""
Simple test to verify connection to Brazilian legal sites
"""
import urllib.request
import urllib.error
from bs4 import BeautifulSoup
import sys

def test_site_connection(url, site_name):
    """Test connection to a Brazilian legal site"""
    print(f"\n🔍 Testing {site_name}: {url}")
    
    try:
        # Use a proper User-Agent to avoid being blocked
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print(f"✅ Connection successful: {response.status}")
                
                # Parse HTML to check structure
                soup = BeautifulSoup(response.read(), 'html.parser')
                
                # Check for common Brazilian legal site elements
                elements_to_check = [
                    ('title', soup.title.string if soup.title else None),
                    ('jurisprudencia links', len(soup.find_all('a', href=lambda x: x and 'jurisprudencia' in x.lower()))),
                    ('acordao links', len(soup.find_all('a', href=lambda x: x and 'acordao' in x.lower()))),
                    ('decisao links', len(soup.find_all('a', href=lambda x: x and 'decisao' in x.lower()))),
                    ('processo links', len(soup.find_all('a', href=lambda x: x and 'processo' in x.lower()))),
                    ('penal mentions', len(soup.find_all(text=lambda x: x and 'penal' in x.lower()))),
                    ('forms', len(soup.find_all('form'))),
                    ('search inputs', len(soup.find_all('input', {'type': ['search', 'text']}))),
                ]
                
                for element, value in elements_to_check:
                    if value:
                        print(f"  📌 {element}: {value}")
                
                # Check for potential selectors
                potential_selectors = [
                    '.resultado-pesquisa', '.listagem-jurisprudencia', '.lista-acordaos',
                    '.item-jurisprudencia', '.acordao-item', '.item-pesquisa',
                    '.titulo-acordao', '.ementa-titulo', '.titulo-jurisprudencia',
                    '.data-julgamento', '.data-decisao', '.data-publicacao',
                ]
                
                print("  🎯 Potential selectors found:")
                for selector in potential_selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"    ✓ {selector}: {len(elements)} elements")
                
                return True
            else:
                print(f"❌ Connection failed: {response.status}")
                return False
                
    except urllib.error.URLError as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Test connection to Brazilian legal sites"""
    print("🇧🇷 Testing Brazilian Legal Sites Connection")
    print("=" * 50)
    
    # Test sites from our configuration
    test_sites = [
        ("https://portal.stf.jus.br/jurisprudencia/", "STF Jurisprudência"),
        ("https://www.stj.jus.br/sites/portalp/Paginas/Jurisprudencia/Jurisprudencia.aspx", "STJ Jurisprudência"),
        ("https://www.tjsp.jus.br/", "TJSP"),
        ("https://www.tjrj.jus.br/", "TJRJ"),
    ]
    
    results = []
    for url, name in test_sites:
        success = test_site_connection(url, name)
        results.append((name, success))
    
    # Summary
    print("\n📊 Summary:")
    print("=" * 30)
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    working_sites = sum(1 for _, success in results if success)
    print(f"\n{working_sites}/{len(results)} sites accessible")
    
    if working_sites == 0:
        print("⚠️  No sites accessible. Check internet connection or site availability.")
        sys.exit(1)
    else:
        print("✅ Ready to configure scrapers with working sites!")

if __name__ == "__main__":
    main() 