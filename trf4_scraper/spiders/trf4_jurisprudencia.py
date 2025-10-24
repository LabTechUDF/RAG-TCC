"""
TRF4 Jurisprudência Spider

Implements the scraping flow described in prompt.md for TRF4.
Uses Playwright via scrapy-playwright and a file-backed lock/state to coordinate
parallel browser workers incrementing a shared page counter.

Notes:
- This spider expects queries to be provided via the `query` spider arg or will
  default to a single empty query if none provided.
"""

import json
import time
import os
import logging
from pathlib import Path
import scrapy
from scrapy_playwright.page import PageMethod
from trf4_scraper.utils import shared_state


class Trf4JurisprudenciaSpider(scrapy.Spider):
    name = 'trf4_jurisprudencia'
    allowed_domains = ['jurisprudencia.trf4.jus.br']
    start_urls = ['https://jurisprudencia.trf4.jus.br/pesquisa/pesquisa.php']

    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 1.5,
        'CONCURRENT_REQUESTS': 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # query can be passed as spider arg: -a query='texto'
        self.query_text = kwargs.get('query', '')

        # Shared state paths (persisted on disk)
        # Try to obtain SHARED_STATE_DIR from Scrapy settings if available,
        # otherwise fallback to environment variable or project-relative default.
        base_state_dir = None
        try:
            base_state_dir = Path(self.settings.get('SHARED_STATE_DIR'))
        except Exception:
            # fallback to spider args or env var or project-relative default
            base_state_dir = Path(kwargs.get('shared_state_dir') or os.getenv('SHARED_STATE_DIR') or Path(__file__).parent.parent.parent / '.scrapy_state')
        base_state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = base_state_dir / 'trf4_shared_state.json'
        self.lock_path = base_state_dir / 'trf4_shared_state.lock'

        # For the AJAX site we will treat pages as page parameter: ?page=N
        self.base_url = str(self.start_urls[0])

        # Internal runtime flags
        self.total_pages = None
        # Ensure logs directory and file exist, configure logger
        logs_dir = Path('logs')
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / 'trf4_scraper.log'
        # Create file if not exists
        if not log_file.exists():
            log_file.write_text('')

        # Configure a package-specific logger so spider logs are persisted
        logger_name = 'trf4_scraper'
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        # Ensure a file handler exists for this log file and reuse it across loggers
        file_handler = None
        for h in logger.handlers:
            try:
                if getattr(h, 'baseFilename', None) == str(log_file):
                    file_handler = h
                    break
            except Exception:
                continue

        if file_handler is None:
            file_handler = logging.FileHandler(str(log_file))
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Attach the same file handler to other key loggers so framework logs go to the same file
        target_logger_names = ['scrapy', 'scrapy_playwright', 'playwright']
        for name in target_logger_names:
            try:
                target = logging.getLogger(name)
                already = any(getattr(h, 'baseFilename', None) == str(log_file) for h in target.handlers)
                if not already:
                    target.addHandler(file_handler)
            except Exception:
                # If any logger isn't available or attaching fails, continue
                continue

        # Attach the file handler to the root logger so all loggers (including the spider's
        # built-in logger) will write to the same file.
        root_logger = logging.getLogger()
        if not any(getattr(h, 'baseFilename', None) == str(log_file) for h in root_logger.handlers):
            root_logger.addHandler(file_handler)

        # Log spider initialization using the package logger
        logger.debug(f'Initializing TRF4 spider (query="{self.query_text}")')

    def start_requests(self):
        self.logger.info('start_requests called')
        # Start by opening the search page and performing the query
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'load'),
                        PageMethod('wait_for_selector', '#btnPesquisaAvancada', timeout=30000),
                    ],
                    'query_text': self.query_text,
                },
                callback=self.parse_search_page,
                dont_filter=True,
            )

    async def parse_search_page(self, response):
        """Open advanced search, select Decisão monocrática, enter query and submit."""
        page = response.meta.get('playwright_page')
        query_text = response.meta.get('query_text', '')

        self.logger.info('parse_search_page started')

        try:
            self.logger.info("Opening advanced options and setting filters")

            # Click the Pesquisa avançada button
            await page.click('#btnPesquisaAvancada')
            # Small wait to allow dynamic content
            time.sleep(0.5)

            # Select "Decisão monocrática" - we try to click element by its inner text
            # Look for the element with class filter-option-inner-inner containing the text
            await page.wait_for_selector(".filter-option-inner-inner", timeout=5000)
            # Try to find the specific option and click
            await page.evaluate('''() => {
                const els = Array.from(document.querySelectorAll('.filter-option-inner-inner'));
                const target = els.find(e => e.textContent && e.textContent.trim().toLowerCase().includes('decisão monocrática')) || els[0];
                if (target) target.click();
            }''')

            # Fill the search box
            await page.fill('#txtPesquisa', query_text)
            # Press Enter to submit OR click the search button
            await page.click('#btnConsultar_form_inicial')

            # Wait for results to load (networkidle and presence of results or no-results)
            await page.wait_for_load_state('networkidle')
            # Give AJAX some extra time
            time.sleep(1.0)

            # After first search, compute total pages
            self.total_pages = await self._extract_total_pages(page)
            if not self.total_pages:
                self.logger.info("Could not detect multiple pages, proceeding with single-page processing")
                self.total_pages = 1

            self.logger.info(f"Total pages detected: {self.total_pages}")

            # For parallel workers we will loop asking the shared state for next page
            while True:
                next_page = shared_state.get_and_increment_page(self.state_path, self.lock_path)
                if next_page is None:
                    self.logger.info("Shared state indicates done. Stopping worker.")
                    break

                if next_page > self.total_pages:
                    # mark done and break
                    self.logger.info(f"No more pages: requested {next_page} > {self.total_pages}")
                    shared_state.mark_done(self.state_path, self.lock_path)
                    break

                # For an AJAX site we construct a URL with page param (workers will use same base URL with page query)
                page_url = f"{self.base_url}?page={next_page}"
                self.logger.info(f"Worker processing page {next_page}: {page_url}")

                yield scrapy.Request(
                    url=page_url,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                            PageMethod('wait_for_selector', 'div.citacao, i.material-icons', timeout=15000),
                        ],
                        'page_number': next_page,
                        'query_text': query_text,
                    },
                    callback=self.parse_results_page,
                    dont_filter=True,
                )

        finally:
            if page:
                await page.close()

    async def _extract_total_pages(self, page):
        """Try to extract total pages from the pagination area; return int or None."""
        self.logger.info('_extract_total_pages called')
        try:
            # Example: there may be an element showing "X de Y" or similar
            text = await page.evaluate(r'''() => {
                const el = document.querySelector('nav .pagination, .paginacao, .paginator, .page-info');
                if (el) return el.textContent || '';
                // fallback search for any span containing 'de'
                const spans = Array.from(document.querySelectorAll('span'));
                const maybe = spans.find(s => s.textContent && /de\s+\d+/i.test(s.textContent));
                return maybe ? maybe.textContent : '';
            }''')

            if not text:
                self.logger.info('No pagination text found while extracting total pages')
                return None

            import re
            m = re.search(r'de\s*(\d+)', text)
            if m:
                total = int(m.group(1))
                self.logger.info(f'Parsed total pages: {total} from text: {text.strip()}')
                return total
            self.logger.info(f'Could not parse total pages from text: {text.strip()}')
            return None
        except Exception:
            self.logger.exception('Exception while extracting total pages')
            return None

    async def parse_results_page(self, response):
        """Parse a page's results and for each result copy citation and save JSON."""
        page = response.meta.get('playwright_page')
        page_number = response.meta.get('page_number', 1)
        query_text = response.meta.get('query_text', '')

        self.logger.info(f'parse_results_page started for page {page_number}')

        try:
            self.logger.info(f"Parsing results on page {page_number}")

            # Wait a short while for elements to stabilize
            await page.wait_for_timeout(500)

            # Use Playwright's page to find the icons that open the citation modal.
            # TRF4 uses icons with class: "material-icons icon-aligned iconeComTexto mr-1" and text 'content_copy'.
            try:
                icons = await page.query_selector_all('i.material-icons.icon-aligned.iconeComTexto.mr-1')
            except Exception:
                icons = []

            # Fallback: select icons that have the exact text content 'content_copy'
            if not icons:
                try:
                    icons = await page.query_selector_all("xpath=//i[normalize-space(text())='content_copy']")
                except Exception:
                    icons = []

            if not icons:
                self.logger.warning(f'No content_copy icons found on page {page_number}. Saving page HTML for inspection.')
                try:
                    page_html = await page.content()
                    dump_path = Path('logs') / f'trf4_page_{page_number}.html'
                    dump_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(dump_path, 'w', encoding='utf-8') as fh:
                        fh.write(page_html)
                    self.logger.info(f'Saved page HTML for inspection: {dump_path}')
                except Exception as e:
                    self.logger.warning(f'Failed to save page HTML: {e}')

            else:
                self.logger.info(f'Found {len(icons)} content_copy icons on page {page_number}')

            # Iterate over each icon and try to copy its citation
            for idx, icon_handle in enumerate(icons, start=1):
                try:
                    self.logger.debug(f'Clicking content_copy icon #{idx} on page {page_number}')
                    await icon_handle.click()

                    # Wait for citation content container
                    try:
                        await page.wait_for_selector('#divConteudoCitacao, div.citacao', timeout=8000)
                    except Exception:
                        self.logger.warning(f'Citation container not found after clicking icon #{idx} on page {page_number}')

                    # Click the copy action (id iconCopiarCitacao) or fallback to anchor text
                    try:
                        copy_btn = await page.query_selector('a#iconCopiarCitacao')
                        if copy_btn:
                            await copy_btn.click()
                        else:
                            await page.evaluate("() => { const a = Array.from(document.querySelectorAll('a')).find(x => (x.textContent||'').trim().toLowerCase()==='copiar'); if (a) a.click(); }")
                    except Exception as e:
                        self.logger.debug(f'Failed to click copy button for item #{idx}: {e}')

                    # Give the clipboard a moment to populate
                    await page.wait_for_timeout(800)

                    # Read clipboard
                    clipboard_text = None
                    try:
                        clipboard_text = await page.evaluate('''async () => { try { return await navigator.clipboard.readText(); } catch(e) { return null; } }''')
                    except Exception as e:
                        self.logger.debug(f'Clipboard read failed for item #{idx}: {e}')

                    if clipboard_text:
                        item_data = {
                            'title': f'trf4_item_{page_number}_{idx}',
                            'page': page_number,
                            'index_on_page': idx,
                            'query': query_text,
                            'content': clipboard_text,
                        }
                        filename = Path('data') / 'trf4_jurisprudencia' / f'page_{page_number}_item_{idx}.json'
                        filename.parent.mkdir(parents=True, exist_ok=True)
                        with open(filename, 'w', encoding='utf-8') as fh:
                            json.dump(item_data, fh, ensure_ascii=False)
                        self.logger.info(f'Saved citation JSON: {filename}')
                        yield item_data
                    else:
                        self.logger.warning(f'Clipboard empty for item #{idx} on page {page_number}')

                except Exception as e:
                    self.logger.error(f'Error processing icon #{idx} on page {page_number}: {e}')

        finally:
            if page:
                await page.close()
