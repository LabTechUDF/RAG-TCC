# 🇧🇷 Brazilian Legal Content Scraper - Scrapy Edition

A powerful, production-ready web scraper for Brazilian legal content using **Scrapy** and **Playwright**. Designed specifically for Brazilian legal websites with Portuguese locale support and LGPD compliance.

## 🚀 Features

### **🏛️ Legal Themes Supported**
- **📚 Jurisprudência** - Court decisions and case law from STF, STJ, and state courts
- **⚖️ Súmulas STF** - Supreme Court precedents and legal summaries
- **📋 Normativas STJ** - Superior Court normative acts and regulations
- **🔒 Direito Penal** - Criminal law content, decisions, and precedents
- **🏛️ Tribunais Estaduais** - State court decisions from all 27 Brazilian states

### **🛠️ Technical Capabilities**
- **Scrapy Framework** - Professional web scraping with built-in concurrency, retries, and throttling
- **Playwright Integration** - Full JavaScript support for modern Brazilian legal sites
- **Portuguese Locale** - Proper pt-BR locale and São Paulo timezone
- **LGPD Compliance** - Automatic handling of consent banners and cookies
- **Brazilian Date Parsing** - Recognizes Portuguese date formats
- **Case Number Recognition** - Extracts Brazilian legal case numbers
- **Quality Validation** - Content quality scoring and validation
- **Comprehensive Pipelines** - Data validation, deduplication, and export

## 📦 Installation

### **Prerequisites**
- Python 3.9+ 
- pip or conda

### **Setup**
```bash
# Clone the repository
git clone <repository-url>
cd learning-cursor

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python3 -m playwright install chromium

# Verify installation
cd legal_scraper && python3 manage.py list
```

## 🎯 Quick Start

### **List Available Scrapers**
```bash
cd legal_scraper
python3 manage.py list
```

### **Run a Single Scraper**
```bash
# Run jurisprudence scraper
python3 manage.py run jurisprudencia

# Run with dry-run (no data saved)
python3 manage.py run jurisprudencia --dry-run

# Limit to 5 pages
python3 manage.py run direito_penal --max-pages 5
```

### **Run All Scrapers**
```bash
# Run all themes
python3 manage.py run-all

# Test run without saving data
python3 manage.py run-all --dry-run
```

### **Direct Scrapy Commands**
```bash
# Run with Scrapy directly
python3 -m scrapy crawl jurisprudencia

# Save to specific file
python3 -m scrapy crawl sumulas_stf -o data/sumulas_$(date +%Y%m%d).json

# Custom settings
python3 -m scrapy crawl direito_penal -s DOWNLOAD_DELAY=5
```

## 📊 Data Output

### **File Structure**
```
legal_scraper/
├── data/
│   ├── jurisprudencia/
│   │   ├── jurisprudencia_20241201.jsonl
│   │   └── scraped_20241201_143022.json
│   ├── sumulas_stf/
│   │   └── sumulas_stf_20241201.jsonl
│   └── scraping_stats.json
├── logs/
│   └── scrapy.log
└── httpcache/        # Scrapy HTTP cache
```

### **Data Formats**
**JSONL** (Default): One JSON object per line for streaming processing
```json
{"theme": "jurisprudencia", "title": "Recurso Especial nº 1.234.567", "tribunal": "STJ", "legal_area": "Civil", ...}
{"theme": "jurisprudencia", "title": "Agravo em Recurso Especial nº 7.890.123", "tribunal": "STJ", "legal_area": "Penal", ...}
```

**JSON**: Standard JSON array format
```json
[
  {
    "theme": "jurisprudencia",
    "title": "Recurso Especial nº 1.234.567",
    "tribunal": "STJ", 
    "case_number": "1234567-12.2023.4.01.1234",
    "publication_date": "2023-12-01",
    "legal_area": "Civil",
    "summary": "Ementa do acórdão...",
    "content": "Texto completo da decisão...",
    "url": "https://stj.jus.br/processo/...",
    "scraped_at": "2023-12-01T14:30:22",
    "content_quality": 85
  }
]
```

## ⚙️ Configuration

### **Theme Configuration**
Each theme has its own configuration in `configs/{theme}/config.json`:

```json
{
  "name": "Jurisprudência",
  "description": "Brazilian court decisions and case law",
  "start_url": "https://stj.jus.br/jurisprudencia/",
  "fallback_urls": ["https://portal.stf.jus.br/jurisprudencia/"],
  "selectors": {
    "container": ".resultado-pesquisa",
    "item": ".acordao-item",
    "title": "h3, .titulo-decisao",
    "date": ".data-julgamento",
    "court": ".tribunal",
    "case_number": ".numero-processo",
    "link": "a[href*='acordao']"
  },
  "pagination": {
    "type": "link",
    "selector": ".proximo, .next-page",
    "max_pages": 20
  }
}
```

### **Scrapy Settings**
Key settings in `legal_scraper/settings.py`:

```python
# Brazilian legal sites optimization
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 2
PLAYWRIGHT_LAUNCH_OPTIONS = {
    'locale': 'pt-BR',
    'timezone_id': 'America/Sao_Paulo'
}

# Politeness for legal sites
ROBOTSTXT_OBEY = True
AUTOTHROTTLE_ENABLED = True
```

## 🔧 Management Commands

### **Available Commands**
```bash
# List all spiders
python3 manage.py list

# Run specific spider
python3 manage.py run <spider_name> [--dry-run] [--max-pages N]

# Run all spiders
python3 manage.py run-all [--dry-run] [--max-pages N]

# Show statistics
python3 manage.py stats

# Check configurations
python3 manage.py check-config [spider_name]

# Clean old data
python3 manage.py clean
```

### **Example Workflows**
```bash
# Development workflow
python3 manage.py check-config           # Verify configs
python3 manage.py run jurisprudencia --dry-run --max-pages 2  # Test
python3 manage.py run jurisprudencia     # Production run
python3 manage.py stats                  # Check results

# Production workflow
python3 manage.py run-all --max-pages 50  # Comprehensive scraping
python3 manage.py stats                    # Review statistics
```

## 📈 Monitoring & Statistics

### **Real-time Monitoring**
```bash
# Watch Scrapy logs
tail -f logs/scrapy.log

# Monitor specific spider
python3 -m scrapy crawl jurisprudencia -L INFO
```

### **Statistics Dashboard**
```bash
python3 manage.py stats
```
Shows:
- Total items scraped
- Items per theme
- Quality distribution
- Scraping duration
- Error rates

## 🎛️ Advanced Usage

### **Custom Scrapy Settings**
```bash
# Increase concurrency
python3 -m scrapy crawl jurisprudencia -s CONCURRENT_REQUESTS=16

# Enable HTTP cache for development
python3 -m scrapy crawl sumulas_stf -s HTTPCACHE_ENABLED=True

# Custom user agent
python3 -m scrapy crawl direito_penal -s USER_AGENT="MyLegalBot 1.0"

# Save to CSV
python3 -m scrapy crawl tribunais_estaduais -o results.csv
```

### **Pipeline Customization**
Edit `legal_scraper/pipelines.py` to add custom data processing:

```python
class CustomValidationPipeline:
    def process_item(self, item, spider):
        # Custom validation logic
        if not item.get('legal_area'):
            item['legal_area'] = 'General'
        return item
```

### **Spider Customization**
Create custom spiders by inheriting from `BrazilianLegalSpiderBase`:

```python
from legal_scraper.spiders.base_spider import BrazilianLegalSpiderBase

class CustomSpider(BrazilianLegalSpiderBase):
    name = 'custom_legal'
    allowed_domains = ['custom-site.jus.br']
    
    def parse_item_preview(self, item, response, selectors):
        # Custom parsing logic
        pass
```

## 🚨 Troubleshooting

### **Common Issues**

**1. Playwright Installation**
```bash
# Reinstall Playwright browsers
python3 -m playwright install --force chromium
```

**2. Memory Issues**
```bash
# Reduce concurrency
python3 -m scrapy crawl jurisprudencia -s CONCURRENT_REQUESTS=2
```

**3. SSL/Certificate Errors**
```bash
# Ignore SSL errors (development only)
python3 -m scrapy crawl sumulas_stf -s PLAYWRIGHT_LAUNCH_OPTIONS='{"ignore_https_errors": true}'
```

**4. Rate Limiting**
```bash
# Increase delays
python3 -m scrapy crawl direito_penal -s DOWNLOAD_DELAY=5 -s RANDOMIZE_DOWNLOAD_DELAY=0.8
```

### **Debug Mode**
```bash
# Enable debug logging
python3 -m scrapy crawl jurisprudencia -L DEBUG

# Debug specific components
python3 -m scrapy crawl sumulas_stf -s LOG_LEVEL=DEBUG -s LOG_FILE=debug.log
```

### **Performance Optimization**
```bash
# Disable images and CSS
python3 -m scrapy crawl tribunais_estaduais -s PLAYWRIGHT_ABORT_REQUEST=True

# Enable AutoThrottle
python3 -m scrapy crawl direito_penal -s AUTOTHROTTLE_ENABLED=True -s AUTOTHROTTLE_TARGET_CONCURRENCY=1.0
```

## 📋 Data Fields

### **Common Fields (All Themes)**
- `theme`: Theme name (jurisprudencia, sumulas_stf, etc.)
- `title`: Document title
- `url`: Source URL
- `tribunal`: Court name
- `publication_date`: Publication date (ISO format)
- `legal_area`: Legal area classification
- `content`: Full document text
- `scraped_at`: Scraping timestamp
- `content_quality`: Quality score (0-100)

### **Theme-Specific Fields**

**Jurisprudência:**
- `case_number`: Brazilian case number
- `judge_rapporteur`: Reporting judge
- `decision_type`: Type of decision
- `parties_involved`: Parties in the case
- `voting_result`: Voting outcome

**Súmulas STF:**
- `sumula_number`: Súmula number
- `binding_effect`: Whether it's binding
- `sumula_type`: Type of súmula
- `revision_date`: Last revision date
- `canceled`: Whether canceled

**Normativas STJ:**
- `normative_type`: Type (Portaria, Resolução, etc.)
- `normative_number`: Number
- `effective_date`: Effective date
- `related_laws`: Related legal provisions

**Direito Penal:**
- `crime_type`: Type of crime
- `penalty_type`: Type of penalty
- `legal_provision`: Legal article reference
- `precedent_references`: Related precedents

**Tribunais Estaduais:**
- `state`: Brazilian state (SP, RJ, etc.)
- `court_chamber`: Court chamber
- `instance_level`: 1ª or 2ª instância
- `jurisdiction`: Jurisdiction area

## 🤝 Contributing

### **Adding New Legal Sites**
1. Create configuration in `configs/{theme}/config.json`
2. Customize spider in `legal_scraper/spiders/{theme}.py`
3. Test with `--dry-run` flag
4. Add to management script

### **Development Setup**
```bash
# Install development dependencies
pip install -r requirements.txt
pip install black isort flake8

# Code formatting
black legal_scraper/
isort legal_scraper/

# Run tests
pytest tests/
```

## 📜 License

This project is for educational and research purposes. Please respect the terms of service of Brazilian legal websites and ensure compliance with applicable laws.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review Scrapy logs in `logs/scrapy.log`
3. Test with `--dry-run` and `--max-pages 1`
4. Create an issue with detailed error information

---

**🇧🇷 Made for Brazilian Legal Research** | **⚖️ Respectful • Compliant • Efficient**
