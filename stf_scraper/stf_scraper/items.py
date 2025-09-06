# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from itemloaders.processors import TakeFirst, MapCompose, Compose
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


def extract_case_number(text):
    """Extract Brazilian legal case number from text"""
    if not text:
        return None
    # Pattern for Brazilian case numbers: 0000000-00.0000.0.00.0000
    pattern = r'(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})'
    match = re.search(pattern, text)
    return match.group(1) if match else None


def normalize_url(url):
    """Normalize and validate URLs"""
    if not url:
        return None
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return None
    return url


class LegalDocumentItem(scrapy.Item):
    """Base item for Brazilian legal documents"""
    
    # Theme and source information
    theme = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    source_site = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    tribunal = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Document identification
    title = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    case_number = scrapy.Field(
        input_processor=MapCompose(extract_case_number),
        output_processor=TakeFirst()
    )
    
    document_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # Content
    summary = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    content = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    keywords = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=list
    )
    
    # Dates
    publication_date = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    decision_date = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Legal specifics
    legal_area = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    subject_matter = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=list
    )
    
    court_level = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    # URL and metadata
    url = scrapy.Field(
        input_processor=MapCompose(normalize_url),
        output_processor=TakeFirst()
    )
    
    scraped_at = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Quality indicators
    content_quality = scrapy.Field(
        output_processor=TakeFirst()
    )


class JurisprudenciaItem(LegalDocumentItem):
    """Item for jurisprudence (court decisions)"""
    
    # Court decision specifics
    judge_rapporteur = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    decision_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    parties_involved = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=list
    )
    
    voting_result = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    appeal_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )

