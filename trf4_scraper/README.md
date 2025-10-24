# trf4_scraper

Minimal spider and helpers for scraping TRF4 jurisprudência. This package mirrors conventions from `stf_scraper` and uses Playwright via `scrapy-playwright`.

Prerequisites
- Python environment with the project's requirements installed (see top-level `requirements.txt`). Ensure the following packages are available:
  - scrapy
  - scrapy-playwright
  - playwright (and run `playwright install chromium`)

Files
- `spiders/trf4_jurisprudencia.py`: main spider. Accepts `-a query='texto'` to set the search text.
- `utils/shared_state.py`: file-lock backed shared page counter for coordinating parallel workers.
- `settings.py`: minimal Playwright and concurrency settings for the package.

How it works (summary)
- The spider opens the search page, clicks "Pesquisa avançada", selects "Decisão monocrática", fills the query input and submits the search.
- It extracts the total number of pages (if present) and then uses a file-backed shared state to allocate page numbers to multiple parallel browser workers.
- Each worker calls `get_and_increment_page` to obtain the next page to process and `mark_done` when all pages are processed.
- For each result on a page the spider attempts to click the clipboard icon, then the "Copiar" button, reads the clipboard content (via Playwright evaluate) and saves a JSON file under `data/trf4_jurisprudencia/`.

Running the spider

Examples (from project root):

```bash
# Install playwright browsers once (if not yet done)
playwright install chromium

# Run the spider with a query and default settings
scrapy runspider trf4_scraper/spiders/trf4_jurisprudencia.py -a query='seu texto aqui' -s SHARED_STATE_DIR=.scrapy_state
```

Parallel workers
- Start multiple processes (or supervisors) that run the same spider command. Each process will coordinate page numbers via the shared state files stored in the directory passed as `SHARED_STATE_DIR`.
- Example: start 3 terminal sessions running the same scrapy command; they will coordinate through `.scrapy_state/trf4_shared_state.json` and `.scrapy_state/trf4_shared_state.lock`.

Notes & troubleshooting
- The TRF4 site uses AJAX — the spider uses waits and short sleeps to stabilize before interactions. Selectors may require adjustments depending on live site changes.
- Clipboard access depends on Playwright context permissions; if clipboard reading fails, items will be skipped and a warning will be logged.
- No extra markdown instructions were added outside this README (per repo rule).
