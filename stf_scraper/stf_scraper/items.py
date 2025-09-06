# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from itemloaders.processors import TakeFirst, MapCompose
from w3lib.html import remove_tags, strip_html5_whitespace
import re

def clean_text(text):
    """Clean text by removing extra whitespace and normalizing"""
    if not text:
        return text
    # Remove HTML tags if any remain
    text = remove_tags(text)
    # Strip whitespace and normalize
    text = strip_html5_whitespace(text)
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_classe_processual_from_url(url):
    """Extract classe processual unificada from STF URL"""
    if not url:
        return None
    
    # Map of abbreviations to full names based on legend
    classe_map = {
        'HC': 'HABEAS CORPUS',
        'ARE': 'RECURSO EXTRAORDINÁRIO COM AGRAVO', 
        'RE': 'RECURSO EXTRAORDINÁRIO',
        'RHC': 'RECURSO ORDINÁRIO EM HABEAS CORPUS',
        'MC': 'MEDIDA CAUTELAR'
    }
    
    # Extract from URL parameter processo_classe_processual_unificada_classe_sigla
    pattern = r'processo_classe_processual_unificada_classe_sigla=([A-Z]+)'
    match = re.search(pattern, url)
    
    if match:
        sigla = match.group(1)
        return classe_map.get(sigla, sigla)  # Return full name or abbreviation if not found
    
    return None


def extract_relator_from_content(content):
    """Extract relator (judge rapporteur) from content"""
    if not content:
        return None
    
    # Pattern to match "Relator(a): Min. NAME"
    pattern = r'Relator\(a\):\s*Min\.\s*([A-ZÁÊÔÇÀÃÕÉ\s]+)'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    return None


def extract_publication_date_from_content(content):
    """Extract publication date from content"""
    if not content:
        return None
    
    # Pattern to match "Publicação: DD/MM/YYYY"
    pattern = r'Publicação:\s*(\d{2}/\d{2}/\d{4})'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        return match.group(1)
    
    return None


def extract_decision_date_from_content(content):
    """Extract decision date from content"""
    if not content:
        return None
    
    # Pattern to match "Julgamento: DD/MM/YYYY"
    pattern = r'Julgamento:\s*(\d{2}/\d{2}/\d{4})'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        return match.group(1)
    
    return None


def extract_partes_from_content(content):
    """Extract parties (partes) information from content"""
    if not content:
        return None
    
    # Pattern to match "Impetrante: NAME" or "Paciente: NAME" etc.
    patterns = [
        r'Impetrante:\s*([^\n]+)',
        r'Paciente:\s*([^\n]+)',
        r'Requerente:\s*([^\n]+)',
        r'Agravante:\s*([^\n]+)',
        r'Recorrente:\s*([^\n]+)',
        r'Autor:\s*([^\n]+)',
        r'Réu:\s*([^\n]+)'
    ]
    
    partes = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            partes.append(match.strip())
    
    return '; '.join(partes) if partes else None


class LegalDocumentItem(scrapy.Item):
    """Base item for Brazilian legal documents"""
    
    # Core identification
    theme = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    title = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    case_number = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Brazilian legal process classification
    classe_processual_unificada = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Content
    content = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Essential metadata
    url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    tribunal = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    legal_area = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )


class JurisprudenciaItem(LegalDocumentItem):
    """Item for jurisprudence (court decisions)"""
    
    # Court decision specifics - will be extracted from content in spider
    relator = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    decision_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Dates specific to decisions - will be extracted from content in spider
    publication_date = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    decision_date = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # New fields for detailed decision content
    partes = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    decision = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    legislacao = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Quality assessment score (calculated by pipeline)
    content_quality = scrapy.Field(
        output_processor=TakeFirst()
    )

