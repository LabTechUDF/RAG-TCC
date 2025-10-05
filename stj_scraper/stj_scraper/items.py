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
    """Extract classe processual unificada from STJ URL"""
    if not url:
        return None
    
    # Map of abbreviations to full names based on STJ patterns
    classe_map = {
        'ARESP': 'AGRAVO EM RECURSO ESPECIAL',
        'RESP': 'RECURSO ESPECIAL', 
        'RHC': 'RECURSO ORDINÁRIO EM HABEAS CORPUS',
        'HC': 'HABEAS CORPUS',
        'MS': 'MANDADO DE SEGURANÇA',
        'MC': 'MEDIDA CAUTELAR',
        'AgRg': 'AGRAVO REGIMENTAL'
    }
    
    # Extract from URL parameter livre= or any class reference
    for sigla, nome_completo in classe_map.items():
        if sigla.lower() in url.lower():
            return nome_completo
    
    return None


def extract_relator_from_content(content):
    """Extract relator (judge rapporteur) from STJ content"""
    if not content:
        return None
    
    # Pattern to match "Relator(a): Min. NAME" or "RELATORA: MINISTRA NAME"
    patterns = [
        r'Relator\(a\):\s*Min\.?\s*([A-ZÁÊÔÇÀÃÕÉ\s]+)',
        r'RELATOR[A]?:\s*MINISTR[OA]\s*([A-ZÁÊÔÇÀÃÕÉ\s]+)',
        r'Rel\.?\s*Min\.?\s*([A-ZÁÊÔÇÀÃÕÉ\s]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def extract_publication_date_from_content(content):
    """Extract publication date from STJ content"""
    if not content:
        return None
    
    # Pattern to match "DJe DD/MM/YYYY" or "Publicação: DD/MM/YYYY"
    patterns = [
        r'DJe\s*(\d{2}/\d{2}/\d{4})',
        r'Publicação:\s*(\d{2}/\d{2}/\d{4})',
        r'DJ[eE]?\s*(\d{2}/\d{2}/\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def extract_decision_date_from_content(content):
    """Extract decision date from STJ content"""
    if not content:
        return None
    
    # Pattern to match "Julgamento: DD/MM/YYYY" or similar
    patterns = [
        r'Julgamento:\s*(\d{2}/\d{2}/\d{4})',
        r'Data do Julgamento:\s*(\d{2}/\d{2}/\d{4})',
        r'Julgado em:\s*(\d{2}/\d{2}/\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def extract_partes_from_content(content):
    """Extract parties (partes) information from STJ content"""
    if not content:
        return None
    
    # Pattern to match various party types in STJ decisions
    patterns = [
        r'RECORRENTE:\s*([^\n]+)',
        r'RECORRIDO:\s*([^\n]+)',
        r'IMPETRANTE:\s*([^\n]+)',
        r'IMPETRADO:\s*([^\n]+)',
        r'AGRAVANTE:\s*([^\n]+)',
        r'AGRAVADO:\s*([^\n]+)',
        r'REQUERENTE:\s*([^\n]+)',
        r'REQUERIDO:\s*([^\n]+)',
        r'PACIENTE:\s*([^\n]+)',
        r'COATOR:\s*([^\n]+)'
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
    cluster_name = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    cluster_description = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    article_reference = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    source = scrapy.Field(
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
    """Item for jurisprudence (court decisions) from STJ"""
    
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
    
    # STJ-specific fields for full decision text extraction
    numero_unico = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Raw text from textarea #textSemformatacao1
    raw_text = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Original textarea container (audit field)
    raw_container_html = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Quality assessment score (calculated by pipeline)
    content_quality = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Processing metadata
    captured_at_utc = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    success = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    errors = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    input_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    decision_url = scrapy.Field(
        output_processor=TakeFirst()
    )