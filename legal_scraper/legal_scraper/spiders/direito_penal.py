"""
Direito Penal spider for Brazilian criminal law content, decisions, and precedents
"""

from .base_spider import BrazilianLegalSpiderBase
from scrapy_playwright.page import PageMethod
import re


class DireitoPenalSpider(BrazilianLegalSpiderBase):
    """Spider for scraping Brazilian criminal law content"""
    
    name = 'direito_penal'
    allowed_domains = [
        'stj.jus.br',
        'portal.stf.jus.br',
        'tjsp.jus.br',
        'tjrj.jus.br',
        'tjmg.jus.br',
        'cnj.jus.br'
    ]
    
    def get_playwright_meta(self, extra_methods=None):
        """Get Playwright meta with criminal law-specific methods"""
        extra_methods = extra_methods or []
        
        # Add criminal law-specific page methods
        extra_methods.extend([
            # Search for criminal law content
            PageMethod('evaluate', '''
                // Fill search form with criminal law terms
                const searchInput = document.querySelector('input[name*="search"], input[id*="search"], input[placeholder*="pesquisar"]');
                if (searchInput) {
                    searchInput.value = "direito penal OR criminal OR crime OR delito";
                    
                    // Try to submit the form
                    const submitBtn = document.querySelector('button[type="submit"], input[type="submit"], .btn-search');
                    if (submitBtn) {
                        submitBtn.click();
                        await new Promise(resolve => setTimeout(resolve, 3000));
                    }
                }
            '''),
            
            # Wait for criminal law content to load
            PageMethod('wait_for_selector', '.criminal-item, .penal-item, .crime-item, .delito-item, .resultado', timeout=15000),
        ])
        
        return super().get_playwright_meta(extra_methods)
    
    def parse_item_preview(self, item, response, selectors):
        """Parse criminal law item with specific field mappings"""
        # Extract criminal law-specific fields
        title = self.extract_with_fallback(item, selectors.get('title', ''))
        link = self.extract_with_fallback(item, selectors.get('link', ''))
        
        if not title:
            self.logger.warning(f"No title found for criminal law item on {response.url}")
            return
        
        # Extract crime type and legal provision
        crime_type = self.extract_crime_type(title)
        legal_provision = self.extract_legal_provision(title)
        
        # Create item data with criminal law-specific fields
        item_data = {
            'theme': self.name,
            'source_site': response.url,
            'title': title,
            'document_type': 'Direito Penal',
            'legal_area': 'Penal',
            'crime_type': crime_type,
            'legal_provision': legal_provision,
        }
        
        # Map config fields to item fields
        field_mapping = {
            'date': 'publication_date',
            'court': 'tribunal',
            'case_number': 'case_number',
            'summary': 'summary',
            'relator': 'judge_rapporteur',
            'type': 'decision_type',
            'temas': 'subject_matter'
        }
        
        for config_field, item_field in field_mapping.items():
            if config_field in selectors:
                value = self.extract_with_fallback(item, selectors[config_field])
                if value:
                    item_data[item_field] = value
        
        # Extract penalty type if mentioned
        penalty_type = self.extract_penalty_type(title)
        if penalty_type:
            item_data['penalty_type'] = penalty_type
        
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
        """Parse criminal law detail page with specific field extraction"""
        page = response.meta.get("playwright_page")
        item_data = response.meta.get('item_data', {})
        
        try:
            self.logger.debug(f"Parsing criminal law detail: {response.url}")
            
            # Update with detail page URL
            item_data['url'] = response.url
            
            # Extract full criminal law content
            content_selectors = [
                '.decisao-penal, .criminal-decision, .penal-content',
                '.ementa, .summary, .abstract',
                '.inteiro-teor, .full-text, .content'
            ]
            
            for selector in content_selectors:
                content = self.extract_with_fallback(response, selector)
                if content and len(content) > 100:
                    item_data['content'] = content
                    break
            
            # Extract criminal law-specific fields from detail page
            if item_data.get('content'):
                content = item_data['content']
                
                # Re-analyze with full content
                if not item_data.get('crime_type'):
                    item_data['crime_type'] = self.extract_crime_type(content)
                
                if not item_data.get('legal_provision'):
                    item_data['legal_provision'] = self.extract_legal_provision(content)
                
                if not item_data.get('penalty_type'):
                    item_data['penalty_type'] = self.extract_penalty_type(content)
            
            # Extract precedent references
            precedent_links = response.css('a[href*="precedente"], a[href*="jurisprudencia"]::attr(href)').getall()
            if precedent_links:
                item_data['precedent_references'] = precedent_links[:5]
            
            yield self.create_item(item_data)
            
        finally:
            if page:
                await page.close()
    
    def extract_crime_type(self, text):
        """Extract crime type from text"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Common crime types in Brazilian criminal law
        crime_patterns = {
            'Homicídio': r'homic[íi]dio',
            'Furto': r'furto',
            'Roubo': r'roubo',
            'Estelionato': r'estelionato',
            'Tráfico de Drogas': r'tr[áa]fico.*drogas?',
            'Lavagem de Dinheiro': r'lavagem.*dinheiro',
            'Corrupção': r'corrup[çc][ãa]o',
            'Peculato': r'peculato',
            'Estupro': r'estupro',
            'Injúria': r'inj[úu]ria',
            'Difamação': r'difama[çc][ãa]o',
            'Calúnia': r'cal[úu]nia',
            'Lesão Corporal': r'les[ãa]o.*corporal',
            'Ameaça': r'amea[çc]a',
            'Sequestro': r'sequestro',
            'Extorsão': r'extors[ãa]o',
            'Apropriação Indébita': r'apropria[çc][ãa]o.*ind[ée]bita',
            'Falsificação': r'falsifica[çc][ãa]o',
            'Sonegação Fiscal': r'sonega[çc][ãa]o.*fiscal',
        }
        
        for crime_type, pattern in crime_patterns.items():
            if re.search(pattern, text_lower):
                return crime_type
        
        return None
    
    def extract_legal_provision(self, text):
        """Extract legal provision (article) from text"""
        if not text:
            return None
        
        # Look for article references (Art. 121, Artigo 157, etc.)
        patterns = [
            r'art(?:igo)?\.?\s*(\d+)',
            r'art(?:igo)?\.?\s*(\d+)-?[A-Z]?',
            r'(\d+).*?(?:do\s+)?c[óo]digo\s+penal',
            r'cp.*?art(?:igo)?\.?\s*(\d+)',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                article_num = match.group(1)
                return f"Art. {article_num} do Código Penal"
        
        # Look for law references
        law_pattern = r'lei\s+(?:nº\s*)?(\d+(?:\.\d+)*\/\d{4})'
        law_match = re.search(law_pattern, text_lower)
        if law_match:
            return f"Lei {law_match.group(1)}"
        
        return None
    
    def extract_penalty_type(self, text):
        """Extract penalty type from text"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Common penalty types
        penalty_patterns = {
            'Reclusão': r'reclus[ãa]o',
            'Detenção': r'deten[çc][ãa]o',
            'Prisão': r'pris[ãa]o',
            'Multa': r'multa',
            'Prestação de Serviços': r'presta[çc][ãa]o.*servi[çc]os',
            'Liberdade Condicional': r'liberdade.*condicional',
            'Sursis': r'sursis|suspens[ãa]o.*condicional',
            'Regime Aberto': r'regime.*aberto',
            'Regime Semiaberto': r'regime.*semiaberto',
            'Regime Fechado': r'regime.*fechado',
        }
        
        for penalty_type, pattern in penalty_patterns.items():
            if re.search(pattern, text_lower):
                return penalty_type
        
        return None 