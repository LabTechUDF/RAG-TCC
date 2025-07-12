# 🇧🇷 Brazilian Legal Content Scraper

A comprehensive, modular web scraping framework for Brazilian legal documents using **Playwright** and **BeautifulSoup**. Designed specifically for Brazilian legal websites with Portuguese locale support and LGPD compliance handling.

## 🌟 Features

- **Modular Architecture**: Theme-based scraping for different legal content categories
- **Brazilian-Specific**: Portuguese locale, proper headers, and LGPD consent handling
- **Async/Await**: High-performance asynchronous scraping with Playwright
- **Data Quality**: Built-in validation, reporting, and quality metrics
- **Robust**: Retry logic, fallback URLs, and comprehensive error handling
- **CLI Interface**: Easy-to-use command-line interface
- **Multiple Formats**: Export data as JSON or CSV

## 📋 Supported Themes

| Theme | Description | Target Sites |
|-------|-------------|--------------|
| **direito_penal** | Criminal law decisions and legislation | STF, STJ criminal law content |
| **jurisprudencia** | Court decisions and case law | STF, STJ, State courts |
| **sumulas_stf** | Supreme Court binding precedents | STF Súmulas |
| **normativas_stj** | Superior Court normative acts | STJ regulations and instructions |
| **tribunais_estaduais** | State court decisions | TJSP, TJRJ, TJMG, etc. |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Run the Scraper

```bash
# List available themes
python scraper/main.py --list-themes

# Scrape a specific theme
python scraper/main.py --theme jurisprudencia

# Scrape multiple themes
python scraper/main.py --theme direito_penal sumulas_stf

# Scrape all themes
python scraper/main.py --all

# Dry run (see what would be scraped)
python scraper/main.py --theme jurisprudencia --dry-run
```

## 📁 Project Structure

```
scraper/
├── main.py                    # Main CLI entry point
├── utils/                     # Core utilities
│   ├── browser.py            # Playwright Brazilian browser setup
│   ├── parser.py             # BeautifulSoup legal content parser
│   └── helpers.py            # Logging, validation, file operations
├── themes/                    # Theme-specific scrapers
│   ├── direito_penal/
│   │   ├── scraper.py        # Criminal law scraper
│   │   └── config.json       # URLs, selectors, filters
│   ├── jurisprudencia/
│   ├── sumulas_stf/
│   ├── normativas_stj/
│   └── tribunais_estaduais/
├── data/                      # Scraped data output
│   ├── direito_penal/
│   ├── jurisprudencia/
│   └── ...
└── logs/                      # Scraping logs
    └── scraping.log
```

## ⚙️ Configuration

Each theme has a `config.json` file with:

```json
{
  "name": "Theme Name",
  "description": "Theme description",
  "start_url": "https://...",
  "fallback_urls": ["https://..."],
  "selectors": {
    "container": ".results",
    "item": ".item",
    "title": "h3",
    "date": ".date"
  },
  "pagination": {
    "type": "button",
    "selector": ".next",
    "max_pages": 10
  },
  "delays": {
    "page_load": 3000,
    "between_requests": 2000
  }
}
```

## 🔧 Advanced Usage

### Programmatic Access

```python
import asyncio
from scraper.main import BrazilianLegalScraper

async def main():
    scraper = BrazilianLegalScraper()
    
    # Run single theme
    result = await scraper.run_theme('jurisprudencia')
    print(f"Scraped {result['total_items']} items")
    
    # Run multiple themes
    results = await scraper.run_multiple_themes(['direito_penal', 'sumulas_stf'])
    
asyncio.run(main())
```

### Custom Parsing

```python
from scraper.utils.parser import BrazilianLegalParser

# Parse custom HTML content
parser = BrazilianLegalParser(html_content)
items = parser.extract_jurisprudencia(element)
```

### Browser Management

```python
from scraper.utils.browser import BrazilianBrowser

async def custom_scraping():
    async with BrazilianBrowser() as browser:
        page = await browser.new_page()
        await browser.navigate_with_retry(page, "https://example.gov.br")
        # Handle consent banners automatically
        await browser.handle_consent_banner(page)
```

## 📊 Data Output

### Scraped Data Structure

```json
{
  "title": "Legal document title",
  "date": "2024-01-15",
  "court": "STF",
  "case_number": "1234567-12.2024.1.00.0000",
  "summary": "Document summary/ementa",
  "link": "https://...",
  "pdf_link": "https://...file.pdf",
  "relator": "Minister Name",
  "type": "Acórdão",
  "theme": "jurisprudencia",
  "scraped_at": "2024-01-15T14:30:00"
}
```

### Quality Reports

Each scraping session generates a quality report:

```json
{
  "theme": "jurisprudencia",
  "scraping_session": {
    "start_time": "2024-01-15T14:00:00",
    "duration_seconds": 120.5
  },
  "data_quality": {
    "total_items": 150,
    "quality_score": 0.85,
    "missing_fields": {"date": 5}
  },
  "status": "SUCCESS",
  "recommendations": ["Review date parsing for better extraction"]
}
```

## 🌐 Brazilian Legal Website Support

### Locale Configuration
- **Language**: Portuguese (pt-BR)
- **Timezone**: America/Sao_Paulo
- **Headers**: Brazilian-specific user agents and accept headers

### LGPD Compliance
- Automatic detection and handling of cookie consent banners
- Support for common Brazilian data protection consent patterns
- Configurable consent selectors

### Supported Sites
- **STF** (Supremo Tribunal Federal)
- **STJ** (Superior Tribunal de Justiça)
- **State Courts** (TJSP, TJRJ, TJMG, etc.)
- **Specialized Legal Databases**

## 🛠️ Development

### Adding New Themes

1. Create theme directory: `scraper/themes/new_theme/`
2. Add `config.json` with selectors and settings
3. Create `scraper.py` with theme-specific logic
4. Register in `main.py`

### Custom Parsers

Extend `BrazilianLegalParser` for specialized content:

```python
class CustomParser(BrazilianLegalParser):
    def extract_custom_data(self, element):
        # Custom extraction logic
        return data
```

## 📝 Logging

Comprehensive logging with multiple levels:

```bash
# Debug mode
python scraper/main.py --theme jurisprudencia --log-level DEBUG

# Logs location
tail -f scraper/logs/scraping.log
```

## 🔍 Troubleshooting

### Common Issues

**No data scraped**: Check if target website structure has changed
```bash
python scraper/main.py --theme jurisprudencia --log-level DEBUG
```

**Consent banner issues**: Update consent selectors in browser.py
```python
consent_selectors = [
    'button[id*="accept"]',
    '.lgpd-accept'
]
```

**Rate limiting**: Increase delays in config.json
```json
{
  "delays": {
    "page_load": 5000,
    "between_requests": 3000
  }
}
```

## 📄 License

This project is designed for educational and research purposes. Please respect the terms of service of target websites and Brazilian data protection laws (LGPD).

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your theme or improvements
4. Submit a pull request

## 📞 Support

For issues or questions:
- Check the logs in `scraper/logs/`
- Review the configuration files
- Open an issue with detailed error information

---

**Built with ❤️ for the Brazilian legal community**
