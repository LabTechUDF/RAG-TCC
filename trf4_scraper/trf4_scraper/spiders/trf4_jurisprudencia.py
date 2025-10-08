"""
TRF 4ª Região Jurisprudência Spider - Focused on extracting clipboard content and PDFs from TRF 4ª Região decisões
"""

import re
import json
import scrapy
import os
from datetime import datetime
from pathlib import Path
from scrapy.exceptions import CloseSpider
from scrapy_playwright.page import PageMethod
from ..items import (
    JurisprudenciaItem, 
    get_classe_processual_from_url,
    extract_relator_from_content,
    extract_publication_date_from_content,
    extract_decision_date_from_content,
    extract_partes_from_content
)

from scrapy.utils.project import get_project_settings
from ..utils.shared_state import (
    get_and_increment_page, mark_done, read_state, write_state
)


class Trf4JurisprudenciaSpider(scrapy.Spider):
    """Focused spider for TRF 4ª Região jurisprudência content and PDF extraction"""

    name = 'trf4_jurisprudencia'
    # TODO: Update to TRF 4ª Região domain when available
    allowed_domains = ['jurisprudencia.trf4.jus.br']

    def load_query_array(self):
        """Load query array from JSON file or group file"""
        # Check if group file is provided (for worker-specific processing)
        group_file = getattr(self, 'group_file', None)
        
        if group_file:
            return self.load_group_file(group_file)
        
        # Check if custom query file is provided via settings
        custom_query_file = getattr(self, 'query_file', None)
        
        if custom_query_file:
            query_file = Path(custom_query_file)
        else:
            # Default query file path
            query_file = Path(__file__).parent.parent.parent / 'data' / 'simple_query_spider' / 'query_links.json'
        
        if not query_file.exists():
            self.logger.error(f"Query file not found: {query_file}")
            return []
        
        try:
            with open(query_file, 'r', encoding='utf-8') as f:
                query_array = json.load(f)
            self.logger.info(f"Loaded {len(query_array)} queries from {query_file}")
            return query_array
        except Exception as e:
            self.logger.error(f"Error loading query file: {e}")
            return []

    def load_group_file(self, group_file_path):
        """Load group file and convert to query array format"""
        group_file = Path(group_file_path)
        
        if not group_file.exists():
            self.logger.error(f"Group file not found: {group_file}")
            return []
        
        try:
            with open(group_file, 'r', encoding='utf-8') as f:
                group_data = json.load(f)
            
            # Convert group format to query array format
            query_array = []
            
            for page_data in group_data.get('pages', []):
                query_item = {
                    'query': group_data.get('query', ''),
                    'artigo': group_data.get('article', 'unknown'),
                    'url': page_data['url'],
                    'page_number': page_data['page_number'],
                    'group_id': group_data.get('group_id', 0)
                }
                query_array.append(query_item)
            
            self.logger.info(f"📁 Loaded Group {group_data.get('group_id', 0)} with {len(query_array)} pages from {group_file.name}")
            self.logger.info(f"🎯 Worker will process pages {query_array[0]['page_number']}-{query_array[-1]['page_number']}")
            
            return query_array
            
        except Exception as e:
            self.logger.error(f"Error loading group file: {e}")
            return []

    custom_settings = {
        'PLAYWRIGHT_ABORT_REQUEST': lambda request: request.resource_type in ["image", "stylesheet", "font", "media"],
        'DOWNLOAD_DELAY': 2.5,  # Slightly higher delay for individual spider safety
        'RANDOMIZE_DOWNLOAD_DELAY': 1.2,  # More randomization to appear human-like
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,  # 3 parallel requests for page groups
        'CONCURRENT_REQUESTS': 3,  # 3 concurrent requests for parallel page processing
        'RETRY_TIMES': 3,
        'ROBOTSTXT_OBEY': False,
    }


    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        # Load query array from JSON file
        spider.query_array = spider.load_query_array()
        spider.current_query_info = None
        # Usar apenas a primeira query para scraping compartilhado
        if spider.query_array:
            spider.shared_query_info = spider.query_array[0]
            spider.base_url = spider.shared_query_info['url'].split('&page=')[0]
        else:
            spider.shared_query_info = None
            spider.base_url = None
        # Diretório de estado compartilhado já criado e funções utilitárias já importadas
        state_dir = Path(__file__).parent.parent / 'data' / 'shared_pagination'
        state_dir.mkdir(parents=True, exist_ok=True)
        # Parallel browser count from settings
        spider.parallel_browser_count = crawler.settings.getint('PARALLEL_BROWSER_COUNT', 3)
        # Dev mode
        spider.dev_mode = (
            kwargs.get('dev_mode', '').lower() in ['true', '1', 'yes'] or
            os.getenv('SPIDER_DEV_MODE', '').lower() in ['true', '1', 'yes'] or
            os.getenv('ENV', '').lower() in ['dev', 'development']
        )
        if spider.dev_mode:
            spider.items_extracted = 0
            spider.max_items = 5
            spider.logger.info("🚧 Running in DEVELOPMENT mode - limited to 5 items")
            spider.custom_settings['CLOSESPIDER_ITEMCOUNT'] = 5
        else:
            spider.items_extracted = 0
            spider.max_items = None
            spider.logger.info("🚀 Running in PRODUCTION mode - no item limit")
            if 'CLOSESPIDER_ITEMCOUNT' in spider.custom_settings:
                del spider.custom_settings['CLOSESPIDER_ITEMCOUNT']
        # Inicializa atributos de paginação para evitar AttributeError
        spider.total_pages = None
        spider.items_processed_on_current_page = 0
        spider.total_items_on_current_page = 0
        spider.current_page_number = 1
        return spider


    def start_requests(self):
        settings = get_project_settings()
        parallel_count = settings.getint('PARALLEL_BROWSER_COUNT', 1)
        shared_state_dir = settings.get('SHARED_STATE_DIR', '.scrapy_state')
        state_file = os.path.join(shared_state_dir, 'stf_shared_state.json')
        lock_file = os.path.join(shared_state_dir, 'stf_shared_state.lock')

        # Inicializa estado se não existir
        if not os.path.exists(state_file):
            os.makedirs(shared_state_dir, exist_ok=True)
            write_state(state_file, {"current_page_number": 1, "done": False})

        self._shared_state_file = state_file
        self._shared_lock_file = lock_file
        self.logger.info(f"[PARALLEL] Shared state: {state_file}, lock: {lock_file}")
        self.logger.info(f"[PARALLEL] Workers: {parallel_count}")
        self.crawler.stats.set_value('stf/parallel_workers', parallel_count)

        # Carrega query base
        if not hasattr(self, 'query_array'):
            self.query_array = self.load_query_array()
        if not self.query_array:
            self.logger.error("Nenhuma query encontrada para scraping compartilhado.")
            return
        self.shared_query_info = self.query_array[0]
        self.base_url = self.shared_query_info['url'].split('&page=')[0]

        for i in range(parallel_count):
            yield self.next_page_request(worker_id=i)


    def next_page_request(self, worker_id=0):
        page_number = get_and_increment_page(self._shared_state_file, self._shared_lock_file)
        if page_number is None:
            self.logger.debug(f"[Worker {worker_id}] Paginação finalizada (done=true)")
            return None
        self.logger.debug(f"[Worker {worker_id}] acquired_page={page_number}")
        self.crawler.stats.inc_value('stf/pages_scheduled')
        url = self.base_url + f"&page={page_number}"
        return scrapy.Request(
            url=url,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'query_info': self.shared_query_info,
                'page_number': page_number,
                'worker_id': worker_id,
                'playwright_page_methods': [
                    PageMethod('wait_for_load_state', 'networkidle'),
                    PageMethod('wait_for_function', '''
                        () => {
                            return document.querySelector('div[id^="result-index-"]') ||
                                   document.querySelector('.resultado-pesquisa') ||
                                   document.querySelector('.search-results') ||
                                   document.querySelector('.no-results') ||
                                   document.querySelector('.loading') === null;
                        }
                    ''', timeout=30000),
                ],
                'playwright_context_kwargs': {
                    'ignore_https_errors': True,
                    'extra_http_headers': {
                        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    },
                },
            },
            callback=self.parse_stf_listing_shared,
            errback=self.handle_error
        )

    async def parse_stf_listing_shared(self, response):
        page = response.meta.get("playwright_page")
        page_number = response.meta.get("page_number")
        worker_id = response.meta.get("worker_id")
        query_info = response.meta.get("query_info")
        self.logger.info(f"[Worker {worker_id}] Processando página {page_number} ({response.url})")

        await page.wait_for_function('''
            () => {
                return document.readyState === 'complete' &&
                       (document.querySelector('div[id^="result-index-"]') ||
                        document.querySelector('.no-results') ||
                        document.querySelector('.loading') === null);
            }
        ''', timeout=15000)

        result_items = response.css('div[id^="result-index-"]')
        if not result_items:
            no_results = response.css('.no-results, .sem-resultados, .empty-results').get()
            if no_results:
                self.logger.info(f"[Worker {worker_id}] Nenhum resultado encontrado na página {page_number}.")
                mark_done(self._shared_state_file, self._shared_lock_file)
                self.logger.debug(f"[Worker {worker_id}] mark_done chamado (no_results)")
                return
            self.logger.warning(f"[Worker {worker_id}] Nenhum item encontrado e sem mensagem de fim. Página: {page_number}")
            return

        self.logger.info(f"[Worker {worker_id}] Encontrados {len(result_items)} itens na página {page_number}.")

        # Processamento normal dos itens (mantém lógica existente)
        for i, item in enumerate(result_items):
            pass  # TODO: implementar extração detalhada se necessário

        # Detecta última página: se menos que o esperado por página
        expected_per_page = 10
        if len(result_items) < expected_per_page:
            self.logger.info(f"[Worker {worker_id}] Última página detectada pelo número de itens.")
            mark_done(self._shared_state_file, self._shared_lock_file)
            self.logger.debug(f"[Worker {worker_id}] mark_done chamado (última página)")
            return

        # Agenda próxima página para este worker
        next_req = self.next_page_request(worker_id=worker_id)
        if next_req:
            yield next_req

    def save_groups_to_json(self, total_pages, base_url, query_info):
        """Save page groups to separate JSON files for worker distribution"""
        import json
        from pathlib import Path
        
        if total_pages <= 1:
            # Single page - create one group file
            group_data = {
                "group_id": 1,
                "article": query_info.get('artigo', 'unknown'),
                "query": query_info.get('query', ''),
                "pages": [
                    {
                        "page_number": 1,
                        "url": f"{base_url}&page=1"
                    }
                ]
            }
            
            groups_dir = Path(__file__).parent.parent.parent / 'temp_queue' / 'groups'
            groups_dir.mkdir(exist_ok=True)
            
            group_file = groups_dir / f"group_1_article_{query_info.get('artigo', 'unknown')}.json"
            with open(group_file, 'w', encoding='utf-8') as f:
                json.dump(group_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"📁 Created single group file: {group_file}")
            return [str(group_file)]
        
        # Calculate pages per group
        pages_per_group = max(1, total_pages // self.parallel_groups_count)
        remainder = total_pages % self.parallel_groups_count
        
        groups_dir = Path(__file__).parent.parent.parent / 'temp_queue' / 'groups'
        groups_dir.mkdir(exist_ok=True)
        
        group_files = []
        current_page = 1
        
        for group_idx in range(self.parallel_groups_count):
            # Calculate group size with remainder distribution
            group_size = pages_per_group + (1 if group_idx < remainder else 0)
            
            if current_page <= total_pages:
                # Create pages list for this group
                pages_data = []
                for page_in_group in range(group_size):
                    if current_page <= total_pages:
                        page_url = f"{base_url}&page={current_page}"
                        pages_data.append({
                            "page_number": current_page,
                            "url": page_url
                        })
                        current_page += 1
                
                if pages_data:  # Only create file if group has pages
                    group_data = {
                        "group_id": group_idx + 1,
                        "article": query_info.get('artigo', 'unknown'),
                        "query": query_info.get('query', ''),
                        "pages": pages_data
                    }
                    
                    group_file = groups_dir / f"group_{group_idx + 1}_article_{query_info.get('artigo', 'unknown')}.json"
                    with open(group_file, 'w', encoding='utf-8') as f:
                        json.dump(group_data, f, indent=2, ensure_ascii=False)
                    
                    group_files.append(str(group_file))
                    
                    pages_range = f"{pages_data[0]['page_number']}-{pages_data[-1]['page_number']}"
                    self.logger.info(f"📁 Created Group {group_idx + 1}: {len(pages_data)} pages ({pages_range}) → {group_file.name}")
        
        self.logger.info(f"✅ Created {len(group_files)} group files for parallel worker processing")
        return group_files

    def divide_pages_into_groups(self, total_pages, base_url):
        """Divide pages into 3 groups for simultaneous parallel processing - creates full URLs"""
        if total_pages <= 1:
            return [{"group_index": 0, "urls": [f"{base_url}&page=1"], "pages": [1]}]  # Single page, single group
        
        # Calculate pages per group
        pages_per_group = max(1, total_pages // self.parallel_groups_count)
        remainder = total_pages % self.parallel_groups_count
        
        groups = []
        current_page = 1
        
        for group_idx in range(self.parallel_groups_count):
            # Add extra page to first groups if there's remainder
            group_size = pages_per_group + (1 if group_idx < remainder else 0)
            
            if current_page <= total_pages:
                group_pages = list(range(current_page, min(current_page + group_size, total_pages + 1)))
                if group_pages:  # Only add non-empty groups
                    # Create full URLs for each page in this group
                    group_urls = [f"{base_url}&page={page_num}" for page_num in group_pages]
                    groups.append({
                        "group_index": group_idx,
                        "urls": group_urls,
                        "pages": group_pages
                    })
                current_page += group_size
        
        self.logger.info(f"📊 Divided {total_pages} pages into {len(groups)} SIMULTANEOUS groups:")
        for i, group in enumerate(groups):
            pages = group["pages"]
            self.logger.info(f"   Group {i+1}: pages {pages[0]}-{pages[-1]} ({len(pages)} pages) - WILL RUN CONCURRENTLY")
            self.logger.info(f"   🔗 Group {i+1} first URL: {group['urls'][0]}")
        
        return groups

    def yield_item_with_limit_check(self, item_data):
        """Create and yield an item"""
        return self.create_item(item_data)

    def create_initial_parallel_urls(self, base_url, total_pages):
        """Create initial URLs for 3 parallel groups - each group gets a different starting page"""
        if total_pages <= 1:
            return []  # No parallel processing needed for single page
        
        # Calculate strategic starting pages for 3 groups to avoid overlap
        pages_per_group = max(1, total_pages // self.parallel_groups_count)
        
        # Create exactly 2 additional starting points (page 1 is already being processed)
        additional_urls = []
        starting_pages = []
        
        # Group 1: already processing page 1
        # Group 2: start at middle page
        group2_start = 1 + pages_per_group
        if group2_start <= total_pages:
            group2_url = f"{base_url}&page={group2_start}"
            additional_urls.append(group2_url)
            starting_pages.append(group2_start)
        
        # Group 3: start at final third
        group3_start = 1 + (2 * pages_per_group)
        if group3_start <= total_pages and group3_start != group2_start:
            group3_url = f"{base_url}&page={group3_start}"
            additional_urls.append(group3_url)
            starting_pages.append(group3_start)
        
        self.logger.info(f"🎯 [PARALLEL-GROUPS] Created {len(additional_urls)} additional parallel starting points:")
        self.logger.info(f"   Group 1: already processing page 1")
        for idx, page_num in enumerate(starting_pages, 2):
            self.logger.info(f"   Group {idx}: will start at page {page_num}")
        
        return additional_urls

    def start_requests(self):
        """Generate requests with STF-optimized Playwright settings"""
        for query_info in self.query_array:
            url = query_info['url']
            yield scrapy.Request(
                url=url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'query_info': query_info,  # Pass query info to the request
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        # Try multiple selectors that might indicate loaded results
                        PageMethod('wait_for_function', '''
                            () => {
                                // Wait for any of these indicators that results have loaded
                                return document.querySelector('div[id^="result-index-"]') ||
                                       document.querySelector('.resultado-pesquisa') ||
                                       document.querySelector('.search-results') ||
                                       document.querySelector('.no-results') ||
                                       document.querySelector('.loading') === null;
                            }
                        ''', timeout=30000),
                    ],
                    'playwright_context_kwargs': {
                        'ignore_https_errors': True,
                        'extra_http_headers': {
                            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        },
                    },
                },
                callback=self.parse_stf_listing,
                errback=self.handle_error
            )

    async def parse_stf_listing(self, response):
        """Parse STF search results page"""
        page = response.meta.get("playwright_page")
        query_info = response.meta.get("query_info")
        page_number = response.meta.get("page_number", 1)
        group_index = response.meta.get("group_index")
        
        # Store current query info for this request
        self.current_query_info = query_info

        try:
            self.logger.info(f"Parsing STF listing for Article {query_info['artigo']}: {response.url}")

            # Extract current page number and total pages on first load
            if self.total_pages is None:
                await self.extract_pagination_info(page, response)

            # Wait for page to be fully interactive and check what we actually have
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('div[id^="result-index-"]') ||
                            document.querySelector('.no-results') ||
                            document.querySelector('.loading') === null);
                }
            ''', timeout=15000)

            # Log page title and basic info for debugging
            page_title = await page.title()
            self.logger.info(f"Page title: {page_title}")

            # Try multiple possible selectors for result items
            result_selectors = [
                'div[id^="result-index-"]'
            ]

            result_items = []
            for selector in result_selectors:
                result_items = response.css(selector)
                if result_items:
                    if group_index is not None:
                        self.logger.info(f"🎯 [PARALLEL] Group {group_index + 1} found {len(result_items)} items on page {page_number} with selector: {selector}")
                    else:
                        self.logger.info(f"🎯 [INITIAL] Found {len(result_items)} items on page {page_number} with selector: {selector}")
                    break

            if not result_items:
                # Check if there's a "no results" message or if we need to wait more
                no_results = response.css('.no-results, .sem-resultados, .empty-results').get()
                if no_results:
                    self.logger.warning("No results found - empty result set")
                else:
                    # Let's see what's actually on the page
                    page_content = await page.content()
                    self.logger.warning(f"No result items found. Page content length: {len(page_content)}")

                    # Try to find any clickable links that might be results
                    all_links = response.css('a[href]::attr(href)').getall()
                    self.logger.info(f"Found {len(all_links)} total links on page")

                    # Look for clipboard-like or processo-like links
                    clipboard_links = [link for link in all_links if 'clipboard' in link.lower()]
                    processo_links = [link for link in all_links if 'processo' in link.lower()]

                    self.logger.info(f"Found {len(clipboard_links)} clipboard-like links")
                    self.logger.info(f"Found {len(processo_links)} processo-like links")

                # Check for next page using new strategy
                async for next_page_request in self.handle_pagination_new_strategy(response, query_info):
                    yield next_page_request
                return

            # Count how many items we need to process for this page
            items_to_process = len(result_items)
            self.total_items_on_current_page = items_to_process
            self.items_processed_on_current_page = 0
            self.logger.info(f"📊 Starting to process {items_to_process} items on page {self.current_page_number}/{self.total_pages or '?'}")

            # Process each result item and yield detailed requests
            for i, item in enumerate(result_items):
                # Check if we've reached the maximum number of items (only in dev mode)
                if self.dev_mode and self.max_items is not None and self.items_extracted >= self.max_items:
                    self.logger.info(f"🛑 DEV MODE: Reached maximum items limit ({self.max_items}). Skipping pagination.")
                    return
                
                if self.dev_mode:
                    self.logger.info(f"Processing item {i+1}/{len(result_items)} (DEV MODE: {self.items_extracted}/{self.max_items})")
                else:
                    self.logger.info(f"Processing item {i+1}/{len(result_items)} (PROD MODE: {self.items_extracted} extracted)")

                # First, let's debug what elements we actually have in each item
                item_html = item.get()
                self.logger.debug(f"Item {i+1} HTML length: {len(item_html)}")
                
                # Log all links in this item for debugging
                all_item_links = item.css('a::attr(href)').getall()
                self.logger.info(f"Item {i+1} has {len(all_item_links)} links")
                
                # Extract the main decision data link and title based on the specific structure
                # Looking for: <a mattooltip="Dados completos" ... href="/pages/search/despacho1583260/false">
                #              <div class="ng-star-inserted"><h4 class="ng-star-inserted">RHC 247645</h4>
                
                decision_data_link = None
                title = None
                case_number_from_url = None
                
                # Extract decision data link with title
                decision_link_selector = 'a[mattooltip="Dados completos"]'
                decision_element = item.css(decision_link_selector)
                
                if decision_element:
                    # Get the href for complete decision data
                    decision_data_link = decision_element.css('::attr(href)').get()
                    if decision_data_link:
                        decision_data_link = decision_data_link.strip()
                        self.logger.info(f"✅ Found decision data link: {decision_data_link}")
                        
                        # Extract case number from URL pattern /pages/search/%case_number%/false
                        import re
                        url_match = re.search(r'/pages/search/([^/]+)/false', decision_data_link)
                        if url_match:
                            case_number_from_url = url_match.group(1)
                            self.logger.info(f"✅ Extracted case number from URL: {case_number_from_url}")
                    
                    # Get the title from h4 inside the link
                    title_element = decision_element.css('div.ng-star-inserted h4.ng-star-inserted::text').get()
                    if title_element:
                        title = title_element.strip()
                        self.logger.info(f"✅ Found title: {title}")
                
                # Fallback selectors if the main structure is not found
                if not title:
                    title_selectors = ['h2::text', 'h3::text', 'h4::text', '.titulo::text', '.ementa::text', '.title::text']
                    for selector in title_selectors:
                        title = item.css(selector).get()
                        if title:
                            title = title.strip()
                            self.logger.debug(f"Found title with fallback selector {selector}: {title[:50]}...")
                            break
                
                if not decision_data_link:
                    # Fallback to any link that might contain decision data
                    fallback_selectors = [
                        'a[href*="/pages/search/"]::attr(href)',
                        'a[href*="despacho"]::attr(href)',
                        'a[href*="processo"]::attr(href)'
                    ]
                    for selector in fallback_selectors:
                        decision_data_link = item.css(selector).get()
                        if decision_data_link:
                            self.logger.debug(f"Found decision link with fallback selector: {decision_data_link}")
                            break

                # Create initial item data
                item_data = {
                    'title': title or f"Item {i+1}",
                    'case_number': case_number_from_url,
                    'source_url': response.url,
                    'scraped_at': datetime.now().isoformat(),
                    'item_index': i+1,
                    'current_article': self.current_query_info.get('artigo', 'unknown') if hasattr(self, 'current_query_info') and self.current_query_info else 'unknown',
                    'query_text': self.current_query_info.get('query', '') if hasattr(self, 'current_query_info') and self.current_query_info else '',
                    # Improved pagination tracking
                    'page_info': {
                        'page_url': response.url,
                        'query_info': query_info,
                        'item_index': i+1,
                        'total_items': items_to_process
                    }
                }

                # If we have a decision data link, follow it to get detailed content
                if decision_data_link:
                    detail_url = response.urljoin(decision_data_link)
                    self.logger.info(f"Following detail URL for item {i+1}: {detail_url}")
                    
                    yield scrapy.Request(
                        url=detail_url,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'playwright_page_methods': [
                                PageMethod('wait_for_load_state', 'networkidle'),
                                PageMethod('wait_for_function', '''
                                    () => {
                                        return document.readyState === 'complete' &&
                                               (document.querySelector('#decisaoTexto') ||
                                                document.querySelector('.header-icons') ||
                                                document.querySelector('.mat-icon') !== null);
                                    }
                                ''', timeout=30000),
                            ],
                            'item_data': item_data,
                        },
                        callback=self.parse_decision_detail,
                        errback=self.handle_error
                    )
                else:
                    self.logger.warning(f"❌ Item {i+1}: No decision data link found, skipping detailed extraction")
                    # Still yield a basic item
                    item_data['content'] = f"STF Item {i+1} - No decision data link available"
                    item_data['extraction_method'] = 'no-detail-link'
                    
                    # Create the item
                    created_item = self.yield_item_with_limit_check(item_data)
                    yield created_item
                    
                    # Track processed items
                    self.items_processed_on_current_page += 1

            self.logger.info(f"✅ Completed yielding {items_to_process} detail requests.")

        finally:
            if page:
                await page.close()

    async def parse_decision_detail(self, response):
        """Parse the detailed decision page to extract full content"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})

        try:
            self.logger.info(f"Parsing decision detail page: {response.url}")

            # Wait for page to be fully loaded
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('#decisaoTexto') ||
                            document.querySelector('.header-icons') ||
                            document.querySelector('.mat-icon') !== null);
                }
            ''', timeout=15000)

            # Extract full content using the clipboard button
            clipboard_content = await page.evaluate('''
                (async () => {
                    // Look for the clipboard button in header-icons section
                    const headerIcons = document.querySelector('.header-icons.hide-in-print');
                    let clipboardBtn = null;
                    
                    if (headerIcons) {
                        // Try to find the clipboard icon by different methods
                        clipboardBtn = headerIcons.querySelector('mat-icon[mattooltip*="Copiar"]') ||
                                     headerIcons.querySelector('mat-icon:contains("file_copy")') ||
                                     headerIcons.querySelector('mat-icon.clipboard-result') ||
                                     Array.from(headerIcons.querySelectorAll('mat-icon')).find(icon => 
                                         icon.textContent.trim() === 'file_copy' || 
                                         icon.getAttribute('mattooltip')?.includes('Copiar')
                                     );
                    }
                    
                    // Fallback: try xpath or other selectors
                    if (!clipboardBtn) {
                        const xpath = '/html/body/app-root/app-home/main/app-search-detail/div/div/div[1]/div/div[1]/div[2]/div/mat-icon[4]';
                        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                        clipboardBtn = result.singleNodeValue;
                    }
                    
                    if (!clipboardBtn) {
                        console.log('No clipboard button found');
                        return null;
                    }
                    
                    // Store original clipboard content
                    let originalClipboard = '';
                    try {
                        originalClipboard = await navigator.clipboard.readText();
                    } catch(e) {
                        console.log('Could not read original clipboard:', e);
                    }
                    
                    // Click the clipboard button
                    console.log('Clicking clipboard button...');
                    clipboardBtn.click();
                    
                    // Wait for clipboard to be populated
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    // Try to read the clipboard content
                    try {
                        const clipboardText = await navigator.clipboard.readText();
                        if (clipboardText && clipboardText !== originalClipboard) {
                            console.log('Successfully copied content to clipboard:', clipboardText.length, 'characters');
                            return {
                                content: clipboardText,
                                source: 'clipboard-detail-page'
                            };
                        }
                    } catch(e) {
                        console.log('Could not read clipboard after click:', e);
                    }
                    
                    return null;
                })();
            ''')

            # Extract specific sections from the page
            # 1. Extract "Partes" information - using XPath for better targeting
            # Target: <div fxlayout="column" class="jud-text ng-star-inserted"><h4>Partes</h4><div class="text-pre-wrap">...</div></div>
            partes_elements = response.xpath('//h4[text()="Partes"]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()
            if not partes_elements:
                # Alternative XPath - look for any h4 containing "Partes"
                partes_elements = response.xpath('//h4[contains(text(), "Partes")]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()
            
            partes_text = ' '.join([p.strip() for p in partes_elements if p.strip()]) if partes_elements else None
            self.logger.debug(f"Partes extraction: found {len(partes_elements) if partes_elements else 0} elements")

            # 2. Extract decision text from div with id="decisaoTexto"
            decision_element = response.css('#decisaoTexto ::text').getall()
            decision_text = ' '.join([d.strip() for d in decision_element if d.strip()]) if decision_element else None
            self.logger.debug(f"Decision extraction: found {len(decision_element) if decision_element else 0} elements")

            # 3. Extract legislation from div with class="text-pre-wrap" under Legislação section
            # Using XPath to target the specific Legislação section
            legislacao_elements = response.xpath('//h4[text()="Legislação"]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()
            if not legislacao_elements:
                # Alternative XPath
                legislacao_elements = response.xpath('//h4[contains(text(), "Legislação")]/following-sibling::div[@class="text-pre-wrap"]//text()').getall()
            
            legislacao_text = ' '.join([l.strip() for l in legislacao_elements if l.strip()]) if legislacao_elements else None
            self.logger.debug(f"Legislacao extraction: found {len(legislacao_elements) if legislacao_elements else 0} elements")

            # Update item data with extracted content
            if clipboard_content and clipboard_content.get('content'):
                full_content = clipboard_content['content']
                item_data['content'] = full_content
                item_data['content_length'] = len(full_content)
                item_data['extraction_method'] = 'clipboard-detail-page'
                self.logger.info(f"✅ Extracted {len(full_content)} characters from clipboard")
            else:
                # Fallback: try to extract content from visible elements
                fallback_content = response.css('main ::text, .content ::text, .decisao ::text').getall()
                fallback_text = ' '.join([c.strip() for c in fallback_content if c.strip()])[:5000]  # Limit to first 5000 chars
                item_data['content'] = fallback_text or "Content extraction failed"
                item_data['extraction_method'] = 'fallback-detail-page'
                self.logger.warning("❌ Clipboard extraction failed, using fallback content")

            # Add the new extracted fields
            item_data['partes'] = partes_text
            item_data['decision'] = decision_text
            item_data['legislacao'] = legislacao_text
            item_data['detail_url'] = response.url

            # Log what we extracted
            self.logger.info(f"Extracted details - Partes: {'✅' if partes_text else '❌'}, Decision: {'✅' if decision_text else '❌'}, Legislacao: {'✅' if legislacao_text else '❌'}")


            # Create and yield the item
            created_item = self.yield_item_with_limit_check(item_data)
            yield created_item

            # Track processed items and handle pagination with new strategy
            self.items_processed_on_current_page += 1
            page_info = item_data.get('page_info', {})
            
            # Check if we've processed all items on this page
            if self.items_processed_on_current_page >= self.total_items_on_current_page:
                self.logger.info(f"📄 Processed all {self.items_processed_on_current_page}/{self.total_items_on_current_page} items on page {self.current_page_number}. Checking for next page...")
                
                query_info = page_info.get('query_info')
                if query_info:
                    # Use new pagination strategy
                    async for next_page_request in self.handle_pagination_new_strategy(response, query_info):
                        yield next_page_request

        except Exception as e:
            self.logger.error(f"Error parsing decision detail: {e}")
            # Still try to yield the basic item and handle pagination
            item_data['content'] = f"Error extracting detailed content: {str(e)}"
            item_data['extraction_method'] = 'error'
            
            created_item = self.yield_item_with_limit_check(item_data)
            yield created_item
            
            # Track processed items even on error
            self.items_processed_on_current_page += 1
            
            # Handle pagination even if there was an error
            if self.items_processed_on_current_page >= self.total_items_on_current_page:
                page_info = item_data.get('page_info', {})
                query_info = page_info.get('query_info')
                
                if query_info:
                    async for next_page_request in self.handle_pagination_new_strategy(response, query_info):
                        yield next_page_request

        finally:
            if page:
                await page.close()

    async def extract_pagination_info(self, page, response):
        """Extract pagination information from the page"""
        try:
            self.logger.info("🔍 Extracting pagination information...")
            
            # Wait for pagination element to be available
            await page.wait_for_function('''
                () => {
                    return document.querySelector('span') !== null;
                }
            ''', timeout=10000)
            
            # Extract pagination text using XPath
            pagination_xpath = '/html/body/app-root/app-home/main/search/div/div/div/div[2]/paginator/nav/div/span'
            pagination_element = await page.query_selector(f'xpath={pagination_xpath}')
            
            if pagination_element:
                pagination_text = await pagination_element.text_content()
                self.logger.info(f"📄 Found pagination text: '{pagination_text}'")
                
                # Extract total pages from text like "1 de 2", "2 de 5", " de 2", etc.
                import re
                # Handle cases where current page might be missing (like " de 2")
                match = re.search(r'(\d+)?\s*de\s+(\d+)', pagination_text.strip())
                if match:
                    current_page_str = match.group(1)
                    total_pages_str = match.group(2)
                    
                    # If current page is missing, assume we're on page 1
                    current_page = int(current_page_str) if current_page_str else 1
                    total_pages = int(total_pages_str)
                    
                    self.current_page_number = current_page
                    self.total_pages = total_pages
                    
                    self.logger.info(f"✅ Extracted pagination: current page {current_page}, total pages {total_pages}")
                    
                    # Log examples of what this means for pagination
                    if total_pages > 1:
                        remaining_pages = list(range(current_page + 1, total_pages + 1))
                        self.logger.info(f"📋 Will navigate through pages: {remaining_pages}")
                    else:
                        self.logger.info("📋 Only one page available - no pagination needed")
                    
                    # Store base URL for pagination
                    current_url = response.url
                    # Remove page parameter from URL to create base URL
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(current_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    
                    # Remove existing page parameter
                    if 'page' in query_params:
                        del query_params['page']
                    
                    # Reconstruct base URL without page parameter
                    new_query = urllib.parse.urlencode(query_params, doseq=True)
                    self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{new_query}"
                    
                    self.logger.info(f"📦 Base URL for pagination: {self.base_url}")
                else:
                    self.logger.warning(f"❌ Could not parse pagination text: '{pagination_text}' - Expected format: 'X de Y' or ' de Y'")
                    self.current_page_number = 1
                    self.total_pages = 1
            else:
                self.logger.warning("❌ Pagination element not found")
                # Fallback: assume single page
                self.current_page_number = 1
                self.total_pages = 1
                
        except Exception as e:
            self.logger.error(f"❌ Error extracting pagination info: {e}")
            # Fallback: assume single page
            self.current_page_number = 1
            self.total_pages = 1

    async def handle_pagination_new_strategy(self, response, query_info):
        """Handle pagination using URL modification strategy - works for any number of pages"""
        try:
            # Check if we have more pages to process
            if self.total_pages is None or self.current_page_number >= self.total_pages:
                self.logger.info(f"🏁 Reached last page ({self.current_page_number}/{self.total_pages or '?'}). Pagination complete.")
                return
            
            # Calculate next page number
            next_page = self.current_page_number + 1
            
            # Check dev mode limits
            if self.dev_mode and self.max_items is not None and self.items_extracted >= self.max_items:
                self.logger.info(f"🛑 DEV MODE: Reached maximum items limit ({self.max_items}). Stopping pagination.")
                return
            
            self.logger.info(f"➡️ Moving to next page: {next_page}/{self.total_pages}")
            
            # Construct next page URL by appending page parameter
            next_page_url = f"{self.base_url}&page={next_page}"
            
            self.logger.info(f"🌐 Next page URL: {next_page_url}")
            
            # Update current page number for next iteration
            self.current_page_number = next_page
            
            # Reset page tracking counters
            self.items_processed_on_current_page = 0
            self.total_items_on_current_page = 0
            
            # Log progress
            pages_remaining = self.total_pages - next_page
            self.logger.info(f"📊 Progress: Page {next_page}/{self.total_pages} ({pages_remaining} pages remaining)")
            
            # Create request for next page
            yield scrapy.Request(
                url=next_page_url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'query_info': query_info,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_function', '''
                            () => {
                                return document.querySelector('div[id^="result-index-"]') ||
                                       document.querySelector('.no-results') ||
                                       document.querySelector('.loading') === null;
                            }
                        ''', timeout=30000),
                    ],
                },
                callback=self.parse_stf_listing,
                errback=self.handle_error,
                dont_filter=True
            )
            
            self.logger.info(f"🔄 Next page request created for page {next_page}")
            
        except Exception as e:
            self.logger.error(f"❌ Error in new pagination strategy: {e}")


    async def extract_pdf_links(self, response):
        """Extract PDF download links from STF processo page"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})

        try:
            self.logger.info(f"Extracting PDF links: {response.url}")

            # Wait for the page to be fully loaded
            await page.wait_for_function('''
                () => {
                    return document.readyState === 'complete' &&
                           (document.querySelector('a[href*="pdf"]') ||
                            document.querySelector('a[href*="downloadPeca"]') ||
                            document.querySelector('.no-pdfs') ||
                            document.links.length > 0);
                }
            ''', timeout=15000)

            # Extract PDF links with multiple strategies
            pdf_selectors = [
                'a[href$=".pdf"]::attr(href)',
                'a[title*="PDF"]::attr(href)',
                'a[title*="pdf"]::attr(href)',
                'a[title*="Pdf"]::attr(href)',
                'a[href*="pdf"]::attr(href)',
                'a[href*="PDF"]::attr(href)',
                'a[href*="downloadPeca.asp"]::attr(href)',
                'a[class*="pdf"]::attr(href)',
                'a[class*="PDF"]::attr(href)',
                'a[onclick*="pdf"]::attr(href)',
                'a[onclick*="PDF"]::attr(href)'
            ]

            pdf_links = []
            for selector in pdf_selectors:
                found_links = response.css(selector).getall()
                if found_links:
                    self.logger.debug(f"Found {len(found_links)} PDF links with selector: {selector}")
                    pdf_links.extend(found_links)

            # Remove duplicates and convert to absolute URLs
            pdf_links = list(set(pdf_links))  # Remove duplicates
            if pdf_links:
                absolute_pdf_links = [response.urljoin(link) for link in pdf_links]
                item_data['pdf_links'] = absolute_pdf_links
                item_data['pdf_count'] = len(absolute_pdf_links)
                self.logger.info(f"Found {len(absolute_pdf_links)} PDF links")
            else:
                self.logger.warning("No PDF links found")
                item_data['pdf_links'] = []
                item_data['pdf_count'] = 0

            # Extract additional metadata from processo page with flexible selectors
            relator_selectors = ['.relator::text', '.ministro::text', '.judge::text', '[class*="relator"]::text']
            for selector in relator_selectors:
                relator = response.css(selector).get()
                if relator:
                    item_data['relator'] = relator.strip()
                    break

            date_selectors = ['.data-julgamento::text', '.data-decisao::text', '.date::text', '[class*="data"]::text']
            for selector in date_selectors:
                decision_date = response.css(selector).get()
                if decision_date:
                    item_data['decision_date'] = decision_date.strip()
                    break

            yield self.yield_item_with_limit_check(item_data)

        except Exception as e:
            self.logger.error(f"Error extracting PDF links: {e}")
            # Still yield the item even if PDF extraction failed
            yield self.yield_item_with_limit_check(item_data)

        finally:
            if page:
                await page.close()

    def create_item(self, item_data):
        """Create a legal document item"""
        item = JurisprudenciaItem()

        # Map data to item fields with new structured naming
        if self.current_query_info:
            article_number = self.current_query_info.get('artigo', 'unknown')
            query_text = self.current_query_info.get('query', '')
            
            item['cluster_name'] = f"art_{article_number}"
            item['cluster_description'] = f"{query_text} (art. {article_number} do Código Penal)"
            item['article_reference'] = f"CP art. {article_number}"
            item['source'] = f"TRF 4ª Região - {item['cluster_name']}"
        else:
            item['cluster_name'] = 'trf4_jurisprudencia'
            item['cluster_description'] = 'Jurisprudência TRF 4ª Região'
            item['article_reference'] = 'N/A'
            item['source'] = 'TRF 4ª Região'
        item['title'] = item_data.get('title', f"TRF 4ª Região Item {item_data.get('item_index', 'Unknown')}")
        item['case_number'] = item_data.get('case_number', '')
        item['content'] = item_data.get('content', item_data.get('clipboard_content', ''))
        item['url'] = item_data.get('detail_url', '') or item_data.get('full_decision_data', '') or item_data.get('processo_link', '') or item_data.get('source_url', '')
        item['tribunal'] = 'TRF 4ª Região'
        item['legal_area'] = 'Penal'  # Based on search query
        
        # Extract classe processual unificada from the current query URL
        current_url = self.current_query_info['url'] if self.current_query_info else ''
        item['classe_processual_unificada'] = get_classe_processual_from_url(current_url)

        # Extract fields from content
        content = item_data.get('content', item_data.get('clipboard_content', ''))
        if content:
            item['relator'] = extract_relator_from_content(content)
            item['publication_date'] = extract_publication_date_from_content(content)
            item['decision_date'] = extract_decision_date_from_content(content)
            
            # If partes wasn't extracted from page elements, try to extract from content
            if not item_data.get('partes'):
                item['partes'] = extract_partes_from_content(content)

        # Add new detailed fields
        item['partes'] = item_data.get('partes', '') or item.get('partes', '')
        item['decision'] = item_data.get('decision', '')
        item['legislacao'] = item_data.get('legislacao', '')
        

        # Increment the items counter
        self.items_extracted += 1
        
        if self.dev_mode:
            self.logger.info(f"✅ DEV MODE: Created item {self.items_extracted}/{self.max_items}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        else:
            self.logger.info(f"✅ PROD MODE: Created item {self.items_extracted}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")
        if content:
            item['relator'] = extract_relator_from_content(content)
            item['publication_date'] = extract_publication_date_from_content(content)
            item['decision_date'] = extract_decision_date_from_content(content)
            
            # If partes wasn't extracted from page elements, try to extract from content
            if not item_data.get('partes'):
                item['partes'] = extract_partes_from_content(content)

        # Add new detailed fields
        item['partes'] = item_data.get('partes', '') or item.get('partes', '')
        item['decision'] = item_data.get('decision', '')
        item['legislacao'] = item_data.get('legislacao', '')
        

        # Increment the items counter
        self.items_extracted += 1
        
        if self.dev_mode:
            self.logger.info(f"✅ DEV MODE: Created item {self.items_extracted}/{self.max_items}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        else:
            self.logger.info(f"✅ PROD MODE: Created item {self.items_extracted}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")
        item['legislacao'] = item_data.get('legislacao', '')
        

        # Increment the items counter
        self.items_extracted += 1
        
        if self.dev_mode:
            self.logger.info(f"✅ DEV MODE: Created item {self.items_extracted}/{self.max_items}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        else:
            self.logger.info(f"✅ PROD MODE: Created item {self.items_extracted}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")
        if content:
            item['relator'] = extract_relator_from_content(content)
            item['publication_date'] = extract_publication_date_from_content(content)
            item['decision_date'] = extract_decision_date_from_content(content)
            
            # If partes wasn't extracted from page elements, try to extract from content
            if not item_data.get('partes'):
                item['partes'] = extract_partes_from_content(content)

        # Add new detailed fields
        item['partes'] = item_data.get('partes', '') or item.get('partes', '')
        item['decision'] = item_data.get('decision', '')
        item['legislacao'] = item_data.get('legislacao', '')
        

        # Increment the items counter
        self.items_extracted += 1
        
        if self.dev_mode:
            self.logger.info(f"✅ DEV MODE: Created item {self.items_extracted}/{self.max_items}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        else:
            self.logger.info(f"✅ PROD MODE: Created item {self.items_extracted}: {item.get('title', 'No title')} - Classe: {item.get('classe_processual_unificada', 'Unknown')} - Relator: {item.get('relator', 'Unknown')}")
        
        return item

    async def handle_error(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url} - {failure.value}")

        # Close page if it exists
        page = failure.request.meta.get('playwright_page')
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.debug(f"Error closing page: {e}")
