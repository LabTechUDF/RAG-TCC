#!/usr/bin/env python3
"""
Simple test to verify connection to Brazilian legal sites (no external dependencies)
"""
import urllib.request
import urllib.error
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
                
                # Read the HTML content
                html_content = response.read().decode('utf-8', errors='ignore')
                
                # Check for common Brazilian legal site indicators
                indicators = [
                    ('jurisprudencia', 'jurisprudencia'),
                    ('acordao', 'acordao'),
                    ('decisao', 'decisao'),
                    ('processo', 'processo'),
                    ('penal', 'penal'),
                    ('criminal', 'criminal'),
                    ('tribunal', 'tribunal'),
                    ('stf', 'stf'),
                    ('stj', 'stj'),
                    ('forms', '<form'),
                    ('search inputs', 'type="search"'),
                ]
                
                print("  📌 Content indicators:")
                for indicator, search_term in indicators:
                    count = html_content.lower().count(search_term.lower())
                    if count > 0:
                        print(f"    ✓ {indicator}: {count} occurrences")
                
                # Check content length
                content_length = len(html_content)
                print(f"  📊 Content length: {content_length} characters")
                
                # Look for potential data containers
                containers = [
                    'resultado-pesquisa',
                    'listagem-jurisprudencia',
                    'lista-acordaos',
                    'item-jurisprudencia',
                    'acordao-item',
                    'item-pesquisa',
                ]
                
                print("  🎯 Potential data containers:")
                for container in containers:
                    if container in html_content:
                        print(f"    ✓ {container}: found")
                
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
        return False
    else:
        print(f"✅ Ready to configure scrapers with {working_sites} working sites!")
        return True

if __name__ == "__main__":
    main() 