"""Inicialização do módulo loaders."""
from src.loaders.legal_document_loader import (
    LegalDocumentLoader,
    DirectoryLoader,
    load_stf_jurisprudence,
    load_stj_decisions,
    load_legal_directory
)

__all__ = [
    'LegalDocumentLoader',
    'DirectoryLoader',
    'load_stf_jurisprudence',
    'load_stj_decisions',
    'load_legal_directory'
]
