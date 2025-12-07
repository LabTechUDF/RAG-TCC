"""
Document Loaders para documentos jurídicos.

Este módulo fornece utilitários para carregar documentos de scrapers
e outros fontes, convertendo para formatos compatíveis com LangChain e src.schema.
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

from langchain_core.documents import Document as LangChainDocument
from langchain_community.document_loaders import JSONLoader
from langchain_community.document_loaders.base import BaseLoader

from src.schema import Doc


class LegalDocumentLoader:
    """
    Carregador unificado para documentos jurídicos.
    
    Suporta:
    - JSONL (scraper output)
    - JSON (single doc ou array)
    - Conversão para LangChain Document
    - Conversão para src.schema.Doc
    """
    
    @staticmethod
    def load_jsonl(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Carrega arquivo JSONL (uma linha = um documento JSON).
        
        Args:
            file_path: Caminho para arquivo .jsonl
            
        Returns:
            Lista de dicionários representando documentos
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        documents = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    doc = json.loads(line)
                    documents.append(doc)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Erro ao parsear linha {line_num} de {file_path}: {e}")
                    continue
        
        return documents
    
    @staticmethod
    def load_json(file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Carrega arquivo JSON (objeto único ou array).
        
        Args:
            file_path: Caminho para arquivo .json
            
        Returns:
            Lista de dicionários representando documentos
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Se é um array, retorna direto
        if isinstance(data, list):
            return data
        
        # Se é objeto único, retorna como lista de 1 elemento
        if isinstance(data, dict):
            return [data]
        
        raise ValueError(f"Formato JSON inválido em {file_path}")
    
    @staticmethod
    def to_schema_docs(raw_docs: List[Dict[str, Any]]) -> List[Doc]:
        """
        Converte dicionários brutos para src.schema.Doc.
        
        Args:
            raw_docs: Lista de dicionários com campos do documento
            
        Returns:
            Lista de objetos Doc
        """
        schema_docs = []
        
        for raw_doc in raw_docs:
            # Campos obrigatórios
            if 'id' not in raw_doc or 'text' not in raw_doc:
                print(f"⚠️ Documento sem id ou text: {raw_doc.keys()}")
                continue
            
            # Extrai campos opcionais
            doc = Doc(
                id=raw_doc['id'],
                text=raw_doc['text'],
                title=raw_doc.get('title'),
                court=raw_doc.get('court'),
                code=raw_doc.get('code'),
                article=raw_doc.get('article'),
                date=raw_doc.get('date'),
                meta=raw_doc.get('meta', {})
            )
            
            schema_docs.append(doc)
        
        return schema_docs
    
    @staticmethod
    def to_langchain_docs(
        raw_docs: List[Dict[str, Any]],
        text_field: str = 'text',
        metadata_fields: Optional[List[str]] = None
    ) -> List[LangChainDocument]:
        """
        Converte dicionários brutos para LangChain Documents.
        
        Args:
            raw_docs: Lista de dicionários
            text_field: Nome do campo que contém o texto principal
            metadata_fields: Lista de campos a incluir nos metadados (None = todos)
            
        Returns:
            Lista de LangChain Documents
        """
        langchain_docs = []
        
        for raw_doc in raw_docs:
            if text_field not in raw_doc:
                print(f"⚠️ Campo '{text_field}' não encontrado em documento")
                continue
            
            # Extrai texto
            page_content = raw_doc[text_field]
            
            # Extrai metadados
            if metadata_fields is None:
                # Inclui todos os campos exceto o text_field
                metadata = {k: v for k, v in raw_doc.items() if k != text_field}
            else:
                # Inclui apenas campos especificados
                metadata = {k: raw_doc.get(k) for k in metadata_fields if k in raw_doc}
            
            doc = LangChainDocument(
                page_content=page_content,
                metadata=metadata
            )
            
            langchain_docs.append(doc)
        
        return langchain_docs
    
    @classmethod
    def from_scraper_output(
        cls,
        file_path: Union[str, Path],
        format: str = 'jsonl'
    ) -> List[Doc]:
        """
        Carrega documentos de output de scraper (STF/STJ).
        
        Args:
            file_path: Caminho para arquivo de output
            format: Formato do arquivo ('jsonl' ou 'json')
            
        Returns:
            Lista de objetos Doc
        """
        # Carrega dados brutos
        if format == 'jsonl':
            raw_docs = cls.load_jsonl(file_path)
        elif format == 'json':
            raw_docs = cls.load_json(file_path)
        else:
            raise ValueError(f"Formato não suportado: {format}")
        
        # Converte para schema
        return cls.to_schema_docs(raw_docs)


class DirectoryLoader(BaseLoader):
    """
    Loader customizado para carregar múltiplos arquivos de um diretório.
    
    Útil para processar output de scrapers em batch.
    """
    
    def __init__(
        self,
        directory: Union[str, Path],
        glob_pattern: str = "*.jsonl",
        loader_cls: type = LegalDocumentLoader
    ):
        """
        Args:
            directory: Diretório contendo arquivos
            glob_pattern: Padrão glob para filtrar arquivos
            loader_cls: Classe loader a usar
        """
        self.directory = Path(directory)
        self.glob_pattern = glob_pattern
        self.loader_cls = loader_cls
    
    def load(self) -> List[Doc]:
        """
        Carrega todos os arquivos do diretório.
        
        Returns:
            Lista de objetos Doc de todos os arquivos
        """
        all_docs = []
        
        for file_path in self.directory.glob(self.glob_pattern):
            try:
                print(f"📄 Carregando {file_path.name}...")
                
                # Detecta formato pelo sufixo
                if file_path.suffix == '.jsonl':
                    docs = self.loader_cls.from_scraper_output(file_path, format='jsonl')
                elif file_path.suffix == '.json':
                    docs = self.loader_cls.from_scraper_output(file_path, format='json')
                else:
                    print(f"⚠️ Formato não suportado: {file_path.suffix}")
                    continue
                
                all_docs.extend(docs)
                print(f"  ✓ {len(docs)} documentos carregados")
                
            except Exception as e:
                print(f"❌ Erro ao carregar {file_path}: {e}")
                continue
        
        print(f"\n✅ Total: {len(all_docs)} documentos carregados de {self.directory}")
        return all_docs


# Funções de conveniência
def load_stf_jurisprudence(file_path: Union[str, Path]) -> List[Doc]:
    """Carrega jurisprudência do STF (formato scraper)"""
    return LegalDocumentLoader.from_scraper_output(file_path, format='jsonl')


def load_stj_decisions(file_path: Union[str, Path]) -> List[Doc]:
    """Carrega decisões do STJ (formato scraper)"""
    return LegalDocumentLoader.from_scraper_output(file_path, format='jsonl')


def load_legal_directory(directory: Union[str, Path], pattern: str = "*.jsonl") -> List[Doc]:
    """Carrega todos os documentos jurídicos de um diretório"""
    loader = DirectoryLoader(directory, glob_pattern=pattern)
    return loader.load()
