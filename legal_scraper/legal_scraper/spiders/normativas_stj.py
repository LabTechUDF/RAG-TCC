"""
Normativas STJ spider for Brazilian Superior Court normative acts and regulations
"""

from .base_spider import BrazilianLegalSpiderBase
from scrapy_playwright.page import PageMethod
import re


class NormativasStjSpider(BrazilianLegalSpiderBase):
    """Spider for scraping STJ normative acts and regulations"""
    
    name = 'normativas_stj'
    allowed_domains = [
        'stj.jus.br',
        'portal.stj.jus.br'
    ]
    
    def get_playwright_meta(self, extra_methods=None):
        """Get Playwright meta with normatives-specific methods"""
        extra_methods = extra_methods or []
        
        # Add normatives-specific page methods
        extra_methods.extend([
            # Navigate to normatives section
            PageMethod('evaluate', '''
                // Look for normatives/regulamentos link
                const normLink = document.querySelector('a[href*="normativ"], a[href*="regulament"], a[href*="portaria"], a[href*="instrucao"]');
                if (normLink) {
                    normLink.click();
                    await new Promise(resolve => setTimeout(resolve, 3000));
                }
            '''),
            
            # Wait for normatives list to load
            PageMethod('wait_for_selector', '.normativa-item, .regulamento-item, .portaria-item, .instrucao-item', timeout=15000),
        ])
        
        return super().get_playwright_meta(extra_methods)
    
    def parse_item_preview(self, item, response, selectors):
        """Parse normative item with specific field mappings"""
        # Extract normative-specific fields
        title = self.extract_with_fallback(item, selectors.get('title', ''))
        link = self.extract_with_fallback(item, selectors.get('link', ''))
        
        if not title:
            self.logger.warning(f"No title found for normative item on {response.url}")
            return
        
        # Extract normative number and type from title
        normative_type, normative_number = self.extract_normative_info(title)
        
        # Create item data with normative-specific fields
        item_data = {
            'theme': self.name,
            'source_site': response.url,
            'title': title,
            'document_type': 'Normativa',
            'tribunal': 'Superior Tribunal de Justiça',
            'court_level': 'Superior Tribunal de Justiça',
            'normative_type': normative_type,
            'normative_number': normative_number,
            'legal_area': 'Processual',
        }
        
        # Map config fields to item fields
        field_mapping = {
            'date': 'publication_date',
            'summary': 'summary',
            'temas': 'subject_matter'
        }
        
        for config_field, item_field in field_mapping.items():
            if config_field in selectors:
                value = self.extract_with_fallback(item, selectors[config_field])
                if value:
                    item_data[item_field] = value
        
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
        """Parse normative detail page with specific field extraction"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})
        
        try:
            self.logger.debug(f"Parsing normative detail: {response.url}")
            
            # Update with detail page URL
            item_data['url'] = response.url
            
            # Extract full normative text
            content_selectors = [
                '.normativa-texto, .regulamento-conteudo, .texto-normativo',
                '.artigos, .articles, .content',
                '.inteiro-teor, .full-text'
            ]
            
            for selector in content_selectors:
                content = self.extract_with_fallback(response, selector)
                if content and len(content) > 100:
                    item_data['content'] = content
                    break
            
            # Extract normative-specific fields
            specific_fields = {
                'effective_date': '.data-vigencia, .effective-date, .data-inicio',
                'revoked': '.revogada, .revoked, .cancelada'
            }
            
            for field, selector in specific_fields.items():
                value = self.extract_with_fallback(response, selector)
                if value:
                    if field == 'revoked':
                        item_data[field] = 'revogada' in value.lower() or 'cancelada' in value.lower()
                    else:
                        item_data[field] = value
            
            # Extract related laws and regulations
            related_laws = response.css('a[href*="lei"], a[href*="decreto"], a[href*="portaria"]::text').getall()
            if related_laws:
                item_data['related_laws'] = [law.strip() for law in related_laws[:5] if law.strip()]
            
            yield self.create_item(item_data)
            
        finally:
            if page:
                await page.close()
    
    def extract_normative_info(self, title):
        """Extract normative type and number from title"""
        if not title:
            return None, None
        
        title_lower = title.lower()
        
        # Common normative types in STJ
        normative_patterns = {
            'Portaria': r'portaria\s+(?:nº\s*)?(\d+)',
            'Instrução Normativa': r'instrução\s+normativa\s+(?:nº\s*)?(\d+)',
            'Resolução': r'resolução\s+(?:nº\s*)?(\d+)',
            'Provimento': r'provimento\s+(?:nº\s*)?(\d+)',
            'Regulamento': r'regulamento\s+(?:nº\s*)?(\d+)',
            'Ordem de Serviço': r'ordem\s+de\s+serviço\s+(?:nº\s*)?(\d+)',
        }
        
        for norm_type, pattern in normative_patterns.items():
            match = re.search(pattern, title_lower)
            if match:
                return norm_type, int(match.group(1))
        
        # Fallback: look for any number
        number_match = re.search(r'\b(\d+)\b', title_lower)
        if number_match:
            return 'Normativa', int(number_match.group(1))
        
        return 'Normativa', None 