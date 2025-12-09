"""
Serviço RAG Orquestrador para consultas jurídicas SEEU.
Coordena: normalização → busca vetorial → LLM → resposta estruturada.
"""
import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from openai import OpenAI
from anthropic import Anthropic

from src.rag_schemas import (
    RagQueryRequest,
    RagQueryResponse,
    QueryNormalizadaOutput,
    ChunkWithScore,
    ChunkMetadata,
    TeseJuridica,
    JurisprudenciaReferencia
)
from src.rag_normalizer import get_normalizer
from src.storage.base import VectorStore
from src.schema import SearchResult
from src import embeddings

log = logging.getLogger(__name__)


# ========================================
# TEMPLATE DO PROMPT FINAL SEEU
# ========================================

TEMPLATE_RAG_SEEU = """Você é um assistente jurídico especializado em **execução penal** e no sistema **SEEU** (Sistema Eletrônico de Execução Unificado).

**CONTEXTO DA CONSULTA:**
Query original do usuário: "{query_original}"
Query normalizada (técnica): "{query_normalizada}"

**DADOS DE EXECUÇÃO PENAL IDENTIFICADOS:**
{dados_execucao}

**TEMAS RELACIONADOS:**
{temas_execucao}

**PALAVRAS-CHAVE JURÍDICAS:**
{palavras_chave}

**DOCUMENTOS JURISPRUDENCIAIS RECUPERADOS:**

{documentos_contexto}

---

**SUA TAREFA:**
Com base EXCLUSIVAMENTE nos documentos acima e nos dados de execução penal fornecidos, elabore uma análise jurídica estruturada.

**ESTRUTURA DA RESPOSTA (JSON):**

{{
  "contexto_seeu": "<Explique brevemente o contexto da execução penal e como o SEEU se relaciona com o caso>",
  
  "teses": [
    {{
      "titulo": "<Título da tese jurídica>",
      "descricao": "<Explicação detalhada da tese com base na jurisprudência>",
      "documentosSuporte": [<lista de IDs dos documentos que sustentam esta tese>]
    }}
  ],
  
  "aplicacao_caso": "<Aplicação prática ao caso concreto, considerando os dados de execução penal fornecidos>",
  
  "jurisprudencias": [
    {{
      "docId": <ID do documento>,
      "tribunal": "<Tribunal>",
      "processo": "<Número do processo>",
      "ano": <Ano da decisão>,
      "tema": "<Tema principal>",
      "relevanciaRelativa": <Relevância em %>,
      "trechoUtilizado": "<Trecho específico que fundamenta a análise>"
    }}
  ],
  
  "avisos_limitacoes": "<Avisos sobre limitações da análise e caráter meramente informativo>"
}}

**REGRAS CRÍTICAS:**
1. Use APENAS informações presentes nos documentos fornecidos
2. NÃO invente números de processo, datas ou fatos
3. Para cada tese, cite os documentos que a sustentam (use os IDs: Documento 1, 2, 3...)
4. Na seção "jurisprudencias", inclua TODOS os documentos relevantes com seus trechos
5. A relevância relativa já está calculada - use o valor fornecido
6. Se faltarem informações de execução penal, mencione isso em "avisos_limitacoes"
7. Mantenha linguagem técnico-jurídica mas compreensível

Retorne apenas o JSON (sem markdown):"""


# ========================================
# TEMPLATE MARKDOWN PARA UX JURÍDICA SEEU
# ========================================

TEMPLATE_RAG_SEEU_MARKDOWN = """Você é um assistente jurídico especializado em **execução penal** e no sistema **SEEU**.

**CONTEXTO DA CONSULTA:**
- Query original: "{query_original}"
- Query normalizada: "{query_normalizada}"

**DADOS DE EXECUÇÃO PENAL IDENTIFICADOS:**
{dados_execucao}

**TEMAS RELACIONADOS:** {temas_execucao}

**PALAVRAS-CHAVE JURÍDICAS:** {palavras_chave}

**DOCUMENTOS JURISPRUDENCIAIS RECUPERADOS:**

{documentos_contexto}

---

**SUA TAREFA:**
Gerar uma resposta em Markdown LIMPO e BEM FORMATADO, seguindo EXATAMENTE a estrutura abaixo.

**REGRAS DE FORMATAÇÃO CRÍTICAS:**
1. Use quebras de linha duplas entre seções (\\n\\n)
2. Use bullets (-) para listas
3. Use **negrito** para destacar informações importantes
4. Mantenha parágrafos curtos e diretos
5. Separe visualmente cada jurisprudência

---

## 📋 Resumo Objetivo

- [Bullet 1: Resposta direta à pergunta do usuário]
- [Bullet 2: Principais conclusões baseadas nos documentos]
- [Bullet 3: Limitações ou observações importantes]

---

## 📚 Documentos Analisados

**Documento 1 – [TRIBUNAL] – [PROCESSO] – [ANO]**
- **Relevância:** XX.X%
- **Tema:** [Resumo em 1 linha do tema central]

**Documento 2 – [TRIBUNAL] – [PROCESSO] – [ANO]**
- **Relevância:** XX.X%
- **Tema:** [Resumo em 1 linha do tema central]

[Repita para cada documento]

---

## ⚖️ Jurisprudências Relevantes

### 📌 [TRIBUNAL] – Processo nº [NÚMERO]

**📊 Relevância:** XX.X%  
**📅 Ano:** AAAA  
**🏛️ Relator(a):** [Nome do relator se disponível]  
**📑 Tema:** [Tema principal da decisão]

**💡 Trecho Relevante:**
> "[Trecho específico mais importante que fundamenta a análise, entre 2-4 linhas]"

---

### 📌 [TRIBUNAL] – Processo nº [NÚMERO]

[Repita a mesma estrutura para cada jurisprudência]

---

## ✅ Conclusão

- [Bullet 1: É possível ou não responder à pergunta com base nos documentos?]
- [Bullet 2: O que FALTA de informação, se for o caso]
- [Bullet 3: Leitura mais prudente diante da jurisprudência encontrada]
- [Bullet 4: Recomendações práticas para o caso]

---

## 🎯 Próximos Passos Sugeridos

1. **Legislação:**
   - Consultar LEP, artigos [X, Y, Z] que tratam de [tema]
   
2. **Pesquisa Complementar:**
   - Buscar jurisprudência específica no [TRIBUNAL] sobre "[palavras-chave]"
   
3. **Dados do Caso:**
   - Obter informação sobre [dado específico necessário]
   
4. **Documentação:**
   - Reunir documentos comprobatórios de [requisito específico]

---

## ⚠️ Avisos e Limitações

- ✓ Esta resposta tem caráter **informativo e consultivo**
- ✓ **NÃO substitui** análise técnico-jurídica completa do processo
- ✓ Baseada **exclusivamente** nos documentos retornados pelo sistema
- ✓ Recomenda-se consulta aos autos originais e verificação de jurisprudência mais recente

---

**REGRAS CRÍTICAS:**
1. Baseie-se APENAS nos documentos fornecidos
2. NÃO invente números de processos, tribunais, anos ou URLs
3. Se faltar informação, diga explicitamente o que falta
4. Mantenha SEMPRE a estrutura das seções conforme descrito acima
5. Use negrito para destacar pontos críticos e palavras-chave
6. Seja direto, mas respeitoso e técnico
7. Quando os documentos NÃO trazem a resposta, seja transparente
8. A relevância relativa já está calculada - use o valor fornecido

Retorne APENAS o texto em Markdown (sem código markdown com ```):"""


# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def calcular_relevancia_relativa(scores: List[float]) -> List[float]:
    """
    Calcula relevância em porcentagem diretamente do score.
    
    Args:
        scores: Lista de scores brutos de similaridade (0 a 1)
        
    Returns:
        Lista de relevâncias em porcentagem (score * 100)
    """
    if not scores:
        return []
    
    # Converte score diretamente para porcentagem
    relevancia_relativa = [score * 100 for score in scores]
    
    return relevancia_relativa


def agrupar_chunks_por_documento(
    chunks: List[ChunkWithScore]
) -> Dict[str, List[ChunkWithScore]]:
    """
    Agrupa chunks pelo ID do documento global.
    
    Returns:
        Dict com chave = idDocumentoGlobal, valor = lista de chunks
    """
    docs: Dict[str, List[ChunkWithScore]] = {}
    
    for chunk in chunks:
        doc_id = chunk.metadata.idDocumentoGlobal
        if doc_id not in docs:
            docs[doc_id] = []
        docs[doc_id].append(chunk)
    
    return docs


def montar_contexto_documentos(
    chunks_agrupados: Dict[str, List[ChunkWithScore]]
) -> str:
    """
    Monta string de contexto formatado para o LLM.
    
    Cada documento é numerado sequencialmente com metadados completos.
    """
    contexto_partes = []
    doc_numero = 1
    
    for doc_id, chunks in chunks_agrupados.items():
        # Ordena chunks por posição se disponível
        chunks_ordenados = sorted(
            chunks,
            key=lambda c: c.metadata.posicaoChunk or 0
        )
        
        # Pega metadados do primeiro chunk
        meta = chunks_ordenados[0].metadata
        
        # Cabeçalho do documento com formatação melhorada
        contexto_partes.append(f"═══════════════════════════════════════")
        contexto_partes.append(f"📄 DOCUMENTO {doc_numero}")
        contexto_partes.append(f"═══════════════════════════════════════")
        
        if meta.tribunal:
            contexto_partes.append(f"🏛️  Tribunal: {meta.tribunal}")
        if meta.numeroProcesso:
            contexto_partes.append(f"📋 Processo: {meta.numeroProcesso}")
        if meta.relator:
            contexto_partes.append(f"👤 Relator(a): {meta.relator}")
        if meta.dataJulgamento:
            contexto_partes.append(f"📅 Data Julgamento: {meta.dataJulgamento}")
        if meta.orgaoJulgador:
            contexto_partes.append(f"⚖️  Órgão Julgador: {meta.orgaoJulgador}")
        if meta.tema:
            contexto_partes.append(f"🔖 Tema: {meta.tema}")
        
        contexto_partes.append("")
        contexto_partes.append("📝 TRECHOS RELEVANTES:")
        contexto_partes.append("")
        
        # Chunks do documento
        for i, chunk in enumerate(chunks_ordenados, 1):
            relevancia = chunk.relevanciaRelativa or (chunk.score * 100)
            contexto_partes.append(f"▸ Trecho {i} (Relevância: {relevancia:.1f}%):")
            contexto_partes.append(f'  "{chunk.texto}"')
            contexto_partes.append("")
        
        doc_numero += 1
    
    return "\n".join(contexto_partes)


# ========================================
# SERVIÇO RAG
# ========================================

class RagService:
    """Serviço orquestrador de RAG jurídico."""
    
    def __init__(
        self,
        store: VectorStore,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Inicializa o serviço RAG.
        
        Args:
            store: Store vetorial (FAISS, OpenSearch, etc.)
            provider: Provedor do LLM ("openai" ou "anthropic")
            model: Nome do modelo
            api_key: Chave da API
        """
        self.store = store
        self.provider = provider.lower()
        
        # Configuração do LLM
        if self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY não configurada")
            self.client = OpenAI(api_key=api_key)
            
        elif self.provider == "anthropic":
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY não configurada")
            self.client = Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Provider não suportado: {provider}")
        
        log.info(f"RagService inicializado: {self.provider} / {self.model}")
    
    def processar_consulta(
        self,
        request: RagQueryRequest
    ) -> RagQueryResponse:
        """
        Processa consulta RAG completa.
        
        Fluxo:
        1. Normalização jurídica
        2. Busca vetorial
        3. Cálculo de relevância relativa
        4. Construção do prompt
        5. Chamada ao LLM
        6. Parse e estruturação da resposta
        
        Args:
            request: Request com prompt do usuário e metadados
            
        Returns:
            RagQueryResponse estruturada
        """
        log.info(f"Processando consulta RAG: {request.promptUsuario[:100]}...")
        
        # ETAPA 1: Normalização Jurídica
        normalizer = get_normalizer()
        contexto_meta = self._formatar_contexto_metadados(request.metadados)
        query_normalizada = normalizer.normalizar(
            prompt_usuario=request.promptUsuario,
            contexto_adicional=contexto_meta
        )
        
        log.info(f"Query normalizada: {query_normalizada.queryRAG}")
        
        # ETAPA 2: Busca Vetorial
        if not request.useRag:
            # Modo sem RAG - retorna resposta direta (TODO: implementar)
            return self._resposta_sem_rag(request, query_normalizada)
        
        chunks_recuperados = self._buscar_chunks(
            query_normalizada.queryRAG,
            k=request.k,
            metadados=request.metadados
        )
        
        if not chunks_recuperados:
            log.warning("Nenhum chunk recuperado")
            return self._resposta_vazia(request, query_normalizada)
        
        # ETAPA 3: Calcular Relevância Relativa
        scores = [c.score for c in chunks_recuperados]
        relevancia_relativa = calcular_relevancia_relativa(scores)
        
        for i, chunk in enumerate(chunks_recuperados):
            chunk.relevanciaRelativa = round(relevancia_relativa[i], 1)
        
        # ETAPA 4: Agrupar por Documento
        chunks_agrupados = agrupar_chunks_por_documento(chunks_recuperados)
        
        log.info(
            f"Recuperados {len(chunks_recuperados)} chunks de "
            f"{len(chunks_agrupados)} documentos únicos"
        )
        
        # ETAPA 5: Montar Prompt e Chamar LLM
        resposta_llm = self._gerar_resposta_llm(
            request.promptUsuario,
            query_normalizada,
            chunks_agrupados
        )
        
        # ETAPA 6: Estruturar Resposta Final
        resposta_final = self._estruturar_resposta(
            request,
            query_normalizada,
            chunks_recuperados,
            chunks_agrupados,
            resposta_llm
        )
        
        log.info("Consulta RAG processada com sucesso")
        return resposta_final
    
    def _formatar_contexto_metadados(self, metadados) -> str:
        """Formata metadados para contexto do normalizador."""
        if not metadados:
            return "Nenhum metadado adicional."
        
        partes = []
        if metadados.tribunal:
            partes.append(f"Tribunal: {metadados.tribunal}")
        if metadados.anoMin or metadados.anoMax:
            partes.append(f"Período: {metadados.anoMin or '?'} - {metadados.anoMax or '?'}")
        if metadados.tipoConsulta:
            partes.append(f"Tipo: {metadados.tipoConsulta}")
        
        return " | ".join(partes) if partes else "Nenhum metadado adicional."
    
    def _buscar_chunks(
        self,
        query: str,
        k: int,
        metadados
    ) -> List[ChunkWithScore]:
        """
        Executa busca vetorial e converte para ChunkWithScore.
        
        TODO: Implementar filtros de metadados quando store suportar.
        """
        # Gera embedding
        query_vector = embeddings.encode_single_text(query)
        
        # Busca no store
        resultados: List[SearchResult] = self.store.search(query_vector, k=k)
        
        # Converte para ChunkWithScore
        chunks = []
        for resultado in resultados:
            doc = resultado.doc
            
            # Extrai metadados do chunk
            meta_dict = doc.meta or {}
            metadata = ChunkMetadata(
                idDocumentoGlobal=meta_dict.get("idDocumentoGlobal", doc.id),
                idChunk=doc.id,
                tribunal=doc.court or meta_dict.get("tribunal"),
                numeroProcesso=meta_dict.get("numeroProcesso"),
                orgaoJulgador=meta_dict.get("orgaoJulgador"),
                relator=meta_dict.get("relator"),
                dataJulgamento=doc.date or meta_dict.get("dataJulgamento"),
                tema=meta_dict.get("tema"),
                fonte=meta_dict.get("fonte"),
                posicaoChunk=meta_dict.get("posicaoChunk"),
                totalChunks=meta_dict.get("totalChunks")
            )
            
            chunk = ChunkWithScore(
                texto=doc.text,
                metadata=metadata,
                score=resultado.score
            )
            chunks.append(chunk)
        
        return chunks
    
    def _gerar_resposta_llm(
        self,
        query_original: str,
        query_normalizada: QueryNormalizadaOutput,
        chunks_agrupados: Dict[str, List[ChunkWithScore]]
    ) -> Dict[str, Any]:
        """Gera resposta estruturada usando LLM."""
        
        # Formata dados de execução penal
        dados_exec = query_normalizada.dadosExecucaoPenal
        dados_exec_str = json.dumps(dados_exec.dict(), ensure_ascii=False, indent=2)
        
        # Formata temas e palavras-chave
        temas_str = ", ".join(query_normalizada.temaExecucao) if query_normalizada.temaExecucao else "Nenhum tema específico identificado"
        palavras_str = ", ".join(query_normalizada.palavrasChaveJuridicas) if query_normalizada.palavrasChaveJuridicas else "Nenhuma palavra-chave específica"
        
        # Monta contexto dos documentos
        contexto_docs = montar_contexto_documentos(chunks_agrupados)
        
        # Monta prompt final
        prompt = TEMPLATE_RAG_SEEU.format(
            query_original=query_original,
            query_normalizada=query_normalizada.queryRAG,
            dados_execucao=dados_exec_str,
            temas_execucao=temas_str,
            palavras_chave=palavras_str,
            documentos_contexto=contexto_docs
        )
        
        log.debug(f"Prompt final montado ({len(prompt)} chars)")
        
        # Chama LLM
        resposta_raw = self._chamar_llm(prompt)
        
        # Parse JSON
        return self._parse_resposta_llm(resposta_raw)
    
    def _chamar_llm(self, prompt: str) -> str:
        """Chama o LLM apropriado."""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você é um assistente jurídico especializado em execução penal. Retorne apenas JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=4000
            )
            return response.choices[0].message.content.strip()
        
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.4,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        
        raise ValueError(f"Provider não suportado: {self.provider}")
    
    def _parse_resposta_llm(self, resposta_raw: str) -> Dict[str, Any]:
        """Parse da resposta JSON do LLM."""
        # Remove markdown fences
        resposta_limpa = resposta_raw.strip()
        if resposta_limpa.startswith("```json"):
            resposta_limpa = resposta_limpa[7:]
        if resposta_limpa.startswith("```"):
            resposta_limpa = resposta_limpa[3:]
        if resposta_limpa.endswith("```"):
            resposta_limpa = resposta_limpa[:-3]
        resposta_limpa = resposta_limpa.strip()
        
        try:
            return json.loads(resposta_limpa)
        except json.JSONDecodeError as e:
            log.error(f"Erro ao fazer parse do JSON do LLM: {e}")
            log.error(f"Resposta recebida: {resposta_raw[:500]}")
            raise ValueError(f"LLM retornou JSON inválido: {e}")
    
    def _estruturar_resposta(
        self,
        request: RagQueryRequest,
        query_normalizada: QueryNormalizadaOutput,
        chunks_todos: List[ChunkWithScore],
        chunks_agrupados: Dict[str, List[ChunkWithScore]],
        resposta_llm: Dict[str, Any]
    ) -> RagQueryResponse:
        """Estrutura resposta final no formato RagQueryResponse."""
        
        # Extrai campos do LLM
        teses_llm = resposta_llm.get("teses", [])
        jurisp_llm = resposta_llm.get("jurisprudencias", [])
        
        # Converte para Pydantic
        teses = [TeseJuridica(**t) for t in teses_llm]
        jurisprudencias = [JurisprudenciaReferencia(**j) for j in jurisp_llm]
        
        return RagQueryResponse(
            queryOriginal=request.promptUsuario,
            queryNormalizada=query_normalizada,
            timestampConsulta=datetime.utcnow().isoformat(),
            contexto_seeu=resposta_llm.get("contexto_seeu", ""),
            teses=teses,
            aplicacao_caso=resposta_llm.get("aplicacao_caso", ""),
            jurisprudencias=jurisprudencias,
            avisos_limitacoes=resposta_llm.get("avisos_limitacoes", ""),
            backend=self.store.__class__.__name__,
            totalChunksRecuperados=len(chunks_todos),
            totalDocumentosUnicos=len(chunks_agrupados)
        )
    
    def _resposta_sem_rag(
        self,
        request: RagQueryRequest,
        query_normalizada: QueryNormalizadaOutput
    ) -> RagQueryResponse:
        """Resposta quando useRag=False (TODO: implementar)."""
        return RagQueryResponse(
            queryOriginal=request.promptUsuario,
            queryNormalizada=query_normalizada,
            contexto_seeu="Modo sem RAG - resposta direta (não implementado)",
            teses=[],
            aplicacao_caso="",
            jurisprudencias=[],
            avisos_limitacoes="Funcionalidade em desenvolvimento",
            backend="none",
            totalChunksRecuperados=0,
            totalDocumentosUnicos=0
        )
    
    def _resposta_vazia(
        self,
        request: RagQueryRequest,
        query_normalizada: QueryNormalizadaOutput
    ) -> RagQueryResponse:
        """Resposta quando nenhum chunk é recuperado."""
        return RagQueryResponse(
            queryOriginal=request.promptUsuario,
            queryNormalizada=query_normalizada,
            contexto_seeu="Nenhum documento relevante encontrado na base de dados.",
            teses=[],
            aplicacao_caso="",
            jurisprudencias=[],
            avisos_limitacoes="Não foram encontrados documentos jurisprudenciais relevantes para esta consulta. Considere reformular a pergunta ou verificar se a base de dados contém informações sobre o tema.",
            backend=self.store.__class__.__name__,
            totalChunksRecuperados=0,
            totalDocumentosUnicos=0
        )

    def query_markdown(
        self,
        request: RagQueryRequest
    ) -> str:
        """
        Processa consulta RAG e retorna resposta em Markdown puro (formato UX jurídica).
        
        Este método é otimizado para exibição direta na interface do usuário,
        seguindo as diretrizes de UX jurídica do SEEU.
        
        Fluxo:
        1. Normalização jurídica
        2. Busca vetorial
        3. Cálculo de relevância relativa
        4. Construção do prompt Markdown
        5. Chamada ao LLM
        6. Retorno direto do Markdown gerado
        
        Args:
            request: Request com prompt do usuário e metadados
            
        Returns:
            String em Markdown formatado para operadores do direito
        """
        log.info(f"Processando consulta RAG (Markdown): {request.promptUsuario[:100]}...")
        
        # ETAPA 1: Normalização Jurídica
        normalizer = get_normalizer()
        contexto_meta = self._formatar_contexto_metadados(request.metadados)
        query_normalizada = normalizer.normalizar(
            prompt_usuario=request.promptUsuario,
            contexto_adicional=contexto_meta
        )
        
        log.info(f"Query normalizada: {query_normalizada.queryRAG}")
        
        # ETAPA 2: Busca Vetorial
        if not request.useRag:
            # Modo sem RAG - retorna resposta direta
            return self._resposta_markdown_sem_rag(request, query_normalizada)
        
        chunks_recuperados = self._buscar_chunks(
            query_normalizada.queryRAG,
            k=request.k,
            metadados=request.metadados
        )
        
        if not chunks_recuperados:
            log.warning("Nenhum chunk recuperado")
            return self._resposta_markdown_vazia(request, query_normalizada)
        
        # ETAPA 3: Calcular Relevância Relativa
        scores = [c.score for c in chunks_recuperados]
        relevancia_relativa = calcular_relevancia_relativa(scores)
        
        for i, chunk in enumerate(chunks_recuperados):
            chunk.relevanciaRelativa = round(relevancia_relativa[i], 1)
        
        # ETAPA 4: Agrupar por Documento
        chunks_agrupados = agrupar_chunks_por_documento(chunks_recuperados)
        
        log.info(
            f"Recuperados {len(chunks_recuperados)} chunks de "
            f"{len(chunks_agrupados)} documentos únicos"
        )
        
        # ETAPA 5: Gerar cabeçalho informativo
        num_docs = len(chunks_agrupados)
        cabecalho = f"📚 Consultados {num_docs} documentos jurídicos (RAG/FAISS)\n\n"
        
        # ETAPA 6: Montar Prompt Markdown e Chamar LLM
        resposta_markdown = self._gerar_resposta_markdown_llm(
            request.promptUsuario,
            query_normalizada,
            chunks_agrupados
        )
        
        log.info("Consulta RAG (Markdown) processada com sucesso")
        return cabecalho + resposta_markdown
    
    def _gerar_resposta_markdown_llm(
        self,
        query_original: str,
        query_normalizada: QueryNormalizadaOutput,
        chunks_agrupados: Dict[str, List[ChunkWithScore]]
    ) -> str:
        """Gera resposta em Markdown usando LLM com template UX jurídica."""
        
        # Formata dados de execução penal
        dados_exec = query_normalizada.dadosExecucaoPenal
        dados_exec_str = json.dumps(dados_exec.dict(), ensure_ascii=False, indent=2)
        
        # Formata temas e palavras-chave
        temas_str = ", ".join(query_normalizada.temaExecucao) if query_normalizada.temaExecucao else "Nenhum tema específico identificado"
        palavras_str = ", ".join(query_normalizada.palavrasChaveJuridicas) if query_normalizada.palavrasChaveJuridicas else "Nenhuma palavra-chave específica"
        
        # Monta contexto dos documentos
        contexto_docs = montar_contexto_documentos(chunks_agrupados)
        
        # Monta prompt final com template Markdown
        prompt = TEMPLATE_RAG_SEEU_MARKDOWN.format(
            query_original=query_original,
            query_normalizada=query_normalizada.queryRAG,
            dados_execucao=dados_exec_str,
            temas_execucao=temas_str,
            palavras_chave=palavras_str,
            documentos_contexto=contexto_docs
        )
        
        log.debug(f"Prompt Markdown montado ({len(prompt)} chars)")
        
        # Chama LLM e retorna Markdown direto
        resposta_markdown = self._chamar_llm(prompt)
        
        # Remove possíveis markdown fences se o LLM insistir em adicionar
        resposta_limpa = resposta_markdown.strip()
        if resposta_limpa.startswith("```markdown"):
            resposta_limpa = resposta_limpa[11:]
        if resposta_limpa.startswith("```"):
            resposta_limpa = resposta_limpa[3:]
        if resposta_limpa.endswith("```"):
            resposta_limpa = resposta_limpa[:-3]
        
        return resposta_limpa.strip()
    
    def _resposta_markdown_sem_rag(
        self,
        request: RagQueryRequest,
        query_normalizada: QueryNormalizadaOutput
    ) -> str:
        """Resposta em Markdown quando useRag=False."""
        return """## Modo Chat Simples Ativado

Esta consulta foi realizada **sem utilizar a base de conhecimento jurídica** (RAG desativado).

Para respostas fundamentadas em jurisprudência, ative o modo **Base de Conhecimento** na interface.

## Avisos e limitações

- Resposta gerada diretamente pelo modelo de linguagem sem consulta à base jurídica.
- Não utiliza documentos indexados do STJ, STF ou outros tribunais.
- Para análises fundamentadas, recomenda-se ativar o modo RAG.
"""
    
    def _resposta_markdown_vazia(
        self,
        request: RagQueryRequest,
        query_normalizada: QueryNormalizadaOutput
    ) -> str:
        """Resposta em Markdown quando nenhum chunk é recuperado."""
        return f"""## Resumo objetivo

- Nenhum documento relevante foi encontrado na base de conhecimento para a consulta: "{request.promptUsuario[:100]}..."
- A base de dados pode não conter jurisprudência específica sobre este tema.
- Considere reformular a pergunta com termos jurídicos mais específicos.

## O que os documentos analisados tratam

Nenhum documento foi recuperado da base de dados.

## Conclusão

- Não foi possível localizar jurisprudência relevante na base indexada.
- Isso pode indicar:
  - Tema muito específico ou recente sem precedentes indexados.
  - Necessidade de reformulação da consulta com termos mais técnicos.
  - Limitação do corpus de documentos disponível.

## Jurisprudências utilizadas

Nenhuma jurisprudência foi utilizada (nenhum documento encontrado).

## Próximos passos sugeridos

- Reformular a consulta utilizando terminologia jurídica mais específica
- Consultar diretamente os sites dos tribunais (STJ, STF, TJs)
- Verificar a LEP (Lei de Execução Penal) para embasamento legal
- Considerar busca manual por precedentes similares
- Entrar em contato com o suporte técnico se acreditar que o documento deveria estar disponível

## Avisos e limitações

- Esta resposta indica ausência de documentos na base de dados para os termos consultados.
- Não substitui análise técnico-jurídica completa do processo.
- A base de conhecimento é limitada aos documentos indexados até o momento.
"""

