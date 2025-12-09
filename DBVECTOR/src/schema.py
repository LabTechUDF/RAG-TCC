"""
Schema de dados para documentos jurídicos.
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List


@dataclass
class Doc:
    """Documento jurídico com metadados estruturados."""
    id: str
    text: str
    title: Optional[str] = None
    court: Optional[str] = None  # Tribunal (STF, STJ, etc.)
    code: Optional[str] = None   # Código/Lei (CF/88, CC, etc.)
    article: Optional[str] = None # Artigo específico
    date: Optional[str] = None   # Data ISO 8601
    meta: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário, removendo valores None."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Doc":
        """Cria Doc a partir de dicionário, ignorando campos desconhecidos e mapeando variações."""
        # Mapeamento de campos alternativos
        mapped_data = {}
        
        # Mapeia 'id' (obrigatório) - usa case_number, raw_seq_documento ou hash como fallback
        if 'id' in data:
            mapped_data['id'] = data['id']
        elif 'case_number' in data and data['case_number']:
            # Prioridade 1: usa case_number como ID (documentos STJ/STF)
            mapped_data['id'] = str(data['case_number'])
        elif 'raw_seq_documento' in data and data['raw_seq_documento']:
            # Prioridade 2: usa raw_seq_documento (documentos STJ)
            mapped_data['id'] = str(data['raw_seq_documento'])
        else:
            # Fallback: gera ID baseado no título + url ou hash do conteúdo
            import hashlib
            id_source = data.get('url', '') or data.get('title', '') or data.get('content', '')
            mapped_data['id'] = hashlib.md5(id_source.encode()).hexdigest()[:16]
        
        # Mapeia 'text' (obrigatório) - pode vir como 'content'
        if 'text' in data:
            mapped_data['text'] = data['text']
        elif 'content' in data:
            mapped_data['text'] = data['content']
        else:
            mapped_data['text'] = ""  # Fallback vazio
        
        # Campos opcionais diretos
        if 'title' in data:
            mapped_data['title'] = data['title']
        if 'court' in data:
            mapped_data['court'] = data['court']
        if 'code' in data:
            mapped_data['code'] = data['code']
        if 'article' in data:
            mapped_data['article'] = data['article']
        if 'date' in data:
            mapped_data['date'] = data['date']
        
        # Campos extras vão para meta
        known_fields = {'id', 'text', 'content', 'title', 'court', 'code', 'article', 'date', 'meta'}
        extra_fields = {k: v for k, v in data.items() if k not in known_fields}
        
        if extra_fields or 'meta' in data:
            mapped_data['meta'] = data.get('meta', {})
            if isinstance(mapped_data['meta'], dict):
                mapped_data['meta'].update(extra_fields)
            else:
                mapped_data['meta'] = extra_fields
        
        return cls(**mapped_data)


@dataclass 
class SearchResult:
    """Resultado de busca com score."""
    doc: Doc
    score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para API."""
        return {
            "id": self.doc.id,
            "title": self.doc.title,
            "text": self.doc.text,
            "court": self.doc.court,
            "code": self.doc.code,
            "article": self.doc.article,
            "date": self.doc.date,
            "meta": self.doc.meta,
            "score": self.score
        }


@dataclass
class SearchRequest:
    """Request de busca via API."""
    q: str
    k: int = 5


@dataclass 
class SearchResponse:
    """Response de busca via API."""
    results: List[SearchResult]
    query: str
    total: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para API."""
        return {
            "query": self.query,
            "total": self.total,
            "results": [r.to_dict() for r in self.results]
        }


def get_dummy_docs() -> List[Doc]:
    """Retorna documentos dummy para testes e desenvolvimento."""
    return [
        Doc(
            id="cf88_art5",
            title="Constituição Federal - Art. 5º",
            text="Todos são iguais perante a lei, sem distinção de qualquer natureza, garantindo-se aos brasileiros e aos estrangeiros residentes no País a inviolabilidade do direito à vida, à liberdade, à igualdade, à segurança e à propriedade. Os direitos fundamentais são cláusulas pétreas e não podem ser abolidos nem mesmo por emenda constitucional.",
            court="Constituição Federal",
            code="CF/88",
            article="5º",
            date="1988-10-05",
            meta={"tipo": "constitucional", "capitulo": "direitos_fundamentais"}
        ),
        Doc(
            id="stf_hc_123456",
            title="STF - Habeas Corpus 123.456",
            text="O direito à liberdade de locomoção é garantia fundamental prevista no art. 5º, XV, da Constituição Federal. A prisão preventiva deve ser fundamentada em requisitos legais específicos, não podendo decorrer de mera conveniência da instrução criminal. Habeas corpus concedido para determinar a soltura do paciente.",
            court="STF",
            code="HC",
            article="123456",
            date="2024-03-15",
            meta={"tipo": "jurisprudencia", "classe": "habeas_corpus", "relator": "Min. Roberto Barroso"}
        ),
        Doc(
            id="cc_art197",
            title="Código Civil - Art. 197 (Prescrição)",
            text="Não corre a prescrição entre cônjuges, na constância da sociedade conjugal. A prescrição é instituto que visa à estabilidade das relações jurídicas, mas deve respeitar vínculos familiares especiais onde há presunção de confiança mútua.",
            court="Legislação Civil", 
            code="CC",
            article="197",
            date="2002-01-10",
            meta={"tipo": "legislacao", "livro": "parte_geral", "titulo": "prescricao_decadencia"}
        ),
        Doc(
            id="cc_art178",
            title="Código Civil - Art. 178 (Decadência)",
            text="É de quatro anos o prazo de decadência para pleitear-se a anulação do negócio jurídico, contado no caso de coação, do dia em que ela cessar. A decadência distingue-se da prescrição por atingir o próprio direito, e não apenas a pretensão de exercê-lo.",
            court="Legislação Civil",
            code="CC", 
            article="178",
            date="2002-01-10",
            meta={"tipo": "legislacao", "livro": "parte_geral", "titulo": "prescricao_decadencia"}
        ),
        Doc(
            id="stj_resp_987654",
            title="STJ - REsp 987.654 (Direito do Consumidor)",
            text="A responsabilidade civil do fornecedor de serviços é objetiva, conforme art. 14 do CDC. Comprovado o dano e o nexo causal, prescinde-se da demonstração de culpa. O consumidor tem direito à reparação integral dos danos materiais e morais sofridos em decorrência de vício ou defeito na prestação do serviço.",
            court="STJ",
            code="REsp", 
            article="987654",
            date="2023-11-20",
            meta={"tipo": "jurisprudencia", "classe": "recurso_especial", "materia": "direito_consumidor"}
        )
    ]