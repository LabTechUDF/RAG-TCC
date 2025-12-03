# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from itemloaders.processors import TakeFirst, MapCompose
from w3lib.html import remove_tags, strip_html5_whitespace
import re
from datetime import datetime


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


def normalize_epoch_date(timestamp):
    """Convert epoch timestamp (milliseconds) to YYYY-MM-DD format"""
    if not timestamp:
        return None
    
    try:
        # Handle both seconds and milliseconds
        if isinstance(timestamp, str):
            timestamp = int(timestamp)
        
        # If timestamp is in milliseconds, convert to seconds
        if timestamp > 9999999999:  # If greater than year 2286 in seconds, it's likely milliseconds
            timestamp = timestamp / 1000
        
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d')
    except (ValueError, OSError) as e:
        return None


def extract_case_number_from_title(title):
    """Extract case number from title (e.g., 'REsp 1890871' -> '1890871')"""
    if not title:
        return None
    
    # Pattern to match legal case numbers in titles
    patterns = [
        r'(?:REsp|RESP|HC|ARE|RE|RHC|MC|AgRg|EDcl|AgInt)\s+(\d+)',  # Standard patterns
        r'(\d{7,})',  # Generic long number
        r'(\d{4}\.\d{6,})',  # Formatted number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def infer_article_from_content(content):
    """Infer article reference from content using robust regex"""
    if not content:
        return None, None, None
    
    # Common article patterns in legal documents
    article_patterns = [
        # CP (Código Penal) patterns
        (r'\b(?:art\.?\s*|artigo\s*)(\d+)(?:-?[A-Z])?(?:\s*do\s*)?(?:CP|Código\s*Penal)', 'CP', 'Código Penal'),
        (r'\bCP\s*art\.?\s*(\d+)(?:-?[A-Z])?', 'CP', 'Código Penal'),
        
        # CPP (Código de Processo Penal) patterns  
        (r'\b(?:art\.?\s*|artigo\s*)(\d+)(?:-?[A-Z])?(?:\s*do\s*)?(?:CPP|Código\s*de\s*Processo\s*Penal)', 'CPP', 'Código de Processo Penal'),
        (r'\bCPP\s*art\.?\s*(\d+)(?:-?[A-Z])?', 'CPP', 'Código de Processo Penal'),
        
        # Generic article patterns
        (r'\b(?:art\.?\s*|artigo\s*)(\d+)(?:-?[A-Z])?', 'Generic', 'Artigo'),
    ]
    
    for pattern, code, description in article_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # Take the first/most common article found
            article = matches[0]
            cluster_name = f"art_{article}"
            
            if code == 'CP':
                cluster_desc = f"Código Penal art. {article}"
                article_ref = f"CP art. {article}"
            elif code == 'CPP':
                cluster_desc = f"Código de Processo Penal art. {article}"  
                article_ref = f"CPP art. {article}"
            else:
                cluster_desc = f"Artigo {article}"
                article_ref = f"art. {article}"
            
            return cluster_name, cluster_desc, article_ref
    
    return None, None, None


class STJDecisionItem(scrapy.Item):
    """Item for STJ monocratic decisions"""
    
    # Core RAG fields
    cluster_name = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    cluster_description = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    article_reference = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    code_family = scrapy.Field(
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
    
    content = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
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
    
    relator = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    publication_date = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    decision_date = scrapy.Field(
        output_processor=TakeFirst()
    )
    
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
    
    content_quality = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Trace fields for full provenance
    trace = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Raw JSON fields from STJ dataset (for debugging/validation)
    raw_seq_documento = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    raw_tipo_documento = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    raw_tipo_decisao = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    raw_data_publicacao = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    raw_data_decisao = scrapy.Field(
        output_processor=TakeFirst()
    )