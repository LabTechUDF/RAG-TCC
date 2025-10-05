"""
STJ SCON Parsers - Regex patterns and parsing functions for STJ decisions
"""
import re
from typing import Optional, Dict, List


def extract_case_number_from_content(content: str) -> Optional[str]:
    """Extract case number from STJ decision content"""
    if not content:
        return None
    
    # Patterns for STJ case numbers (ARESP, RESP, etc.)
    patterns = [
        r'(ARESP\s*\d+(?:\.\d+)*)',
        r'(RESP\s*\d+(?:\.\d+)*)',
        r'(RHC\s*\d+(?:\.\d+)*)',
        r'(HC\s*\d+(?:\.\d+)*)',
        r'(MS\s*\d+(?:\.\d+)*)',
        r'(MC\s*\d+(?:\.\d+)*)',
        r'(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})'  # Número único
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def extract_relator_from_content(content: str) -> Optional[str]:
    """Extract relator name from STJ decision content"""
    if not content:
        return None
    
    patterns = [
        r'RELATOR[A]?:\s*MINISTR[OA]\s*([A-ZÁÊÔÇÀÃÕÉ\s\-]+)',
        r'Relator\(a\):\s*Min\.?\s*([A-ZÁÊÔÇÀÃÕÉ\s\-]+)',
        r'Rel\.?\s*Min\.?\s*([A-ZÁÊÔÇÀÃÕÉ\s\-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            relator = match.group(1).strip()
            # Clean up the name (remove extra spaces, etc.)
            relator = re.sub(r'\s+', ' ', relator)
            return relator
    
    return None


def extract_decision_date_from_content(content: str) -> Optional[str]:
    """Extract decision date from STJ content"""
    if not content:
        return None
    
    patterns = [
        r'Brasília\s*,\s*(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        r'Data do Julgamento:\s*(\d{2}/\d{2}/\d{4})',
        r'Julgamento:\s*(\d{2}/\d{2}/\d{4})',
        r'Julgado em:\s*(\d{2}/\d{2}/\d{4})'
    ]
    
    # Month mapping for Portuguese months
    months = {
        'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
        'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
        'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
    }
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            if i == 0:  # Brasília format
                day, month_name, year = match.groups()
                month = months.get(month_name.lower(), '01')
                return f"{day.zfill(2)}/{month}/{year}"
            else:  # DD/MM/YYYY format
                return match.group(1)
    
    return None


def extract_publication_date_from_content(content: str) -> Optional[str]:
    """Extract publication date from STJ content"""
    if not content:
        return None
    
    patterns = [
        r'DJe\s*(\d{2}/\d{2}/\d{4})',
        r'DJ\s*(\d{2}/\d{2}/\d{4})',
        r'Publicação:\s*(\d{2}/\d{2}/\d{4})',
        r'Data de Publicação:\s*(\d{2}/\d{2}/\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def extract_partes_from_content(content: str) -> Optional[str]:
    """Extract parties information from STJ decision content"""
    if not content:
        return None
    
    patterns = [
        r'RECORRENTE:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'RECORRIDO:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'IMPETRANTE:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'IMPETRADO:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'AGRAVANTE:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'AGRAVADO:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'REQUERENTE:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'REQUERIDO:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'PACIENTE:\s*([^\n]+(?:\n[^\n:]+)*)',
        r'COATOR:\s*([^\n]+(?:\n[^\n:]+)*)'
    ]
    
    partes = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Clean up the text
            parte = re.sub(r'\s+', ' ', match.strip())
            if parte and len(parte) > 3:  # Avoid very short matches
                partes.append(parte)
    
    return '; '.join(partes) if partes else None


def clean_textarea_content(raw_content: str) -> str:
    """Clean and normalize textarea content from STJ"""
    if not raw_content:
        return ""
    
    # Remove extra whitespaces and normalize line breaks
    content = re.sub(r'\r\n', '\n', raw_content)
    content = re.sub(r'\r', '\n', content)
    content = re.sub(r'\n\s*\n', '\n\n', content)  # Normalize multiple line breaks
    content = re.sub(r'[ \t]+', ' ', content)  # Normalize spaces and tabs
    
    return content.strip()


def extract_uf_from_content(content: str) -> Optional[str]:
    """Extract UF (state) from STJ decision content"""
    if not content:
        return None
    
    # Common UF patterns in STJ decisions
    pattern = r'(?:COMARCA|ESTADO|UF):\s*([A-Z]{2})'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        return match.group(1).upper()
    
    # Alternative: look for state abbreviations in specific contexts
    states = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 
              'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 
              'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']
    
    pattern = r'\b(' + '|'.join(states) + r')\b'
    match = re.search(pattern, content)
    
    if match:
        return match.group(1)
    
    return None


def is_valid_stj_decision(content: str) -> bool:
    """Check if content appears to be a valid STJ decision"""
    if not content or len(content.strip()) < 100:
        return False
    
    # Check for STJ-specific indicators
    stj_indicators = [
        'SUPERIOR TRIBUNAL DE JUSTIÇA',
        'STJ',
        'RELATORA',
        'RELATOR',
        'ARESP',
        'RESP',
        'RECURSO ESPECIAL'
    ]
    
    content_upper = content.upper()
    indicators_found = sum(1 for indicator in stj_indicators if indicator in content_upper)
    
    # Should have at least 2 indicators for a valid decision
    return indicators_found >= 2