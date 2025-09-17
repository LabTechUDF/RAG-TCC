"""
STF Jurisprudência Spider - Focused on extracting clipboard content and PDFs from STF decisões
"""

import re
import json
import scrapy
import os
from datetime import datetime
from pathlib import Path
from scrapy.exceptions import CloseSpider
from scrapy_playwright.page import PageMethod
from stf_scraper.items import (
    JurisprudenciaItem, 
    get_classe_processual_from_url,
    extract_relator_from_content,
    extract_publication_date_from_content,
    extract_decision_date_from_content,
    extract_partes_from_content
)
from pdb import set_trace


class StfJurisprudenciaSpider(scrapy.Spider):
    """Focused spider for STF jurisprudência content and PDF extraction"""

    name = 'stf_jurisprudencia'
    allowed_domains = ['jurisprudencia.stf.jus.br']

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load query array from JSON file
        self.query_array = self.load_query_array()
        self.current_query_info = None
        
        # Generate start_urls from query array
        self.start_urls = [item['url'] for item in self.query_array]
        
        # Add pagination tracking with parallel page strategy
        self.items_processed_on_current_page = 0
        self.total_items_on_current_page = 0
        self.current_page_number = 1
        self.total_pages = None
        self.base_url = None  # Store base URL without page parameter
        
        # Parallel page processing variables
        self.page_groups = []  # Will store groups of pages for parallel processing
        self.parallel_groups_count = 3  # 3 groups for safe parallel processing
        self.pages_processed = set()  # Track which pages have been processed
        self.initial_parallel_processing_started = False  # Track if we've started parallel processing
        
        # Check processing mode
        self.discovery_mode = kwargs.get('discovery_mode', '').lower() in ['true', '1', 'yes']
        self.worker_id = kwargs.get('worker_id', None)
        self.group_file = kwargs.get('group_file', None)
        
        if self.discovery_mode:
            self.logger.info("🔍 Running in DISCOVERY mode - will generate group files")
        elif self.group_file:
            self.logger.info(f"👷 Running in GROUP mode - Worker {self.worker_id} processing specific group")
        else:
            self.logger.info("🚀 Running in STANDARD mode")
        
        # Check if we're in development mode
        # Can be set via environment variable or spider argument
        self.dev_mode = (
            kwargs.get('dev_mode', '').lower() in ['true', '1', 'yes'] or
            os.getenv('SPIDER_DEV_MODE', '').lower() in ['true', '1', 'yes'] or
            os.getenv('ENV', '').lower() in ['dev', 'development']
        )
        
        if self.dev_mode:
            self.items_extracted = 0
            self.max_items = 5
            self.logger.info("🚧 Running in DEVELOPMENT mode - limited to 5 items")
            # Set the Scrapy built-in item count limit as backup
            self.custom_settings['CLOSESPIDER_ITEMCOUNT'] = 5
        else:
            self.items_extracted = 0
            self.max_items = None  # No limit in production
            self.logger.info("🚀 Running in PRODUCTION mode - no item limit")
            # Remove any item count limit
            if 'CLOSESPIDER_ITEMCOUNT' in self.custom_settings:
                del self.custom_settings['CLOSESPIDER_ITEMCOUNT']

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
            # Enhanced logging for parallel processing tracking
            if group_index is not None:
                group_name = f"Group {group_index + 1}"
                self.logger.info(f"🎯 [PARALLEL] Processing page {page_number} from {group_name} | Article {query_info['artigo']}")
                self.logger.info(f"📍 [PARALLEL] URL: {response.url}")
                self.logger.info(f"⚡ [PARALLEL] This page is running concurrently with other groups!")
            else:
                self.logger.info(f"🎯 [INITIAL] Processing first page for Article {query_info['artigo']}")
                self.logger.info(f"📍 [INITIAL] URL: {response.url}")
                self.logger.info(f"🚀 [INITIAL] This will trigger parallel processing of remaining pages")

            # Extract current page number and total pages on first load
            if self.total_pages is None:
                await self.extract_pagination_info(page, response)
                
                # Start immediate parallel processing if this is the first page and we have multiple pages
                if (page_number == 1 and self.total_pages and self.total_pages > 1 and 
                    not self.initial_parallel_processing_started and group_index is None):
                    
                    self.logger.info(f"🚀 [GROUP-DISCOVERY] Pagination discovered! Saving groups to JSON files")
                    self.logger.info(f"🎯 [GROUP-DISCOVERY] Total pages found: {self.total_pages}")
                    
                    # Save groups to JSON files for worker distribution
                    if self.base_url:
                        group_files = self.save_groups_to_json(self.total_pages, self.base_url, query_info)
                        self.logger.info(f"📁 [GROUP-DISCOVERY] Created {len(group_files)} group files for workers")
                        
                        # Signal to workers that groups are ready
                        self.logger.info(f"🔔 [GROUP-DISCOVERY] Groups ready for worker distribution:")
                        for i, group_file in enumerate(group_files, 1):
                            self.logger.info(f"   Worker-{i-1} → {Path(group_file).name}")
                        
                        self.initial_parallel_processing_started = True
                        self.logger.info(f"✅ [GROUP-DISCOVERY] Group files created! Workers can now process in parallel")
                        
                        # If in discovery mode, stop processing after creating groups
                        if self.discovery_mode:
                            self.logger.info(f"🛑 [GROUP-DISCOVERY] Discovery mode complete - terminating spider")
                            return

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

                # Check for next page using new strategy - yield all parallel requests at once
                parallel_requests = self.handle_pagination_new_strategy(response, query_info)
                for next_page_request in parallel_requests:
                    yield next_page_request
                return

            # Count how many items we need to process for this page
            items_to_process = len(result_items)
            self.total_items_on_current_page = items_to_process
            self.items_processed_on_current_page = 0
            if group_index is not None:
                self.logger.info(f"📊 [PARALLEL] Group {group_index + 1} starting to process {items_to_process} items on page {page_number}/{self.total_pages or '?'}")
                self.logger.info(f"⚡ [PARALLEL] This is running CONCURRENTLY with other groups!")
            else:
                self.logger.info(f"📊 [INITIAL] Starting to process {items_to_process} items on page {page_number}/{self.total_pages or '?'}")

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

            # Now try to extract the RTF file by following the process tracking flow
            self.logger.info(f"🔍 Before RTF extraction - rtf_url: {item_data.get('rtf_url', 'NOT_SET')}, rtf_file_path: {item_data.get('rtf_file_path', 'NOT_SET')}")
            await self.extract_rtf_file(page, item_data, response)
            self.logger.info(f"🔍 After RTF extraction - rtf_url: {item_data.get('rtf_url', 'NOT_SET')}, rtf_file_path: {item_data.get('rtf_file_path', 'NOT_SET')}")

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
                    
                    # Divide pages into groups for parallel processing with URLs
                    if total_pages > 1:
                        self.page_groups = self.divide_pages_into_groups(total_pages, self.base_url)
                        self.logger.info(f"⚡ Prepared {len(self.page_groups)} parallel groups for SIMULTANEOUS processing")
                    else:
                        self.page_groups = [{"group_index": 0, "urls": [f"{self.base_url}&page=1"], "pages": [1]}]
                        self.logger.info("📋 Only one page available - no parallel processing needed")
                    
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

    def handle_pagination_new_strategy(self, response, query_info):
        """Handle pagination using native Scrapy parallelism - yields ALL page groups simultaneously"""
        requests = []
        try:
            # Check if we have page groups to process
            if not self.page_groups:
                self.logger.info(f"🏁 No page groups to process. Pagination complete.")
                return requests
            
            # Check dev mode limits
            if self.dev_mode and self.max_items is not None and self.items_extracted >= self.max_items:
                self.logger.info(f"🛑 DEV MODE: Reached maximum items limit ({self.max_items}). Stopping pagination.")
                return requests
            
            self.logger.info(f"🚀 [PARALLEL-INIT] Starting SIMULTANEOUS processing of ALL {len(self.page_groups)} page groups")
            
            # Count total pages across all groups
            total_pages_to_process = sum(len(group["pages"]) for group in self.page_groups)
            self.logger.info(f"⚡ [PARALLEL-INIT] This will run {total_pages_to_process} pages CONCURRENTLY")
            
            # Generate requests for ALL page groups SIMULTANEOUSLY using pre-built URLs
            for group_data in self.page_groups:
                group_idx = group_data["group_index"]
                group_urls = group_data["urls"]
                group_pages = group_data["pages"]
                
                group_name = f"Group {group_idx + 1}"
                self.logger.info(f"📦 [PARALLEL-INIT] {group_name}: pages {group_pages[0]}-{group_pages[-1]} ({len(group_pages)} pages) - RUNNING NOW!")
                
                for url_idx, page_url in enumerate(group_urls):
                    page_num = group_pages[url_idx]
                    
                    # Skip page 1 as it's already being processed
                    if page_num == 1:
                        self.pages_processed.add(page_num)
                        self.logger.info(f"⏭️  [PARALLEL-INIT] Skipping page {page_num} (already being processed)")
                        continue
                    
                    # Skip if already processed
                    if page_num in self.pages_processed:
                        self.logger.info(f"⏭️  [PARALLEL-INIT] Skipping page {page_num} (already processed)")
                        continue
                    
                    self.logger.info(f"🌐 [PARALLEL-INIT] Creating request for page {page_num} ({group_name}) - CONCURRENT")
                    self.logger.info(f"🔗 [PARALLEL-INIT] URL: {page_url}")
                    
                    # Mark as processed to avoid duplicates
                    self.pages_processed.add(page_num)
                    
                    # Create request for this page using pre-built URL
                    request = scrapy.Request(
                        url=page_url,
                        meta={
                            'playwright': True,
                            'playwright_include_page': True,
                            'query_info': query_info,
                            'page_number': page_num,
                            'group_index': group_idx,
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
                    requests.append(request)
            
            # Log summary with group-specific information
            total_pages_to_process = sum(len(group["pages"]) for group in self.page_groups)
            self.logger.info(f"🎯 PARALLEL EXECUTION SUMMARY:")
            self.logger.info(f"   ⚡ CONCURRENT GROUPS: {len(self.page_groups)} groups running SIMULTANEOUSLY")
            self.logger.info(f"   📊 TOTAL PAGES: {total_pages_to_process} pages")  
            self.logger.info(f"   🚀 CONCURRENT REQUESTS: {len(requests)} requests YIELDED AT ONCE")
            self.logger.info(f"   🔥 MAX CONCURRENCY: Up to {len(requests)} pages processing in parallel")
            
            # Log specific pages being processed per group
            for group_data in self.page_groups:
                group_idx = group_data["group_index"]
                group_pages = group_data["pages"]
                req_count = len([p for p in group_pages if p != 1])  # Exclude page 1 since it's already processing
                self.logger.info(f"   - Group {group_idx + 1}: {req_count} requests (pages {group_pages[0]}-{group_pages[-1]})")
            
            # Clear page groups to prevent re-processing
            self.page_groups = []
            
            return requests
            
        except Exception as e:
            self.logger.error(f"❌ Error in parallel pagination strategy: {e}")
            return requests

    async def extract_rtf_file(self, page, item_data, response):
        """Extract RTF file by following the process tracking flow"""
        try:
            self.logger.info("Starting RTF extraction process...")

            # Step 1: Click the process tracking button (view_list icon)
            process_tracking_btn = await page.query_selector('mat-icon[mattooltip="Acompanhamento processual"]')
            if not process_tracking_btn:
                # Fallback xpath
                process_tracking_btn = await page.query_selector('/html/body/app-root/app-home/main/app-search-detail/div/div/div[1]/div/div[1]/div[2]/div/mat-icon[1]')
            
            if not process_tracking_btn:
                self.logger.warning("❌ Process tracking button not found")
                return
            
            self.logger.info("Clicking process tracking button...")
            
            # Use the same context as the original page to avoid browser issues
            context = page.context
            
            # Wait for the new tab to open when clicking process tracking
            async with context.expect_page() as new_page_info:
                await process_tracking_btn.click()
            
            new_page = await new_page_info.value
            await new_page.wait_for_load_state('networkidle', timeout=30000)
            self.logger.info(f"Process tracking page opened: {new_page.url}")

            try:
                # Step 2: Extract the unique number from the process page
                unique_number_element = await new_page.query_selector('.processo-rotulo')
                unique_number = None
                if unique_number_element:
                    unique_number_text = await unique_number_element.text_content()
                    if unique_number_text:
                        # Extract number from "Número Único: 9955162-53.2013.1.00.0000"
                        import re
                        number_match = re.search(r'Número Único:\s*([0-9\-\.]+)', unique_number_text)
                        if number_match:
                            unique_number = number_match.group(1)
                            item_data['numero_unico'] = unique_number
                            self.logger.info(f"✅ Extracted unique number: {unique_number}")

                # Step 3: Click the DJe button to open DJe page in new tab
                self.logger.info("Looking for DJe button...")
                dje_button = await new_page.query_selector('#btn-dje')
                if not dje_button:
                    self.logger.warning("❌ DJe button not found")
                    return
                
                self.logger.info("Found DJe button, clicking to open new tab...")
                
                # Wait for DJe page to open in new tab
                async with context.expect_page() as dje_page_info:
                    await dje_button.click()
                
                dje_page = await dje_page_info.value
                await dje_page.wait_for_load_state('networkidle', timeout=30000)
                self.logger.info(f"✅ DJe page opened: {dje_page.url}")
                
                try:
                    # Step 4: Find and click decision links on DJe page
                    self.logger.info("Looking for decision links...")
                    
                    # Try multiple selectors for decision links
                    decision_selectors = [
                        'a[onclick*="abreDetalheDiarioProcesso"]',  # Original selector
                        'xpath=//*[@id="conteudo"]/div/div[3]/div/div/a',  # From debugging
                        '#conteudo a[href="#"]',  # Alternative CSS selector
                        'a[onclick*="abreDetalhe"]',  # Another variation
                    ]
                    
                    decision_links = []
                    selector_used = None
                    
                    for selector in decision_selectors:
                        try:
                            if selector.startswith('xpath='):
                                # Use XPath selector
                                xpath = selector[6:]  # Remove 'xpath=' prefix
                                decision_links = await dje_page.query_selector_all(f'xpath={xpath}')
                            else:
                                # Use CSS selector
                                decision_links = await dje_page.query_selector_all(selector)
                            
                            if decision_links:
                                selector_used = selector
                                self.logger.info(f"Found {len(decision_links)} decision links with selector: {selector}")
                                break
                            else:
                                self.logger.debug(f"No decision links found with selector: {selector}")
                        except Exception as e:
                            self.logger.debug(f"Selector {selector} failed: {e}")
                    
                    if not decision_links:
                        self.logger.warning("❌ No decision links found in DJe page with any selector")
                        
                        # Debug: Let's see what links are actually on the page
                        all_links = await dje_page.query_selector_all('a')
                        self.logger.info(f"Total links found on DJe page: {len(all_links)}")
                        
                        # Log first few links for debugging
                        for i, link in enumerate(all_links[:5]):
                            try:
                                link_text = await link.text_content()
                                link_onclick = await link.get_attribute('onclick')
                                link_href = await link.get_attribute('href')
                                self.logger.debug(f"Link {i+1}: text='{link_text}', onclick='{link_onclick}', href='{link_href}'")
                            except:
                                pass
                    
                    self.logger.info(f"Found {len(decision_links)} decision links in DJe page")
                    
                    # Try the first decision link for RTF download
                    rtf_downloaded = False
                    if decision_links:
                        # Only try the first decision link
                        decision_link = decision_links[0]
                        
                        try:
                            decision_text = await decision_link.text_content()
                            self.logger.info(f"Trying first decision link: {decision_text}")
                            
                            # Click the decision link to open the popup
                            await decision_link.click()
                            
                            # Wait for the popup div to appear
                            self.logger.info("Waiting for popup to appear...")
                            await dje_page.wait_for_selector('#conteudo-diario-processo', timeout=15000)
                            
                            # Add visible 8 second sleep to ensure popup is fully loaded
                            self.logger.info("Waiting 8 seconds for popup to fully load...")
                            for second in range(8):
                                await dje_page.wait_for_timeout(1000)
                                self.logger.info(f"  Waiting... {second + 1}/8 seconds")
                            
                            # Step 5: Find the RTF download link in the popup
                            rtf_link_selector = '#conteudo-diario-processo a[href*="verDecisao.asp"]'
                            rtf_link = await dje_page.query_selector(rtf_link_selector)
                            
                            if not rtf_link:
                                # Try alternative selectors
                                alternative_selectors = [
                                    '#conteudo-diario-processo a:has-text("Download do documento")',
                                    '#conteudo-diario-processo a[href*="RTF"]',
                                    '#conteudo-diario-processo a:has-text("RTF")',
                                    '#conteudo-diario-processo strong:has-text("Download") + a',
                                    '#conteudo-diario-processo a[href*="texto="]'
                                ]
                                
                                for selector in alternative_selectors:
                                    try:
                                        rtf_link = await dje_page.query_selector(selector)
                                        if rtf_link:
                                            self.logger.info(f"Found RTF link with selector: {selector}")
                                            break
                                    except Exception as e:
                                        self.logger.debug(f"Selector {selector} failed: {e}")
                            
                            if rtf_link:
                                rtf_url = await rtf_link.get_attribute('href')
                                if rtf_url:
                                    # Use raw href as provided
                                    item_data['rtf_url'] = rtf_url
                                    self.logger.info(f"✅ Found RTF download URL: {rtf_url}")
                                    
                                    # Step 6: Download the RTF file
                                    await self.download_rtf_file(dje_page, rtf_url, item_data)
                                    rtf_downloaded = True
                                    self.logger.info("✅ RTF file downloaded successfully")
                                else:
                                    self.logger.warning(f"❌ RTF link found but no href attribute")
                            else:
                                self.logger.warning(f"❌ No RTF download link found in popup")
                                
                                # Debug: log the popup content to see what's actually there
                                popup_content = await dje_page.query_selector('#conteudo-diario-processo')
                                if popup_content:
                                    popup_html = await popup_content.inner_html()
                                    self.logger.debug(f"Popup content: {popup_html[:500]}...")
                                else:
                                    self.logger.warning(f"❌ Popup div not found")
                            
                            # Close popup after processing
                            try:
                                close_btn = await dje_page.query_selector('#conteudo-diario-processo .close, .modal-close, [onclick*="close"]')
                                if close_btn:
                                    await close_btn.click()
                                    await dje_page.wait_for_timeout(1000)  # Wait for popup to close
                                else:
                                    # Try pressing Escape to close popup
                                    await dje_page.keyboard.press('Escape')
                                    await dje_page.wait_for_timeout(1000)
                            except:
                                pass  # Ignore if we can't close the popup
                                
                        except Exception as e:
                            self.logger.error(f"Error processing first decision link: {e}")
                    else:
                        self.logger.warning("❌ No decision links found in DJe page")
                    
                    if not rtf_downloaded:
                        self.logger.warning("❌ No RTF file could be downloaded from the first decision link")

                except Exception as e:
                    self.logger.error(f"Error in DJe page processing: {e}")
                finally:
                    await dje_page.close()

            except Exception as e:
                self.logger.error(f"Error in process tracking page: {e}")
            finally:
                await new_page.close()

        except Exception as e:
            self.logger.error(f"Error in RTF extraction process: {e}")

    async def download_rtf_file(self, page, rtf_url, item_data):
        """Download the RTF file using proper Playwright download handling"""
        try:
            self.logger.info(f"🔽 Downloading RTF file from: {rtf_url}")
            
            # Get current article number from item_data
            current_article = item_data.get('current_article', 'unknown')
            
            # Create download directory with article-specific subdirectory
            download_dir = Path(f"data/rtf_files/{current_article}")
            download_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📂 Download directory: {download_dir.absolute()}")
            
            # Generate filename with article prefix and case number or timestamp
            case_number = item_data.get('case_number', 'unknown')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{current_article}_{case_number}_{timestamp}.rtf"
            file_path = download_dir / filename
            
            self.logger.info(f"📄 Target file path: {file_path.absolute()}")
            
            # Method 1: Use Playwright's download event handling with proper navigation
            download_page = None
            try:
                self.logger.info("📥 Method 1: Using Playwright download event...")
                
                # Create a new page with download handling enabled
                context = page.context
                download_page = await context.new_page()
                
                # Set up download event listener
                downloads = []
                def handle_download(download):
                    downloads.append(download)
                    self.logger.info(f"📦 Download event triggered: {download.url}")
                    self.logger.info(f"💾 Suggested filename: {download.suggested_filename}")
                
                download_page.on("download", handle_download)
                
                # Navigate to RTF URL - this will trigger download and may abort with ERR_ABORTED
                self.logger.info(f"🌐 Navigating to: {rtf_url}")
                try:
                    response = await download_page.goto(rtf_url, wait_until='networkidle', timeout=15000)
                    self.logger.info(f"📊 Response status: {response.status if response else 'No response'}")
                except Exception as nav_error:
                    # This is expected for direct downloads (ERR_ABORTED)
                    self.logger.info(f"ℹ️ Navigation aborted (expected for downloads): {nav_error}")
                
                # Wait for download to complete
                await download_page.wait_for_timeout(5000)
                
                if downloads:
                    download = downloads[0]
                    self.logger.info(f"✅ Download detected, saving to: {file_path}")
                    
                    # Save the download using suggested filename if ours doesn't work
                    try:
                        await download.save_as(str(file_path))
                        self.logger.info(f"💾 Saved with custom filename: {file_path}")
                    except Exception as save_error:
                        # Try with suggested filename but add article prefix
                        suggested_name = download.suggested_filename
                        prefixed_name = f"{current_article}_{suggested_name}"
                        suggested_path = download_dir / prefixed_name
                        await download.save_as(str(suggested_path))
                        file_path = suggested_path  # Update the path
                        self.logger.info(f"💾 Saved with prefixed suggested filename: {file_path}")
                    
                    # Verify the file exists
                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        item_data['rtf_file_path'] = str(file_path)
                        item_data['rtf_url'] = rtf_url
                        self.logger.info(f"🎉 RTF file successfully downloaded: {file_path} ({file_size} bytes)")
                        self.logger.info(f"📝 Updated item_data - rtf_url: {item_data['rtf_url']}, rtf_file_path: {item_data['rtf_file_path']}")
                        return
                    else:
                        self.logger.error(f"❌ File not found after save: {file_path}")
                        raise Exception("Download saved but file not found")
                else:
                    self.logger.warning("⚠️ No download event triggered")
                    raise Exception("No download event detected")
                    
            except Exception as e:
                self.logger.error(f"❌ Method 1 failed: {e}")
                
                # Method 2: Try using existing page context directly
                try:
                    self.logger.info("📥 Method 2: Using existing page context...")
                    
                    # Set up download event on the existing page
                    existing_downloads = []
                    def handle_existing_download(download):
                        existing_downloads.append(download)
                        self.logger.info(f"📦 Existing page download: {download.url}")
                        self.logger.info(f"� Existing suggested filename: {download.suggested_filename}")
                    
                    page.on("download", handle_existing_download)
                    
                    # Try navigation on existing page
                    try:
                        await page.goto(rtf_url, wait_until='load', timeout=15000)
                    except Exception as nav_error:
                        self.logger.info(f"ℹ️ Existing page navigation aborted: {nav_error}")
                    
                    # Wait for download
                    await page.wait_for_timeout(5000)
                    
                    if existing_downloads:
                        download = existing_downloads[0]
                        # Add article prefix to suggested filename
                        suggested_name = download.suggested_filename
                        prefixed_name = f"{current_article}_{suggested_name}"
                        suggested_path = download_dir / prefixed_name
                        await download.save_as(str(suggested_path))
                        
                        if suggested_path.exists():
                            file_size = suggested_path.stat().st_size
                            item_data['rtf_file_path'] = str(suggested_path)
                            item_data['rtf_url'] = rtf_url
                            self.logger.info(f"🎉 RTF file downloaded with existing page: {suggested_path} ({file_size} bytes)")
                            self.logger.info(f"📝 Updated item_data (method 2) - rtf_url: {item_data['rtf_url']}, rtf_file_path: {item_data['rtf_file_path']}")
                            return
                        else:
                            self.logger.error(f"❌ File not found: {suggested_path}")
                    else:
                        self.logger.warning("⚠️ No download on existing page")
                        
                except Exception as existing_error:
                    self.logger.error(f"❌ Method 2 failed: {existing_error}")
                    
                    # Method 3: Log failure
                    self.logger.error("❌ All download methods failed - RTF file could not be saved")
                        
            finally:
                # Always close the download page to prevent tab accumulation
                if download_page:
                    try:
                        await download_page.close()
                        self.logger.info("🚪 Download page closed")
                    except Exception as close_error:
                        self.logger.warning(f"⚠️ Failed to close download page: {close_error}")
                
        except Exception as e:
            self.logger.error(f"💥 Critical error in RTF download: {e}")

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
            item['source'] = f"STF - {item['cluster_name']}"
        else:
            item['cluster_name'] = 'stf_jurisprudencia'
            item['cluster_description'] = 'Jurisprudência STF'
            item['article_reference'] = 'N/A'
            item['source'] = 'STF'
        item['title'] = item_data.get('title', f"STF Item {item_data.get('item_index', 'Unknown')}")
        item['case_number'] = item_data.get('case_number', '')
        item['content'] = item_data.get('content', item_data.get('clipboard_content', ''))
        item['url'] = item_data.get('detail_url', '') or item_data.get('full_decision_data', '') or item_data.get('processo_link', '') or item_data.get('source_url', '')
        item['tribunal'] = 'STF'
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
        
        # Add RTF-related fields
        item['numero_unico'] = item_data.get('numero_unico', '')
        item['rtf_url'] = item_data.get('rtf_url', '')
        item['rtf_file_path'] = item_data.get('rtf_file_path', '')

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
        
        # Add RTF-related fields
        item['numero_unico'] = item_data.get('numero_unico', '')
        item['rtf_url'] = item_data.get('rtf_url', '')
        item['rtf_file_path'] = item_data.get('rtf_file_path', '')

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
        
        # Add RTF-related fields
        item['numero_unico'] = item_data.get('numero_unico', '')
        item['rtf_url'] = item_data.get('rtf_url', '')
        item['rtf_file_path'] = item_data.get('rtf_file_path', '')

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
        
        # Add RTF-related fields
        item['numero_unico'] = item_data.get('numero_unico', '')
        item['rtf_url'] = item_data.get('rtf_url', '')
        item['rtf_file_path'] = item_data.get('rtf_file_path', '')

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
