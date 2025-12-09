"""
Utilitário para buscar documentos diretamente no merged_clean.jsonl.
Útil para encontrar documentos por case_number, processo ou outros campos
sem depender do índice FAISS.
"""
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

log = logging.getLogger(__name__)


class DocumentFinder:
    """Busca documentos diretamente no JSONL."""
    
    def __init__(self, jsonl_path: str = "data/merged_clean.jsonl"):
        self.jsonl_path = Path(jsonl_path)
        if not self.jsonl_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {jsonl_path}")
    
    def find_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca documento por ID, tentando múltiplas estratégias.
        
        Estratégias de busca (em ordem):
        1. Match exato por case_number
        2. Match exato por raw_seq_documento
        3. Match por substring em case_number (extrai números do doc_id)
        4. Match por tribunal + número extraído
        
        Args:
            doc_id: ID do documento (pode ser case_number, raw_seq, ou formato misto)
            
        Returns:
            Dict com dados do documento ou None se não encontrado
        """
        log.info(f"Buscando documento: {doc_id}")
        
        # Extrai números do doc_id (ex: "stj_hc_280533" -> ["280533"])
        extracted_numbers = re.findall(r'\d{4,}', doc_id)
        
        # Extrai tribunal se presente (ex: "stj_hc_280533" -> "STJ")
        tribunal_match = re.match(r'^(stj|stf|seeu)_', doc_id.lower())
        tribunal_hint = tribunal_match.group(1).upper() if tribunal_match else None
        
        log.debug(f"Números extraídos: {extracted_numbers}, Tribunal: {tribunal_hint}")
        
        # Estratégia 1: Busca por match exato
        doc = self._find_exact_match(doc_id, extracted_numbers)
        if doc:
            log.info(f"✓ Documento encontrado (match exato)")
            return doc
        
        # Estratégia 2: Busca por tribunal + número
        if tribunal_hint and extracted_numbers:
            doc = self._find_by_tribunal_and_number(tribunal_hint, extracted_numbers)
            if doc:
                log.info(f"✓ Documento encontrado (tribunal + número)")
                return doc
        
        # Estratégia 3: Busca ampla por números
        if extracted_numbers:
            doc = self._find_by_numbers(extracted_numbers)
            if doc:
                log.info(f"✓ Documento encontrado (busca ampla)")
                return doc
        
        log.warning(f"Documento não encontrado: {doc_id}")
        return None
    
    def _find_exact_match(
        self, 
        doc_id: str, 
        extracted_numbers: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Busca por match exato em case_number ou raw_seq_documento."""
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    doc = json.loads(line)
                    
                    # Match exato por case_number
                    case_number = doc.get('case_number')
                    if case_number and str(case_number) == doc_id:
                        return doc
                    
                    # Match exato por raw_seq_documento
                    raw_seq = doc.get('raw_seq_documento')
                    if raw_seq and str(raw_seq) == doc_id:
                        return doc
                    
                    # Match por números extraídos em case_number
                    if case_number and extracted_numbers:
                        case_number_str = str(case_number)
                        for num in extracted_numbers:
                            if num == case_number_str:
                                return doc
                    
                    # Match por números extraídos em raw_seq_documento
                    if raw_seq and extracted_numbers:
                        raw_seq_str = str(raw_seq)
                        for num in extracted_numbers:
                            if num == raw_seq_str:
                                return doc
                    
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _find_by_tribunal_and_number(
        self, 
        tribunal: str, 
        numbers: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Busca por tribunal + número.
        
        Lógica específica por tribunal:
        - STJ/STF: busca em case_number, raw_seq_documento
        - SEEU: busca em campos específicos do SEEU
        """
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    doc = json.loads(line)
                    
                    # Verifica tribunal
                    doc_tribunal = doc.get('tribunal', '').upper()
                    if doc_tribunal != tribunal:
                        continue
                    
                    # Busca números em campos relevantes
                    case_number = str(doc.get('case_number', ''))
                    raw_seq = str(doc.get('raw_seq_documento', ''))
                    title = str(doc.get('title', ''))
                    
                    for num in numbers:
                        # Match em case_number (substring)
                        if num in case_number:
                            return doc
                        
                        # Match em raw_seq_documento (substring)
                        if num in raw_seq:
                            return doc
                        
                        # Match em título (para alguns casos)
                        if num in title:
                            return doc
                    
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _find_by_numbers(self, numbers: List[str]) -> Optional[Dict[str, Any]]:
        """
        Busca ampla por números em qualquer campo relevante.
        Retorna o primeiro match encontrado.
        """
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    doc = json.loads(line)
                    
                    # Verifica se é documento jurídico (não SEEU)
                    if not doc.get('tribunal'):
                        continue
                    
                    # Busca em campos relevantes
                    case_number = str(doc.get('case_number', ''))
                    raw_seq = str(doc.get('raw_seq_documento', ''))
                    
                    for num in numbers:
                        if num in case_number or num in raw_seq:
                            return doc
                    
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def find_all_by_tribunal(
        self, 
        tribunal: str, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retorna todos os documentos de um tribunal específico.
        
        Args:
            tribunal: STF, STJ, etc.
            limit: Número máximo de documentos
            
        Returns:
            Lista de documentos
        """
        docs = []
        with open(self.jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    doc = json.loads(line)
                    if doc.get('tribunal', '').upper() == tribunal.upper():
                        docs.append(doc)
                        if len(docs) >= limit:
                            break
                except json.JSONDecodeError:
                    continue
        
        return docs


# Singleton global para reutilização
_finder_instance: Optional[DocumentFinder] = None


def get_document_finder() -> DocumentFinder:
    """Retorna instância singleton do DocumentFinder."""
    global _finder_instance
    if _finder_instance is None:
        _finder_instance = DocumentFinder()
    return _finder_instance
