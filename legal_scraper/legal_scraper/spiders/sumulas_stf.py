"""
Sumulas STF spider for Brazilian Supreme Court precedents and legal summaries
"""

from .base_spider import BrazilianLegalSpiderBase
from scrapy_playwright.page import PageMethod
import re


class SumulasStfSpider(BrazilianLegalSpiderBase):
    """Spider for scraping STF Súmulas (legal precedents)"""
    
    name = 'sumulas_stf'
    allowed_domains = [
        'portal.stf.jus.br',
        'stf.jus.br',
        'supremo.stf.jus.br'
    ]
    
    def get_playwright_meta(self, extra_methods=None):
        """Get Playwright meta with Súmulas-specific methods"""
        extra_methods = extra_methods or []
        
        # Add Súmulas-specific page methods
        extra_methods.extend([
            # Navigate to Súmulas section if needed
            PageMethod('evaluate', '''
                // Look for Súmulas link and click it
                const sumulaLink = document.querySelector('a[href*="sumula"], a[href*="precedent"], a[text*="Súmula"]');
                if (sumulaLink) {
                    sumulaLink.click();
                    await new Promise(resolve => setTimeout(resolve, 3000));
                }
            '''),
            
            # Wait for Súmulas list to load
            PageMethod('wait_for_selector', '.sumula-item, .precedent-item, .lista-sumulas, .sumula', timeout=15000),
        ])
        
        return super().get_playwright_meta(extra_methods)
    
    def parse_item_preview(self, item, response, selectors):
        """Parse Súmula item with specific field mappings"""
        # Extract Súmula-specific fields
        title = self.extract_with_fallback(item, selectors.get('title', ''))
        link = self.extract_with_fallback(item, selectors.get('link', ''))
        
        if not title:
            self.logger.warning(f"No title found for Súmula item on {response.url}")
            return
        
        # Extract Súmula number from title
        sumula_number = self.extract_sumula_number(title)
        
        # Create item data with Súmula-specific fields
        item_data = {
            'theme': self.name,
            'source_site': response.url,
            'title': title,
            'document_type': 'Súmula',
            'tribunal': 'Supremo Tribunal Federal',
            'court_level': 'Supremo Tribunal Federal',
            'sumula_number': sumula_number,
            'legal_area': 'Constitucional',
        }
        
        # Map config fields to item fields
        field_mapping = {
            'date': 'publication_date',
            'summary': 'summary',
            'type': 'sumula_type',
            'temas': 'subject_matter'
        }
        
        for config_field, item_field in field_mapping.items():
            if config_field in selectors:
                value = self.extract_with_fallback(item, selectors[config_field])
                if value:
                    item_data[item_field] = value
        
        # Determine if it's a binding Súmula
        item_data['binding_effect'] = self.is_binding_sumula(title)
        
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
        """Parse Súmula detail page with specific field extraction"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})
        
        try:
            self.logger.debug(f"Parsing Súmula detail: {response.url}")
            
            # Update with detail page URL
            item_data['url'] = response.url
            
            # Extract full Súmula text
            selectors = self.config.get('selectors', {})
            content_selectors = [
                '.sumula-texto, .sumula-conteudo, .texto-sumula',
                '.enunciado, .statement, .content',
                '.inteiro-teor, .full-text'
            ]
            
            for selector in content_selectors:
                content = self.extract_with_fallback(response, selector)
                if content:
                    item_data['content'] = content
                    break
            
            # Extract Súmula-specific fields
            specific_fields = {
                'revision_date': '.data-revisao, .revision-date, .data-alteracao',
                'canceled': '.cancelada, .revogada, .canceled, .revoked'
            }
            
            for field, selector in specific_fields.items():
                value = self.extract_with_fallback(response, selector)
                if value:
                    if field == 'canceled':
                        item_data[field] = 'cancelada' in value.lower() or 'revogada' in value.lower()
                    else:
                        item_data[field] = value
            
            # Extract related Súmulas
            related_sumulas = response.css('a[href*="sumula"]::attr(href)').getall()
            if related_sumulas:
                item_data['related_sumulas'] = related_sumulas[:5]  # Limit to 5
            
            # Extract precedent cases that led to this Súmula
            precedent_cases = response.css('.casos-precedentes, .precedent-cases')
            if precedent_cases:
                cases = []
                for case in precedent_cases.css('a::text').getall()[:3]:  # Limit to 3
                    if case.strip():
                        cases.append(case.strip())
                if cases:
                    item_data['precedent_cases'] = cases
            
            yield self.create_item(item_data)
            
        finally:
            if page:
                await page.close()
    
    def extract_sumula_number(self, title):
        """Extract Súmula number from title"""
        if not title:
            return None
        
        # Look for patterns like "Súmula 123", "Súmula nº 123", "Súmula Vinculante 123"
        patterns = [
            r'súmula\s+(?:nº\s*)?(\d+)',
            r'sumula\s+(?:nº\s*)?(\d+)', 
            r'precedente\s+(?:nº\s*)?(\d+)',
            r'\b(\d+)\b'  # fallback: any number
        ]
        
        title_lower = title.lower()
        for pattern in patterns:
            match = re.search(pattern, title_lower)
            if match:
                return int(match.group(1))
        
        return None
    
    def is_binding_sumula(self, title):
        """Determine if Súmula is binding (vinculante)"""
        if not title:
            return False
        
        title_lower = title.lower()
        binding_terms = ['vinculante', 'binding', 'obrigatória', 'obrigatoria']
        
        return any(term in title_lower for term in binding_terms)
    
    def extract_legal_area_from_content(self, content):
        """Extract legal area from Súmula content"""
        if not content:
            return 'Constitucional'
        
        content_lower = content.lower()
        
        # Súmulas often deal with specific constitutional issues
        area_keywords = {
            'tributário': ['tributo', 'imposto', 'taxa', 'contribuição', 'icms', 'ipi'],
            'processual': ['processo', 'procedimento', 'competência', 'recurso'],
            'administrativo': ['servidor', 'administrativo', 'licitação', 'contrato administrativo'],
            'penal': ['penal', 'criminal', 'crime', 'pena'],
            'civil': ['civil', 'contrato', 'responsabilidade civil', 'propriedade'],
            'trabalhista': ['trabalho', 'trabalhista', 'emprego', 'salário'],
        }
        
        for area, keywords in area_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return area.title()
        
        return 'Constitucional'  # Default for STF Súmulas 