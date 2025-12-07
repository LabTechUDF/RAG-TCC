"""
Query Optimizer com LangChain para RAG jurídico.

Este módulo usa LLMs via LangChain para otimizar queries de busca,
extrair filtros estruturados e decidir quando é necessário esclarecimento.
"""
import os
import json
from typing import Dict, List, Optional, Any
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from src.tools.query_builder import QueryContext, CanonicalQuery


# Prompt otimizado para análise de queries jurídicas
QUERY_OPTIMIZATION_PROMPT = """Você é um assistente especializado em análise de consultas jurídicas.

Sua tarefa é analisar a consulta do usuário e retornar um JSON estruturado com:
1. "optimized_text": Versão otimizada da query para busca semântica
2. "requires_clarification": true/false se a query é ambígua ou precisa mais informações
3. "clarification_questions": Lista de perguntas para esclarecer (vazia se não precisa)
4. "filters": Objeto com filtros estruturados extraídos:
   - "court": Tribunal mencionado (STF, STJ, TST, TSE, TRF, TJ, ou null)
   - "article": Artigo mencionado (número ou null)
   - "date_range": Período mencionado (objeto com start/end ou null)

CONSULTA DO USUÁRIO:
{user_query}

CONTEXTO ADICIONAL:
- Clusters relacionados: {cluster_hints}
- Histórico da conversa: {conversation_history}

INSTRUÇÕES:
- Para "optimized_text": expanda abreviações (CP → Código Penal, CPP → Código de Processo Penal, etc.)
- Se a query menciona termos vagos como "isso", "aquilo" sem histórico, marque requires_clarification=true
- Se múltiplos tribunais são mencionados sem especificar, marque requires_clarification=true
- Queries muito curtas (< 3 palavras) geralmente precisam de esclarecimento
- Seja objetivo e retorne APENAS o JSON, sem explicações adicionais

FORMATO DE SAÍDA (JSON válido):
{{
  "optimized_text": "texto otimizado da query",
  "requires_clarification": false,
  "clarification_questions": [],
  "filters": {{
    "court": null,
    "article": null,
    "date_range": null
  }}
}}

JSON:"""


class QueryOptimizer:
    """
    Otimizador de queries usando LangChain e LLMs.
    
    Integra com o fluxo RAG conforme TCC (Figura 4.5):
    - Recebe query bruta do usuário
    - Usa LLM para entender intenção e extrair metadados
    - Gera query canônica otimizada para busca vetorial
    - Identifica necessidade de esclarecimento
    """
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: Optional[str] = None
    ):
        """
        Inicializa QueryOptimizer com LLM.
        
        Args:
            model_name: Nome do modelo OpenAI a usar
            temperature: Temperatura para geração (0.0 = determinístico)
            api_key: API key da OpenAI (usa OPENAI_API_KEY env var se None)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("⚠️ OPENAI_API_KEY não configurada. QueryOptimizer usará fallback simples.")
            self.llm = None
            self.prompt = None
        else:
            # Inicializa LLM
            self.llm = ChatOpenAI(
                model=model_name,
                temperature=temperature,
                api_key=self.api_key
            )
            
            # Cria prompt template
            self.prompt = PromptTemplate(
                input_variables=["user_query", "cluster_hints", "conversation_history"],
                template=QUERY_OPTIMIZATION_PROMPT
            )
        
        self.stats = {
            'queries_optimized': 0,
            'llm_calls': 0,
            'fallback_used': 0,
            'errors': 0
        }
    
    def optimize_query(self, context: QueryContext) -> CanonicalQuery:
        """
        Otimiza query usando LLM.
        
        Args:
            context: QueryContext com query original e metadados
            
        Returns:
            CanonicalQuery otimizada com filtros e decisão de esclarecimento
        """
        self.stats['queries_optimized'] += 1
        
        # Se LLM não disponível, usa fallback simples
        if self.llm is None:
            return self._fallback_optimization(context)
        
        try:
            # Prepara inputs para o LLM
            cluster_hints_str = ", ".join(context.cluster_hints) if context.cluster_hints else "nenhum"
            history_str = self._format_history(context.conversation_history)
            
            # Chama LLM usando LCEL
            self.stats['llm_calls'] += 1
            chain = self.prompt | self.llm
            result = chain.invoke({
                "user_query": context.user_query,
                "cluster_hints": cluster_hints_str,
                "conversation_history": history_str
            })
            
            # Parse da resposta JSON
            llm_output = result.content if hasattr(result, 'content') else str(result)
            parsed = self._parse_llm_response(llm_output)
            
            # Combina filtros do LLM com filtros explícitos do contexto
            filters = parsed.get("filters", {})
            if context.court_filter:
                filters["court"] = context.court_filter
            if context.article_filter:
                filters["article"] = context.article_filter
            if context.date_range:
                filters["date_range"] = context.date_range
            if context.cluster_hints:
                filters["clusters"] = context.cluster_hints
            
            # Remove filtros None
            filters = {k: v for k, v in filters.items() if v is not None}
            
            return CanonicalQuery(
                optimized_text=parsed.get("optimized_text", context.user_query),
                filters=filters,
                metadata={
                    "original_query": context.user_query,
                    "optimization_method": "llm",
                    "has_history": len(context.conversation_history) > 0
                },
                requires_clarification=parsed.get("requires_clarification", False),
                clarification_questions=parsed.get("clarification_questions", [])
            )
            
        except Exception as e:
            print(f"⚠️ Erro ao otimizar query com LLM: {e}")
            self.stats['errors'] += 1
            return self._fallback_optimization(context)
    
    def _fallback_optimization(self, context: QueryContext) -> CanonicalQuery:
        """
        Otimização simples sem LLM (fallback).
        Usa heurísticas básicas do QueryBuilder original.
        """
        self.stats['fallback_used'] += 1
        
        # Import aqui para evitar circular dependency
        from src.tools.query_builder import QueryBuilder
        builder = QueryBuilder()
        return builder.build_canonical_query(context)
    
    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Formata histórico de conversa para o prompt"""
        if not history:
            return "nenhum histórico"
        
        formatted = []
        for i, exchange in enumerate(history[-3:]):  # Últimas 3 interações
            if "user" in exchange:
                formatted.append(f"Usuário: {exchange['user']}")
            if "assistant" in exchange:
                formatted.append(f"Assistente: {exchange['assistant']}")
        
        return "\n".join(formatted) if formatted else "nenhum histórico"
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse da resposta JSON do LLM.
        Trata erros comuns de formatação.
        """
        try:
            # Remove markdown code blocks se presentes
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
            
            # Remove "json" tag se presente
            response = response.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            parsed = json.loads(response)
            
            # Validação básica da estrutura
            if not isinstance(parsed, dict):
                raise ValueError("Resposta não é um objeto JSON")
            
            # Garante campos obrigatórios
            parsed.setdefault("optimized_text", "")
            parsed.setdefault("requires_clarification", False)
            parsed.setdefault("clarification_questions", [])
            parsed.setdefault("filters", {})
            
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Erro ao parsear JSON do LLM: {e}")
            print(f"Resposta recebida: {response[:200]}")
            # Retorna estrutura mínima válida
            return {
                "optimized_text": "",
                "requires_clarification": False,
                "clarification_questions": [],
                "filters": {}
            }
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de uso do QueryOptimizer"""
        return self.stats.copy()
