"""
Tribunais Estaduais spider for Brazilian state court decisions and legal content
"""

from .base_spider import BrazilianLegalSpiderBase
from scrapy_playwright.page import PageMethod
import re


class TribunaisEstaduaisSpider(BrazilianLegalSpiderBase):
    """Spider for scraping Brazilian state court decisions"""
    
    name = 'tribunais_estaduais'
    allowed_domains = [
        'tjsp.jus.br',
        'tjrj.jus.br',
        'tjmg.jus.br',
        'tjrs.jus.br',
        'tjpr.jus.br',
        'tjsc.jus.br',
        'tjgo.jus.br',
        'tjba.jus.br',
        'tjpe.jus.br',
        'tjce.jus.br',
        'tjal.jus.br',
        'tjpb.jus.br',
        'tjrn.jus.br',
        'tjse.jus.br',
        'tjpi.jus.br',
        'tjma.jus.br',
        'tjpa.jus.br',
        'tjam.jus.br',
        'tjac.jus.br',
        'tjro.jus.br',
        'tjrr.jus.br',
        'tjap.jus.br',
        'tjto.jus.br',
        'tjmt.jus.br',
        'tjms.jus.br',
        'tjdf.jus.br',
        'tjes.jus.br',
    ]
    
    def get_playwright_meta(self, extra_methods=None):
        """Get Playwright meta with state courts-specific methods"""
        extra_methods = extra_methods or []
        
        # Add state courts-specific page methods
        extra_methods.extend([
            # Navigate to jurisprudence section
            PageMethod('evaluate', '''
                // Look for jurisprudence/consulta link
                const jurispLink = document.querySelector('a[href*="jurisprudencia"], a[href*="consulta"], a[href*="acordao"]');
                if (jurispLink) {
                    jurispLink.click();
                    await new Promise(resolve => setTimeout(resolve, 3000));
                }
            '''),
            
            # Wait for court decisions to load
            PageMethod('wait_for_selector', '.acordao-item, .decisao-item, .jurisprudencia-item, .resultado-item', timeout=15000),
        ])
        
        return super().get_playwright_meta(extra_methods)
    
    def parse_item_preview(self, item, response, selectors):
        """Parse state court item with specific field mappings"""
        # Extract state court-specific fields
        title = self.extract_with_fallback(item, selectors.get('title', ''))
        link = self.extract_with_fallback(item, selectors.get('link', ''))
        
        if not title:
            self.logger.warning(f"No title found for state court item on {response.url}")
            return
        
        # Extract state and court info from URL/content
        state = self.extract_state_from_url(response.url)
        court_chamber = self.extract_court_chamber(title)
        instance_level = self.extract_instance_level(title)
        
        # Create item data with state court-specific fields
        item_data = {
            'theme': self.name,
            'source_site': response.url,
            'title': title,
            'document_type': 'Decisão Estadual',
            'state': state,
            'court_chamber': court_chamber,
            'instance_level': instance_level,
            'tribunal': f'TJ{state}' if state else 'Tribunal de Justiça',
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
        
        # Extract legal area from title
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
        """Parse state court detail page with specific field extraction"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})
        
        try:
            self.logger.debug(f"Parsing state court detail: {response.url}")
            
            # Update with detail page URL
            item_data['url'] = response.url
            
            # Extract full decision text
            content_selectors = [
                '.acordao-texto, .decisao-completa, .inteiro-teor',
                '.ementa, .summary, .abstract',
                '.voto, .fundamentacao, .content'
            ]
            
            for selector in content_selectors:
                content = self.extract_with_fallback(response, selector)
                if content and len(content) > 100:
                    item_data['content'] = content
                    break
            
            # Extract state court-specific fields
            specific_fields = {
                'parties_involved': '.partes, .parties, .litigantes',
                'voting_result': '.resultado-votacao, .placar',
                'appeal_type': '.tipo-recurso, .recurso'
            }
            
            for field, selector in specific_fields.items():
                value = self.extract_with_fallback(response, selector)
                if value:
                    item_data[field] = value
            
            # Re-extract court chamber and instance if not found before
            if not item_data.get('court_chamber') and item_data.get('content'):
                item_data['court_chamber'] = self.extract_court_chamber(item_data['content'])
            
            if not item_data.get('instance_level') and item_data.get('content'):
                item_data['instance_level'] = self.extract_instance_level(item_data['content'])
            
            yield self.create_item(item_data)
            
        finally:
            if page:
                await page.close()
    
    def extract_state_from_url(self, url):
        """Extract state abbreviation from URL"""
        if not url:
            return None
        
        # Extract state from domain (e.g., tjsp.jus.br -> SP)
        state_pattern = r'tj([a-z]{2})\.jus\.br'
        match = re.search(state_pattern, url.lower())
        if match:
            return match.group(1).upper()
        
        # Fallback: try to extract from path
        path_pattern = r'/([a-z]{2})/'
        match = re.search(path_pattern, url.lower())
        if match:
            return match.group(1).upper()
        
        return None
    
    def extract_court_chamber(self, text):
        """Extract court chamber from text"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Common chamber patterns in Brazilian state courts
        chamber_patterns = [
            r'(\d+ª?\s*câmara\s*(?:cível|criminal|de\s*direito\s*(?:privado|público)))',
            r'(\d+ª?\s*turma\s*(?:cível|criminal))',
            r'(\d+º\s*grupo\s*de\s*câmaras)',
            r'(câmara\s*especial)',
            r'(seção\s*(?:cível|criminal))',
            r'(\d+ª?\s*vara\s*(?:cível|criminal|da\s*família))',
        ]
        
        for pattern in chamber_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).title()
        
        return None
    
    def extract_instance_level(self, text):
        """Extract court instance level from text"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Determine instance level
        if any(term in text_lower for term in ['câmara', 'turma', 'apelação', 'agravo', 'tribunal']):
            return '2ª Instância'
        elif any(term in text_lower for term in ['vara', 'juiz', 'sentença', 'primeiro grau']):
            return '1ª Instância'
        else:
            return '1ª Instância'  # Default
    
    def extract_legal_area(self, title):
        """Extract legal area from title"""
        if not title:
            return 'Geral'
        
        title_lower = title.lower()
        
        # Legal areas common in state courts
        area_keywords = {
            'Civil': ['civil', 'contrato', 'responsabilidade civil', 'propriedade', 'família'],
            'Criminal': ['criminal', 'penal', 'crime', 'delito'],
            'Trabalhista': ['trabalho', 'trabalhista', 'emprego', 'clt'],
            'Tributário': ['tributo', 'tributário', 'imposto', 'taxa', 'icms'],
            'Administrativo': ['administrativo', 'servidor público', 'licitação'],
            'Consumidor': ['consumidor', 'cdc', 'relação de consumo'],
            'Empresarial': ['empresarial', 'societário', 'falência'],
            'Família': ['família', 'divórcio', 'guarda', 'alimentos'],
            'Sucessões': ['sucessões', 'herança', 'inventário'],
            'Ambiental': ['ambiental', 'meio ambiente', 'licenciamento'],
            'Eleitoral': ['eleitoral', 'eleição', 'candidato'],
        }
        
        for area, keywords in area_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return area
        
        return 'Geral' 