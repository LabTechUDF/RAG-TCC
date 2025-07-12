"""
Parser utilities for Brazilian legal content using BeautifulSoup.
Handles common patterns found in Brazilian legal websites.
"""

import logging
from typing import Dict, List, Optional, Union, Any
from bs4 import BeautifulSoup, Tag
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class BrazilianLegalParser:
    """Parser for Brazilian legal content with specific patterns and formats."""
    
    def __init__(self, html_content: str):
        """
        Initialize parser with HTML content.
        
        Args:
            html_content: Raw HTML content to parse
        """
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.brazilian_months = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }
        
    def extract_by_selectors(self, selectors: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract content using CSS selectors from config.
        
        Args:
            selectors: Dictionary of field names to CSS selectors
            
        Returns:
            Dictionary with extracted content
        """
        extracted = {}
        
        for field, selector in selectors.items():
            try:
                elements = self.soup.select(selector)
                if elements:
                    if len(elements) == 1:
                        extracted[field] = self._clean_text(elements[0].get_text())
                    else:
                        extracted[field] = [self._clean_text(elem.get_text()) for elem in elements]
                else:
                    extracted[field] = None
                    logger.debug(f"No elements found for selector: {selector}")
                    
            except Exception as e:
                logger.warning(f"Error extracting {field} with selector {selector}: {e}")
                extracted[field] = None
                
        return extracted
        
    def extract_legal_document_info(self, item_element: Tag) -> Dict[str, Any]:
        """
        Extract standard legal document information.
        
        Args:
            item_element: BeautifulSoup Tag representing a legal document
            
        Returns:
            Dictionary with standardized legal document fields
        """
        info = {
            'title': None,
            'date': None,
            'court': None,
            'document_type': None,
            'case_number': None,
            'summary': None,
            'link': None,
            'pdf_link': None
        }
        
        # Title extraction
        title_selectors = ['h1', 'h2', 'h3', '.title', '.titulo', '.ementa']
        info['title'] = self._extract_first_match(item_element, title_selectors)
        
        # Date extraction
        date_selectors = ['.date', '.data', '.data-publicacao', 'time']
        date_text = self._extract_first_match(item_element, date_selectors)
        if date_text:
            info['date'] = self._parse_brazilian_date(date_text)
            
        # Court/Tribunal extraction
        court_selectors = ['.tribunal', '.court', '.orgao', '.origem']
        info['court'] = self._extract_first_match(item_element, court_selectors)
        
        # Case number extraction
        case_patterns = [
            r'(\d{7}-\d{2}\.\d{4}\.\d{1}\.\d{2}\.\d{4})',  # Standard format
            r'(\d{4}\.\d{2}\.\d{2}\.\d{6})',              # Alternative format
            r'(Processo\s*n[º°]\s*[\d\.\-/]+)',           # Process number
        ]
        info['case_number'] = self._extract_case_number(item_element, case_patterns)
        
        # Document type
        type_selectors = ['.type', '.tipo', '.classe']
        info['document_type'] = self._extract_first_match(item_element, type_selectors)
        
        # Summary/Abstract
        summary_selectors = ['.summary', '.resumo', '.ementa', '.decisao']
        info['summary'] = self._extract_first_match(item_element, summary_selectors)
        
        # Links
        info['link'] = self._extract_main_link(item_element)
        info['pdf_link'] = self._extract_pdf_link(item_element)
        
        return info
        
    def extract_jurisprudencia(self, item_element: Tag) -> Dict[str, Any]:
        """
        Extract jurisprudence-specific information.
        
        Args:
            item_element: BeautifulSoup Tag representing jurisprudence
            
        Returns:
            Dictionary with jurisprudence-specific fields
        """
        base_info = self.extract_legal_document_info(item_element)
        
        # Additional jurisprudence fields
        jurisprudence_info = {
            'relator': None,
            'classe_processual': None,
            'origem': None,
            'precedente': None,
            'temas': []
        }
        
        # Relator (Judge/Rapporteur)
        relator_selectors = ['.relator', '.ministro', '.desembargador']
        jurisprudence_info['relator'] = self._extract_first_match(item_element, relator_selectors)
        
        # Process class
        class_selectors = ['.classe', '.classe-processual']
        jurisprudence_info['classe_processual'] = self._extract_first_match(item_element, class_selectors)
        
        # Origin
        origin_selectors = ['.origem', '.procedencia', '.instancia']
        jurisprudence_info['origem'] = self._extract_first_match(item_element, origin_selectors)
        
        # Themes/Keywords
        theme_selectors = ['.temas', '.palavras-chave', '.keywords', '.assuntos']
        themes = self._extract_first_match(item_element, theme_selectors)
        if themes:
            jurisprudence_info['temas'] = [theme.strip() for theme in themes.split(',')]
            
        return {**base_info, **jurisprudence_info}
        
    def extract_sumula(self, item_element: Tag) -> Dict[str, Any]:
        """
        Extract Súmula-specific information.
        
        Args:
            item_element: BeautifulSoup Tag representing a Súmula
            
        Returns:
            Dictionary with Súmula-specific fields
        """
        sumula_info = {
            'numero': None,
            'texto': None,
            'tipo': None,  # Vinculante, Comum, etc.
            'tribunal': None,
            'data_aprovacao': None,
            'cancelada': False,
            'alteracoes': []
        }
        
        # Súmula number
        number_patterns = [
            r'Súmula\s*n[º°]\s*(\d+)',
            r'Súmula\s*(\d+)',
            r'Enunciado\s*(\d+)'
        ]
        sumula_info['numero'] = self._extract_number_pattern(item_element, number_patterns)
        
        # Súmula text
        text_selectors = ['.texto', '.enunciado', '.sumula-texto', 'p']
        sumula_info['texto'] = self._extract_first_match(item_element, text_selectors)
        
        # Type (Vinculante, etc.)
        if 'vinculante' in item_element.get_text().lower():
            sumula_info['tipo'] = 'Vinculante'
        else:
            sumula_info['tipo'] = 'Comum'
            
        # Tribunal
        tribunal_selectors = ['.tribunal', '.orgao', '.stf', '.stj']
        sumula_info['tribunal'] = self._extract_first_match(item_element, tribunal_selectors)
        
        # Check if cancelled
        if any(word in item_element.get_text().lower() for word in ['cancelada', 'revogada', 'superada']):
            sumula_info['cancelada'] = True
            
        return sumula_info
        
    def _extract_first_match(self, element: Tag, selectors: List[str]) -> Optional[str]:
        """Extract text from first matching selector."""
        for selector in selectors:
            found = element.select_one(selector)
            if found:
                return self._clean_text(found.get_text())
        return None
        
    def _extract_case_number(self, element: Tag, patterns: List[str]) -> Optional[str]:
        """Extract case number using regex patterns."""
        text = element.get_text()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
        
    def _extract_number_pattern(self, element: Tag, patterns: List[str]) -> Optional[str]:
        """Extract number using regex patterns."""
        text = element.get_text()
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
        
    def _extract_main_link(self, element: Tag) -> Optional[str]:
        """Extract main link from element."""
        # Look for main link
        link = element.find('a', href=True)
        if link:
            return link['href']
        return None
        
    def _extract_pdf_link(self, element: Tag) -> Optional[str]:
        """Extract PDF link from element."""
        # Look for PDF links
        pdf_link = element.find('a', href=lambda x: x and '.pdf' in x.lower())
        if pdf_link:
            return pdf_link['href']
        return None
        
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common legal document artifacts
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\r+', ' ', text)
        text = re.sub(r'\t+', ' ', text)
        
        return text.strip()
        
    def _parse_brazilian_date(self, date_text: str) -> Optional[str]:
        """
        Parse Brazilian date formats to ISO format.
        
        Args:
            date_text: Date text in Portuguese format
            
        Returns:
            ISO format date string or None if parsing fails
        """
        if not date_text:
            return None
            
        # Clean the date text
        date_text = self._clean_text(date_text.lower())
        
        # Common Brazilian date patterns
        patterns = [
            r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',  # 15 de janeiro de 2024
            r'(\d{1,2})/(\d{1,2})/(\d{4})',             # 15/01/2024
            r'(\d{1,2})-(\d{1,2})-(\d{4})',             # 15-01-2024
            r'(\d{4})-(\d{1,2})-(\d{1,2})',             # 2024-01-15
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    if 'de' in pattern:  # Portuguese format
                        day, month_name, year = match.groups()
                        month = self.brazilian_months.get(month_name)
                        if month:
                            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        groups = match.groups()
                        if len(groups) == 3:
                            if groups[0].isdigit() and len(groups[0]) == 4:  # Year first
                                year, month, day = groups
                            else:  # Day first
                                day, month, year = groups
                            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except Exception as e:
                    logger.warning(f"Error parsing date {date_text}: {e}")
                    
        return None 