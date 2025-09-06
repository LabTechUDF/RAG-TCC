# 🏛️ STF Legal Content Scraper

A web scraper for Brazilian Supreme Court (STF) legal decisions using **Scrapy** and **Playwright**.

> **Status**: Working STF scraper that extracts legal decisions about criminal law (estelionato previdenciário - art. 171 §3).

## 🏗️ Architecture

### **Spiders**
Extract data from websites. We have:
- `stf_clipboard` - Extracts STF legal decisions (working)
- `stf_legal` - Configurable STF scraper (new)

### **Items** 
Define data structure for scraped content (legal documents with title, content, case number, etc.)

### **Pipelines**
Process scraped data:
- **ValidationPipeline** - Validates required fields
- **DuplicatesPipeline** - Removes duplicate content
- **JsonWriterPipeline** - Saves data to JSON files

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

# Run STF clipboard scraper (working)
poetry run python manage.py run stf_clipboard

# Run with dry-run (no data saved, just testing)
poetry run python manage.py run stf_clipboard --dry-run

# Run with browser visible (for debugging)
poetry run python manage.py run stf_clipboard --show-browser

# Run directly with scrapy
poetry run scrapy crawl stf_clipboard

# Run with custom settings
poetry run scrapy crawl stf_clipboard -s DOWNLOAD_DELAY=5
```

### **Output**
Data saved to `stf_scraper/data/stf_clipboard/` as JSON files with STF legal decisions.

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
