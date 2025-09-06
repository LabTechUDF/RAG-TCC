# 🏛️ STF Legal Content Scraper

A web scraper for Brazilian Supreme Court (STF) legal decisions using **Scrapy** and **Playwright**.

> **Status**: Working STF scraper that extracts legal decisions about criminal law (estelionato previdenciário - art. 171 §3).

## 🏗️ Architecture

### **Spiders**
Extract data from websites. We have:
- `stf_jurisprudencia` - Extracts STF legal decisions (working)

### **Items** 
Define data structure for scraped content (legal documents with title, content, case number, etc.)

### **Pipelines**
Process scraped data:
- **ValidationPipeline** - Validates required fields
- **DuplicatesPipeline** - Removes duplicate content

### **Middlewares**
Handle requests/responses between spiders and websites (headers, retries, etc.)

### **Settings**
Configure Playwright browser, delays, file outputs, etc.

## 🚀 How to Run

### **Requirements**
- Python 3.12+
- Poetry

### **Setup**
```bash
# Install dependencies
poetry install

# Install browser
poetry run playwright install chromium
```

### **Run Scrapers**
```bash
# Go to scraper directory
cd stf_scraper

# List available spiders
poetry run python manage.py list

# Run STF jurisprudência scraper (working)
poetry run python manage.py run stf_jurisprudencia

# Run with dry-run (no data saved, just testing)
poetry run python manage.py run stf_jurisprudencia --dry-run

# Run with browser visible (for debugging)
poetry run python manage.py run stf_jurisprudencia --show-browser

# Run directly with scrapy
poetry run scrapy crawl stf_jurisprudencia

# Run with custom settings
poetry run scrapy crawl stf_jurisprudencia -s DOWNLOAD_DELAY=5

# Run with full INFO in dev mode
ENV=dev poetry run scrapy crawl stf_jurisprudencia -a dev_mode=true -s CLOSESPIDER_ITEMCOUNT=2 -L INFO
```

### **Output**
Data saved to `stf_scraper/data/stf_jurisprudencia/` as JSON files with STF legal decisions.

## 📁 Structure
```
stf_scraper/
├── stf_scraper/
│   ├── spiders/          # Data extraction logic
│   ├── items.py          # Data structure definitions  
│   ├── pipelines.py      # Data processing
│   ├── middlewares.py    # Request/response handling
│   └── settings.py       # Configuration
├── data/                 # Scraped data output
└── manage.py             # Management script
```
