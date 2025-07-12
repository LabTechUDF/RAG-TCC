### 🎯 **Prompt for Agent: Create a Thematic Web Scraper for Brazilian Legal Content Using Playwright + BeautifulSoup**

Develop a Python web scraping project that uses **Playwright** for page navigation and **BeautifulSoup** for HTML parsing. The project should be modular and structured by **themes**, where each theme represents a category of **Brazilian legal documents** or web pages to be scraped. All target websites will be from **Brazil**, written in **Portuguese**, and might require setting **location or locale settings** to support regional content loading properly.

---

### 🌐 **Important Locale and Language Requirements**

- All websites are Brazilian (TLDs like `.gov.br`, `.jus.br`, etc.)
- Content is in **Portuguese**
- Set **browser language or locale to Portuguese (pt-BR)** in Playwright configuration
- Handle possible cookie/consent banners related to Brazilian data protection laws (LGPD)

---

### 🧱 **Project Specifications**

**1. Required Technologies:**

- `playwright` (Chromium in headless mode, with Portuguese locale set)
- `beautifulsoup4`
- `requests` (optional, e.g., for downloading PDFs or supplementary files)

**2. Project Directory Structure:**

```plaintext
scraper/
├── main.py
├── utils/
│   └── browser.py
│   └── parser.py
│   └── helpers.py
├── themes/
│   ├── direito_penal/
│   │   ├── scraper.py
│   │   └── config.json
│   ├── jurisprudencia/
│   │   ├── scraper.py
│   │   └── config.json
│   ├── sumulas_stf/
│   ├── normativas_stj/
│   └── tribunais_estaduais/
├── data/
│   ├── direito_penal/
│   ├── jurisprudencia/
│   ├── sumulas_stf/
│   ├── normativas_stj/
│   └── tribunais_estaduais/
└── logs/
    └── scraping.log
```

---

### ⚙️ **Functional Requirements**

**1. Modular Architecture**

- Each theme folder under `themes/` is self-contained with its own `scraper.py`
- Implement key functions: `run_scraper()`, `parse_page()`, `save_data()`

**2. Browser Setup with Playwright**

- In `browser.py`, launch browser with:

  - Portuguese locale (`"pt-BR"`)
  - Proper user-agent headers for Brazilian sites
  - Headless Chromium

- Handle pagination, dynamic content loading, and consent modals

**3. Parsing Logic with BeautifulSoup**

- Use `parser.py` to implement BeautifulSoup parsing and content extraction logic
- Extract structured content (titles, dates, links, summaries, etc.)

**4. Logging**

- Log events in `logs/scraping.log`, including start/end times, errors, and number of items scraped

**5. Config Per Theme**

- Each `config.json` defines:

  ```json
  {
    "start_url": "https://...",
    "selectors": {
      "item": ".class",
      "title": ".title",
      "date": ".date"
    },
    "pagination": {
      "type": "button",
      "selector": ".next-page"
    }
  }
  ```

---

### 🧠 **Best Practices**

- Use `async/await` Playwright API
- Use docstrings and type hints
- Add retry logic for failed requests
- Save output in `.json` or `.csv` inside `data/<theme>/`
