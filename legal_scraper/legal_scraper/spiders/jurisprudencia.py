"""
Jurisprudencia spider for Brazilian court decisions and case law
"""

from .base_spider import BrazilianLegalSpiderBase
from scrapy_playwright.page import PageMethod


class JurisprudenciaSpider(BrazilianLegalSpiderBase):
    """Spider for scraping Brazilian jurisprudence from courts"""
    
    name = 'jurisprudencia'
    allowed_domains = [
        'stj.jus.br',
        'portal.stf.jus.br', 
        'tjsp.jus.br',
        'tjrj.jus.br',
        'tribunais.jus.br'
    ]
    
    def get_playwright_meta(self, extra_methods=None):
        """Get Playwright meta with jurisprudence-specific methods"""
        extra_methods = extra_methods or []
        
        # Add jurisprudence-specific page methods
        extra_methods.extend([
            # Handle search forms that might be present
            PageMethod('evaluate', '''
                // Fill search form if present
                const searchInput = document.querySelector('input[name*="search"], input[id*="search"], input[placeholder*="pesquisar"]');
                if (searchInput) {
                    searchInput.value = "jurisprudência OR acórdão OR decisão";
                    
                    // Try to submit the form
                    const submitBtn = document.querySelector('button[type="submit"], input[type="submit"], .btn-search');
                    if (submitBtn) {
                        submitBtn.click();
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }
                }
            '''),
            
            # Wait for results to load
            PageMethod('wait_for_selector', '.resultado-pesquisa, .jurisprudencia-lista, .search-results, .item-jurisprudencia', timeout=15000),
        ])
        
        return super().get_playwright_meta(extra_methods)
    
    def parse_item_preview(self, item, response, selectors):
        """Parse jurisprudence item with specific field mappings"""
        # Extract jurisprudence-specific fields
        title = self.extract_with_fallback(item, selectors.get('title', ''))
        link = self.extract_with_fallback(item, selectors.get('link', ''))
        
        if not title:
            self.logger.warning(f"No title found for jurisprudence item on {response.url}")
            return
        
        # Create item data with jurisprudence-specific fields
        item_data = {
            'theme': self.name,
            'source_site': response.url,
            'title': title,
            'document_type': 'Jurisprudência',
            'court_level': self.extract_court_level(response.url),
        }
        
        # Map config fields to item fields
        field_mapping = {
            'date': 'publication_date',
            'court': 'tribunal', 
            'case_number': 'case_number',
            'summary': 'summary',
            'relator': 'judge_rapporteur',
            'type': 'decision_type',
            'origem': 'jurisdiction',
            'temas': 'subject_matter'
        }
        
        for config_field, item_field in field_mapping.items():
            if config_field in selectors:
                value = self.extract_with_fallback(item, selectors[config_field])
                if value:
                    item_data[item_field] = value
        
        # Extract legal area from content
        if 'legal_area' not in item_data:
            item_data['legal_area'] = self.extract_legal_area(title)
        
        # Follow detail link or yield preview
        if link:
            detail_url = response.urljoin(link)
            if detail_url not in self.scraped_urls:
                self.scraped_urls.add(detail_url)
                yield response.follow(
                    link,
                    meta={
                        **self.get_playwright_meta(),
                        'item_data': item_data,
                    },
                    callback=self.parse_detail,
                    errback=self.handle_error
                )
        else:
            yield self.create_item(item_data)
    
    async def parse_detail(self, response):
        """Parse jurisprudence detail page with specific field extraction"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})
        
        try:
            self.logger.debug(f"Parsing jurisprudence detail: {response.url}")
            
            # Update with detail page URL
            item_data['url'] = response.url
            
            # Extract full decision text
            selectors = self.config.get('selectors', {})
            content_selectors = [
                '.inteiro-teor, .decisao-completa, .acordao-texto',
                '.ementa, .summary, .abstract',
                '.conteudo, .content, .texto-decisao'
            ]
            
            for selector in content_selectors:
                content = self.extract_with_fallback(response, selector)
                if content and len(content) > 100:
                    item_data['content'] = content
                    break
            
            # Extract jurisprudence-specific fields
            specific_fields = {
                'voting_result': '.resultado-votacao, .placar, .voting',
                'appeal_type': '.tipo-recurso, .recurso, .appeal-type',
                'parties_involved': '.partes, .parties, .litigantes'
            }
            
            for field, selector in specific_fields.items():
                value = self.extract_with_fallback(response, selector)
                if value:
                    item_data[field] = value
            
            # Extract related precedents
            precedent_links = response.css('a[href*="precedente"], a[href*="similar"]::attr(href)').getall()
            if precedent_links:
                item_data['precedent_references'] = precedent_links[:5]  # Limit to 5
            
            yield self.create_item(item_data)
            
        finally:
            if page:
                await page.close()
    
    def extract_court_level(self, url):
        """Extract court level from URL"""
        if 'stf.jus.br' in url:
            return 'Supremo Tribunal Federal'
        elif 'stj.jus.br' in url:
            return 'Superior Tribunal de Justiça'
        elif 'tj' in url:
            return 'Tribunal de Justiça'
        elif 'tst.jus.br' in url:
            return 'Tribunal Superior do Trabalho'
        elif 'tse.jus.br' in url:
            return 'Tribunal Superior Eleitoral'
        else:
            return 'Tribunal'
    
    def extract_legal_area(self, title):
        """Extract legal area from title"""
        title_lower = title.lower()
        
        # Common legal areas in Brazilian jurisprudence
        area_keywords = {
            'civil': ['civil', 'direito civil', 'contratos', 'responsabilidade civil'],
            'penal': ['penal', 'criminal', 'crime', 'delito'],
            'trabalhista': ['trabalho', 'trabalhista', 'emprego', 'clt'],
            'tributário': ['tributo', 'tributário', 'imposto', 'taxa'],
            'administrativo': ['administrativo', 'licitação', 'servidor público'],
            'constitucional': ['constitucional', 'constituição', 'direitos fundamentais'],
            'empresarial': ['empresarial', 'societário', 'falência', 'recuperação'],
            'consumidor': ['consumidor', 'cdc', 'relação de consumo'],
        }
        
        for area, keywords in area_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return area.title()
        
        return 'Geral' 