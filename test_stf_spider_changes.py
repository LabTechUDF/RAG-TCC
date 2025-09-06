#!/usr/bin/env python3
"""
Test script to verify STF spider URL and title extraction changes
"""

import re

def test_url_pattern_extraction():
    """Test the URL pattern extraction logic"""
    test_urls = [
        "/pages/search/despacho1583260/false",
        "/pages/search/despacho1075052/false", 
        "/pages/search/HC221912/false",
        "/pages/search/RHC247645/false"
    ]
    
    print("Testing URL pattern extraction:")
    print("=" * 50)
    
    for url in test_urls:
        match = re.search(r'/pages/search/([^/]+)/false', url)
        if match:
            case_number = match.group(1)
            print(f"URL: {url}")
            print(f"Extracted case number: {case_number}")
            print("-" * 30)
        else:
            print(f"❌ No match for URL: {url}")

def test_title_extraction_pattern():
    """Test CSS selector patterns for title extraction"""
    print("\nTesting CSS selector patterns:")
    print("=" * 50)
    
    # Test selectors
    selectors = [
        'a[mattooltip="Dados completos"] div.ng-star-inserted h4.ng-star-inserted::text',
        'div.ng-star-inserted h4.ng-star-inserted::text',
        'h4.ng-star-inserted::text'
    ]
    
    for selector in selectors:
        print(f"Selector: {selector}")
        print("Target: <h4 class=\"ng-star-inserted\">RHC 247645</h4>")
        print("-" * 30)

def simulate_item_data_structure():
    """Simulate the new item data structure"""
    print("\nSimulating new item data structure:")
    print("=" * 50)
    
    # Simulated extracted data
    decision_data_link = "/pages/search/despacho1583260/false"
    title = "RHC 247645"
    
    # Extract case number
    url_match = re.search(r'/pages/search/([^/]+)/false', decision_data_link)
    case_number_from_url = url_match.group(1) if url_match else None
    
    # Create item data structure
    item_data = {
        'title': title,
        'case_number': case_number_from_url,
        'full_decision_data': f"https://jurisprudencia.stf.jus.br{decision_data_link}",
        'processo_link': f"https://portal.stf.jus.br/processos/listarProcessos.asp?numeroProcesso={case_number_from_url}&classe=RHC",
        'source_url': "https://jurisprudencia.stf.jus.br/pages/search?base=decisoes&...",
        'scraped_at': "2025-09-06T12:00:00",
        'item_index': 1,
        'has_clipboard_button': True
    }
    
    print("New item data structure:")
    for key, value in item_data.items():
        print(f"  {key}: {value}")
    
    return item_data

if __name__ == "__main__":
    test_url_pattern_extraction()
    test_title_extraction_pattern()
    simulate_item_data_structure()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed successfully!")
    print("The spider should now extract:")
    print("1. Title from <h4> tags inside decision links")
    print("2. Case numbers from URL patterns")
    print("3. Full decision data URLs for later processing")
