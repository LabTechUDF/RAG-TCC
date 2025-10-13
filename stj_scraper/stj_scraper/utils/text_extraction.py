"""
Text extraction and content processing utilities
"""
import re
from typing import Optional, Tuple, Dict, List


class LegalTextProcessor:
    """Process and extract information from legal texts"""
    
    def __init__(self):
        self.article_patterns = self._compile_article_patterns()
    
    def _compile_article_patterns(self):
        """Compile regex patterns for article detection"""
        return [
            # CP (Código Penal) patterns - more specific first
            (re.compile(r'\b(?:art\.?\s*|artigo\s*)(\d+)(?:-?[A-Z])?(?:\s*do\s*)?(?:CP|Código\s*Penal)', re.IGNORECASE), 'CP', 'Código Penal'),
            (re.compile(r'\bCP\s*art\.?\s*(\d+)(?:-?[A-Z])?', re.IGNORECASE), 'CP', 'Código Penal'),
            
            # CPP (Código de Processo Penal) patterns
            (re.compile(r'\b(?:art\.?\s*|artigo\s*)(\d+)(?:-?[A-Z])?(?:\s*do\s*)?(?:CPP|Código\s*de\s*Processo\s*Penal)', re.IGNORECASE), 'CPP', 'Código de Processo Penal'),
            (re.compile(r'\bCPP\s*art\.?\s*(\d+)(?:-?[A-Z])?', re.IGNORECASE), 'CPP', 'Código de Processo Penal'),
            
            # Generic article patterns (less specific, fallback)
            (re.compile(r'\b(?:art\.?\s*|artigo\s*)(\d+)(?:-?[A-Z])?', re.IGNORECASE), 'Generic', 'Artigo'),
        ]
    
    def extract_article_info(self, content: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract article information from legal text"""
        if not content:
            return None, None, None
        
        # Try each pattern in order of specificity
        for pattern, code, description in self.article_patterns:
            matches = pattern.findall(content)
            if matches:
                # Take the first/most prominent article found
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
    
    def extract_case_number(self, title: str) -> Optional[str]:
        """Extract case number from decision title"""
        if not title:
            return None
        
        # Common STJ case number patterns
        patterns = [
            r'(?:REsp|RESP|HC|ARE|RE|RHC|MC|AgRg|EDcl|AgInt)\s+(\d+)',  # Standard legal acronyms
            r'(\d{7,})',  # Long numeric sequences (7+ digits)
            r'(\d{4}\.\d{6,})',  # Formatted numbers with dots
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def extract_relator(self, content: str) -> Optional[str]:
        """Extract relator (reporting judge) from content"""
        if not content:
            return None
        
        # Patterns for relator extraction
        patterns = [
            r'Relator\(a\):\s*(?:Min\.?\s*|Ministra?\s*|Des\.?\s*|Desembargadora?\s*)([A-ZÁÊÔÇÀÃÕÉÍÚÝ\s\.]+)',
            r'RELATOR\(A\):\s*(?:MIN\.?\s*|MINISTRA?\s*|DES\.?\s*|DESEMBARGADORA?\s*)([A-ZÁÊÔÇÀÃÕÉÍÚÝ\s\.]+)',
            r'(?:Min\.?\s*|Ministra?\s*|Des\.?\s*|Desembargadora?\s*)([A-ZÁÊÔÇÀÃÕÉÍÚÝ\s\.]+)(?:\s*\(Relator)', 
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                relator = match.group(1).strip()
                # Clean up the name (remove extra spaces, dots at the end)
                relator = re.sub(r'\s+', ' ', relator)
                relator = relator.rstrip('.')
                if len(relator) > 3:  # Valid judge name should be at least 3 chars
                    return relator
        
        return None
    
    def extract_partes(self, content: str) -> Optional[str]:
        """Extract parties information from content"""
        if not content:
            return None
        
        # Patterns for parties extraction
        patterns = [
            r'(?:Impetrante|IMPETRANTE):\s*([^\n\r]+)',
            r'(?:Paciente|PACIENTE):\s*([^\n\r]+)',
            r'(?:Requerente|REQUERENTE):\s*([^\n\r]+)',
            r'(?:Agravante|AGRAVANTE):\s*([^\n\r]+)',
            r'(?:Recorrente|RECORRENTE):\s*([^\n\r]+)',
            r'(?:Autor|AUTOR):\s*([^\n\r]+)',
            r'(?:Réu|RÉU):\s*([^\n\r]+)',
        ]
        
        partes = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                clean_parte = match.strip()
                if len(clean_parte) > 2:
                    partes.append(clean_parte)
        
        return '; '.join(partes) if partes else None
    
    def extract_decision(self, content: str) -> Optional[str]:
        """Extract decision/ruling from content"""
        if not content:
            return None
        
        # Look for decision sections
        patterns = [
            r'(?:DECISÃO|DECISAO|ACÓRDÃO|ACORDAO|EMENTA):\s*([^\n\r]{50,500})',
            r'(?:Decisão|Decisao|Acórdão|Acordao|Ementa):\s*([^\n\r]{50,500})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                decision = match.group(1).strip()
                # Clean up decision text
                decision = re.sub(r'\s+', ' ', decision)
                return decision
        
        return None
    
    def extract_legislacao(self, content: str) -> Optional[str]:
        """Extract referenced legislation from content"""
        if not content:
            return None
        
        # Look for legislation references
        patterns = [
            r'(?:Lei\s+n[ºo°]?\s*\d+[./]\d+)',
            r'(?:Decreto\s+n[ºo°]?\s*\d+[./]\d+)',
            r'(?:Portaria\s+n[ºo°]?\s*\d+[./]\d+)',
            r'(?:Resolução\s+n[ºo°]?\s*\d+[./]\d+)',
            r'(?:CF|Constituição\s*Federal)',
            r'(?:CC|Código\s*Civil)',
            r'(?:CPC|Código\s*de\s*Processo\s*Civil)',
            r'(?:CLT|Consolidação\s*das\s*Leis\s*do\s*Trabalho)',
        ]
        
        legislacao_found = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            legislacao_found.extend(matches)
        
        # Remove duplicates and return
        unique_legislacao = list(dict.fromkeys(legislacao_found))  # Preserve order
        return '; '.join(unique_legislacao) if unique_legislacao else None
    
    def is_monocratic_decision(self, json_record: Dict) -> bool:
        """Determine if a decision is monocratic based on JSON metadata"""
        
        # Check tipo_documento first
        tipo_documento = json_record.get('tipoDocumento', '').upper()
        if tipo_documento != 'DECISÃO' and tipo_documento != 'DECISAO':
            return False
        
        # Look for monocratic indicators
        monocratic_indicators = [
            'tipoDecisao',
            'decisaoMonocratica', 
            'monocratica',
            'individual',
            'singular'
        ]
        
        for indicator in monocratic_indicators:
            value = json_record.get(indicator)
            if value:
                # Check boolean true or string indicating monocratic
                if isinstance(value, bool) and value:
                    return True
                elif isinstance(value, str) and any(
                    keyword in value.lower() for keyword in ['monocr', 'individual', 'singular']
                ):
                    return True
        
        # Fallback heuristic: if it's a "DECISÃO" and has certain patterns
        # This is a conservative approach
        return tipo_documento in ['DECISÃO', 'DECISAO']
    
    def clean_content(self, content: str) -> str:
        """Clean and normalize legal text content"""
        if not content:
            return content
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove common OCR artifacts
        content = re.sub(r'[^\w\s\-\.,;:()áâãàéêçíîóôõúû]', ' ', content, flags=re.IGNORECASE)
        
        # Normalize spacing around punctuation
        content = re.sub(r'\s*([.,;:])\s*', r'\1 ', content)
        
        return content.strip()