"""
Query Builder - Módulo para otimização de consultas RAG
Gera string de busca canônica baseada em metadados e contexto
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re


@dataclass
class QueryContext:
    """Contexto da query com metadados extraídos"""
    user_query: str
    cluster_hints: List[str] = None
    court_filter: Optional[str] = None
    date_range: Optional[tuple] = None
    article_filter: Optional[str] = None
    conversation_history: List[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.cluster_hints is None:
            self.cluster_hints = []
        if self.conversation_history is None:
            self.conversation_history = []


@dataclass
class CanonicalQuery:
    """Query canônica otimizada para busca vetorial"""
    optimized_text: str
    filters: Dict[str, Any]
    metadata: Dict[str, Any]
    requires_clarification: bool = False
    clarification_questions: List[str] = None
    
    def __post_init__(self):
        if self.clarification_questions is None:
            self.clarification_questions = []


class QueryBuilder:
    """
    Constrói queries canônicas otimizadas para o sistema RAG jurídico.
    
    Segue o fluxo descrito na Figura 4.5 do TCC:
    1. Analisa query do usuário
    2. Extrai metadados e intenção
    3. Identifica filtros aplicáveis (tribunal, cluster, data, artigo)
    4. Gera query otimizada para busca vetorial
    5. Identifica necessidade de esclarecimento
    """
    
    # Padrões de tribunais
    TRIBUNAL_PATTERNS = {
        r'\b(STF|Supremo)\b': 'STF',
        r'\b(STJ|Superior)\b': 'STJ',
        r'\b(TST|Trabalho)\b': 'TST',
        r'\b(TSE|Eleitoral)\b': 'TSE',
        r'\bTRF\b': 'TRF',
        r'\bTJ[A-Z]{2}\b': 'TJ'
    }
    
    # Padrões de artigos/códigos
    ARTICLE_PATTERNS = [
        r'art(?:igo)?\.?\s*(\d+)',
        r'(?:CP|Código Penal).*?art\.?\s*(\d+)',
        r'(?:CPP|Código de Processo Penal).*?art\.?\s*(\d+)'
    ]
    
    def __init__(self):
        self.stats = {
            'queries_processed': 0,
            'queries_with_filters': 0,
            'clarifications_requested': 0
        }
    
    def build_canonical_query(self, context: QueryContext) -> CanonicalQuery:
        """
        Constrói query canônica a partir do contexto.
        
        Args:
            context: QueryContext com query original e metadados
            
        Returns:
            CanonicalQuery otimizada para busca vetorial
        """
        self.stats['queries_processed'] += 1
        
        # 1. Extrai metadados da query
        extracted_filters = self._extract_filters(context.user_query)
        
        # 2. Combina com filtros explícitos do contexto
        filters = {
            'court': context.court_filter or extracted_filters.get('court'),
            'article': context.article_filter or extracted_filters.get('article'),
            'date_range': context.date_range,
            'clusters': context.cluster_hints
        }
        
        # Remove filtros None
        filters = {k: v for k, v in filters.items() if v is not None}
        
        # 3. Otimiza texto da query
        optimized_text = self._optimize_query_text(
            context.user_query,
            context.conversation_history
        )
        
        # 4. Verifica se precisa de esclarecimento
        needs_clarification, questions = self._check_clarification_needed(
            context, extracted_filters
        )
        
        if needs_clarification:
            self.stats['clarifications_requested'] += 1
        
        if filters:
            self.stats['queries_with_filters'] += 1
        
        return CanonicalQuery(
            optimized_text=optimized_text,
            filters=filters,
            metadata={
                'original_query': context.user_query,
                'has_history': len(context.conversation_history) > 0,
                'extracted_entities': extracted_filters
            },
            requires_clarification=needs_clarification,
            clarification_questions=questions
        )
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extrai filtros estruturados da query"""
        filters = {}
        
        # Extrai tribunal
        for pattern, court in self.TRIBUNAL_PATTERNS.items():
            if re.search(pattern, query, re.IGNORECASE):
                filters['court'] = court
                break
        
        # Extrai artigos
        for pattern in self.ARTICLE_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                filters['article'] = match.group(1)
                break
        
        return filters
    
    def _optimize_query_text(
        self,
        query: str,
        history: List[Dict[str, str]]
    ) -> str:
        """
        Otimiza texto da query para busca vetorial.
        
        - Remove stopwords menos relevantes
        - Adiciona contexto do histórico se disponível
        - Expande abreviações jurídicas comuns
        """
        # Expande abreviações comuns
        expansions = {
            r'\bCP\b': 'Código Penal',
            r'\bCPP\b': 'Código de Processo Penal',
            r'\bCF\b': 'Constituição Federal',
            r'\bCC\b': 'Código Civil'
        }
        
        optimized = query
        for abbrev, full in expansions.items():
            optimized = re.sub(abbrev, full, optimized, flags=re.IGNORECASE)
        
        # Se há histórico recente, adiciona contexto
        if history:
            last_exchange = history[-1]
            if 'user' in last_exchange:
                # Extrai termos-chave do contexto anterior
                context_keywords = self._extract_keywords(last_exchange['user'])
                if context_keywords:
                    optimized = f"{optimized} (contexto: {', '.join(context_keywords[:3])})"
        
        return optimized.strip()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extrai palavras-chave relevantes do texto"""
        # Remove stopwords básicas
        stopwords = {'o', 'a', 'de', 'da', 'do', 'em', 'no', 'na', 'para', 'como', 'que'}
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        return keywords[:5]  # Top 5 keywords
    
    def _check_clarification_needed(
        self,
        context: QueryContext,
        extracted_filters: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Verifica se a query precisa de esclarecimento.
        
        Returns:
            (needs_clarification, list_of_questions)
        """
        questions = []
        
        # Query muito curta ou vaga
        if len(context.user_query.split()) < 3:
            questions.append(
                "Sua pergunta é muito breve. Poderia fornecer mais detalhes sobre o que procura?"
            )
        
        # Múltiplos tribunais mencionados
        tribunal_mentions = sum(
            1 for pattern in self.TRIBUNAL_PATTERNS.keys()
            if re.search(pattern, context.user_query, re.IGNORECASE)
        )
        if tribunal_mentions > 1:
            questions.append(
                "Você mencionou múltiplos tribunais. Qual tribunal específico você gostaria de consultar?"
            )
        
        # Termos ambíguos
        ambiguous_terms = ['isso', 'aquilo', 'esse caso', 'aquele processo']
        if any(term in context.user_query.lower() for term in ambiguous_terms):
            if not context.conversation_history:
                questions.append(
                    "Você mencionou termos que requerem contexto anterior. Poderia especificar a que se refere?"
                )
        
        return len(questions) > 0, questions
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de uso do QueryBuilder"""
        return self.stats.copy()
