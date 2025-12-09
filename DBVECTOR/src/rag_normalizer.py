"""
Serviço de Normalização Jurídica (Query Rewriting).
Transforma consultas em linguagem natural para queries técnico-jurídicas otimizadas para RAG.
"""
import os
import json
import logging
from typing import Optional
from openai import OpenAI
from anthropic import Anthropic

from src.rag_schemas import QueryNormalizadaOutput, DadosExecucaoPenal

log = logging.getLogger(__name__)


# ========================================
# TEMPLATE DO NORMALIZADOR JURÍDICO
# ========================================

TEMPLATE_NORMALIZADOR = """Você é um assistente jurídico especializado em execução penal e no sistema SEEU (Sistema Eletrônico de Execução Unificado).

**TAREFA:**
Analise a consulta do usuário e extraia informações estruturadas para busca em base de jurisprudência.

**REGRAS IMPORTANTES:**
1. NÃO invente fatos ou dados não mencionados pelo usuário
2. Use `null` quando a informação não estiver disponível
3. Use terminologia jurídica brasileira (CPP, CP, LEP, HC, progressão, remição, etc.)
4. Identifique a INTENÇÃO principal (buscar jurisprudência, entender requisitos, analisar benefício, etc.)
5. Reescreva a pergunta em linguagem técnico-jurídica para busca vetorial eficiente
6. Se houver ambiguidades, explique em "observacoes"

**CONTEXTO DO USUÁRIO:**
{contexto_adicional}

**CONSULTA DO USUÁRIO:**
"{prompt_usuario}"

**SAÍDA ESPERADA:**
Retorne APENAS um JSON válido no seguinte formato (sem markdown, sem explicações):

{{
  "intencao": "<string: objetivo principal da consulta>",
  "tipoBeneficioOuTema": "<string: benefício ou tema jurídico identificado>",
  "dadosExecucaoPenal": {{
    "regimeAtual": "<string ou null>",
    "tempoCumpridoAproximado": "<string ou null>",
    "faltasGraves": "<string ou null>",
    "tipoCrime": "<string ou null>",
    "outrosDadosRelevantes": "<string ou null>"
  }},
  "temaExecucao": ["<tema1>", "<tema2>"],
  "palavrasChaveJuridicas": ["<termo1>", "<termo2>"],
  "queryRAG": "<pergunta reescrita em linguagem jurídica técnica>",
  "observacoes": "<ambiguidades ou informações faltantes, ou null>"
}}

**EXEMPLOS DE TEMAS DE EXECUÇÃO:**
- progressao_regime
- remicao
- livramento_condicional
- prisao_preventiva
- execucao_provisoria
- falta_grave
- regressao_regime
- saida_temporaria
- detração
- comutacao_pena

Retorne apenas o JSON:"""


# ========================================
# SERVIÇO DE NORMALIZAÇÃO
# ========================================

class LegalQueryNormalizer:
    """Normalizador de queries jurídicas usando LLM."""
    
    def __init__(
        self,
        provider: str = "openai",  # "openai" ou "anthropic"
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Inicializa o normalizador.
        
        Args:
            provider: Provedor do LLM ("openai" ou "anthropic")
            model: Nome do modelo (default: gpt-4o-mini ou claude-3-haiku-20240307)
            api_key: Chave da API (se None, usa variável de ambiente)
        """
        self.provider = provider.lower()
        
        # Configuração por provider
        if self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY não configurada")
            self.client = OpenAI(api_key=api_key)
            
        elif self.provider == "anthropic":
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY não configurada")
            self.client = Anthropic(api_key=api_key)
            
        else:
            raise ValueError(f"Provider não suportado: {provider}")
        
        log.info(f"Normalizador inicializado: {self.provider} / {self.model}")
    
    def normalizar(
        self,
        prompt_usuario: str,
        contexto_adicional: Optional[str] = None
    ) -> QueryNormalizadaOutput:
        """
        Normaliza query do usuário para formato estruturado.
        
        Args:
            prompt_usuario: Pergunta original do usuário
            contexto_adicional: Contexto extra (metadados, histórico, etc.)
            
        Returns:
            QueryNormalizadaOutput com query normalizada
            
        Raises:
            Exception: Se houver erro na chamada do LLM ou parsing
        """
        # Monta prompt
        contexto = contexto_adicional or "Nenhum contexto adicional fornecido."
        prompt_final = TEMPLATE_NORMALIZADOR.format(
            prompt_usuario=prompt_usuario,
            contexto_adicional=contexto
        )
        
        log.debug(f"Normalizando query: {prompt_usuario[:100]}...")
        
        try:
            # Chama LLM
            resposta_raw = self._chamar_llm(prompt_final)
            
            # Parse JSON
            query_normalizada = self._parse_resposta(resposta_raw)
            
            log.info(f"Query normalizada: {query_normalizada.queryRAG}")
            return query_normalizada
            
        except Exception as e:
            log.error(f"Erro ao normalizar query: {e}")
            # Fallback: retorna query original sem normalização
            return self._fallback_normalizacao(prompt_usuario)
    
    def _chamar_llm(self, prompt: str) -> str:
        """Chama o LLM apropriado."""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um normalizador de queries jurídicas. Retorne apenas JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return response.choices[0].message.content.strip()
        
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        
        raise ValueError(f"Provider não suportado: {self.provider}")
    
    def _parse_resposta(self, resposta_raw: str) -> QueryNormalizadaOutput:
        """
        Parse da resposta JSON do LLM.
        Remove markdown fences se presentes.
        """
        # Remove markdown fences se presentes
        resposta_limpa = resposta_raw.strip()
        if resposta_limpa.startswith("```json"):
            resposta_limpa = resposta_limpa[7:]
        if resposta_limpa.startswith("```"):
            resposta_limpa = resposta_limpa[3:]
        if resposta_limpa.endswith("```"):
            resposta_limpa = resposta_limpa[:-3]
        resposta_limpa = resposta_limpa.strip()
        
        # Parse JSON
        try:
            data = json.loads(resposta_limpa)
        except json.JSONDecodeError as e:
            log.error(f"Erro ao fazer parse do JSON: {e}")
            log.error(f"Resposta recebida: {resposta_raw}")
            raise ValueError(f"LLM retornou JSON inválido: {e}")
        
        # Valida e converte para Pydantic
        try:
            return QueryNormalizadaOutput(**data)
        except Exception as e:
            log.error(f"Erro ao validar schema: {e}")
            log.error(f"Dados recebidos: {data}")
            raise ValueError(f"Resposta do LLM não corresponde ao schema esperado: {e}")
    
    def _fallback_normalizacao(self, prompt_usuario: str) -> QueryNormalizadaOutput:
        """
        Fallback quando normalização falha.
        Retorna estrutura mínima com query original.
        """
        log.warning("Usando fallback de normalização")
        return QueryNormalizadaOutput(
            intencao="consulta_jurisprudencia",
            tipoBeneficioOuTema="desconhecido",
            dadosExecucaoPenal=DadosExecucaoPenal(),
            temaExecucao=[],
            palavrasChaveJuridicas=[],
            queryRAG=prompt_usuario,  # Usa query original
            observacoes="Normalização automática falhou. Usando query original."
        )


# ========================================
# SINGLETON GLOBAL (LAZY LOADING)
# ========================================

_normalizer_instance: Optional[LegalQueryNormalizer] = None


def get_normalizer() -> LegalQueryNormalizer:
    """
    Retorna instância singleton do normalizador.
    Inicializa apenas quando necessário.
    """
    global _normalizer_instance
    if _normalizer_instance is None:
        provider = os.getenv("LLM_PROVIDER", "openai")
        _normalizer_instance = LegalQueryNormalizer(provider=provider)
    return _normalizer_instance
