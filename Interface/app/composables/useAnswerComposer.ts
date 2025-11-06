/**
 * GPT-5 Answer Composer Composable
 * 
 * Responsável por montar a resposta final do RAG com base em:
 * - user_prompt: pergunta do usuário
 * - recent_history: histórico recente de conversação
 * - retrieved: documentos recuperados do banco vetorial
 */

interface RetrievedDocument {
  doc_id: string
  title?: string
  score: number
  snippet: string
  source_url?: string | null
  date?: string | null
  article?: string
  court?: string
}

interface AnswerComposerInput {
  user_prompt: string
  recent_history?: string
  retrieved: RetrievedDocument[]
}

interface AnswerComposerOutput {
  answer: string
  citations_used: string[]
  coverage_level: 'high' | 'medium' | 'low' | 'none'
  suggestions?: string[]
}

export function useAnswerComposer() {
  const config = useRuntimeConfig()

  /**
   * Constrói o prompt do sistema para o Answer Composer
   */
  function buildSystemPrompt(): string {
    return `Você é o **GPT-5 Answer Composer** de um pipeline RAG jurídico/técnico. Seu trabalho é responder ao user_prompt usando **exclusivamente** o material em retrieved como base factual.

INSTRUÇÕES DE RESPOSTA:
1) **Use apenas o que está em retrieved para afirmações factuais.** Se algo essencial não estiver coberto, diga explicitamente o que falta e avance com a melhor resposta possível **sem inventar**.
2) **Cite as fontes** colocando o doc_id entre colchetes **no fim da frase** a que se refere. Ex.: "... segundo entendimento consolidado [STJ_2021_AgInt_12345]." Use tantas citações quantas forem necessárias.
3) Se houver **conflito** entre passagens, prefira as de maior score e as mais **recentes** (se date for fornecida); explique o conflito em uma frase.
4) **Clareza e concisão**: organize em parágrafos curtos e/ou listas. Evite jargão desnecessário. Não exponha raciocínio interno passo a passo.
5) **Idioma**: responda no mesmo idioma do user_prompt.
6) Não copie trechos longos. Parafraseie e sintetize.

COMPORTAMENTO EM COBERTURA BAIXA:
- Se retrieved vier vazio ou irrelevante, devolva:
  - Um pequeno **resumo do que você precisa** para responder melhor (ex.: norma, período, jurisdição), e
  - **3 sugestões objetivas** de refinamento que a aplicação pode usar para nova busca (sem fazer perguntas ao usuário nesta etapa).

SAÍDA:
- Texto final para o usuário, com citações entre colchetes ao final das frases pertinentes. Nada de JSON, nada de metadados extras.`
  }

  /**
   * Constrói a mensagem do usuário com o contexto
   */
  function buildUserMessage(input: AnswerComposerInput): string {
    const { user_prompt, recent_history = '', retrieved } = input

    // Formata os documentos recuperados
    const retrievedJson = JSON.stringify(retrieved, null, 2)

    return `ENTRADAS:
- user_prompt:
  ${user_prompt}
  
- recent_history (texto plano):
  ${recent_history || '(vazio)'}
  
- retrieved (JSON de passagens):
${retrievedJson}

Responda à pergunta do usuário usando exclusivamente o contexto acima.`
  }

  /**
   * Extrai citações da resposta
   */
  function extractCitations(answer: string): string[] {
    const citationRegex = /\[([^\]]+)\]/g
    const citations: string[] = []
    let match

    while ((match = citationRegex.exec(answer)) !== null) {
      citations.push(match[1])
    }

    return [...new Set(citations)] // Remove duplicatas
  }

  /**
   * Avalia o nível de cobertura com base no número de documentos e scores
   */
  function assessCoverage(retrieved: RetrievedDocument[]): 'high' | 'medium' | 'low' | 'none' {
    if (retrieved.length === 0) return 'none'
    
    const avgScore = retrieved.reduce((sum, doc) => sum + doc.score, 0) / retrieved.length
    
    if (retrieved.length >= 3 && avgScore >= 0.7) return 'high'
    if (retrieved.length >= 2 && avgScore >= 0.5) return 'medium'
    if (retrieved.length >= 1) return 'low'
    
    return 'none'
  }

  /**
   * Extrai sugestões da resposta quando cobertura é baixa
   */
  function extractSuggestions(answer: string): string[] {
    // Procura por padrões de sugestões na resposta
    const suggestionPatterns = [
      /(?:sugestões?|refinamentos?|recomendações?):\s*\n([^\n]+(?:\n[^\n]+)*)/i,
      /(?:para melhorar|tente):\s*\n([^\n]+(?:\n[^\n]+)*)/i
    ]

    for (const pattern of suggestionPatterns) {
      const match = answer.match(pattern)
      if (match) {
        // Extrai linhas numeradas ou com bullets
        const lines = match[1]
          .split('\n')
          .map(line => line.trim())
          .filter(line => line.match(/^[\d\-\*•]/))
          .map(line => line.replace(/^[\d\-\*•\.)\s]+/, '').trim())
          .filter(line => line.length > 0)
        
        if (lines.length > 0) return lines.slice(0, 3)
      }
    }

    return []
  }

  /**
   * Compõe a resposta final usando GPT
   */
  async function composeAnswer(input: AnswerComposerInput): Promise<AnswerComposerOutput> {
    const { user_prompt, retrieved } = input

    // Validação básica
    if (!user_prompt || user_prompt.trim().length < 2) {
      throw new Error('user_prompt deve ter pelo menos 2 caracteres')
    }

    try {
      const systemPrompt = buildSystemPrompt()
      const userMessage = buildUserMessage(input)

      interface OpenAIMessage {
        role: 'system' | 'user' | 'assistant'
        content: string
      }

      interface OpenAIResponse {
        id: string
        object: string
        created: number
        model: string
        choices: Array<{
          index: number
          message: OpenAIMessage
          finish_reason: string
        }>
        usage?: {
          prompt_tokens: number
          completion_tokens: number
          total_tokens: number
        }
      }

      const result = await $fetch<OpenAIResponse>('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${config.public.openaiApiKey}`,
          'Content-Type': 'application/json',
          'OpenAI-Project': config.public.openaiProjectId as string
        },
        body: {
          model: 'gpt-4o-mini', // Modelo eficiente para composição
          messages: [
            {
              role: 'system',
              content: systemPrompt
            },
            {
              role: 'user',
              content: userMessage
            }
          ],
          temperature: 0.3, // Mais factual e menos criativo
          max_tokens: 1000 // Respostas completas mas não excessivas
        }
      })

      const answer = result?.choices?.[0]?.message?.content?.trim() || 
        'Não foi possível gerar uma resposta. Por favor, tente novamente.'

      // Extrai metadados da resposta
      const citations_used = extractCitations(answer)
      const coverage_level = assessCoverage(retrieved)
      const suggestions = coverage_level === 'low' || coverage_level === 'none' 
        ? extractSuggestions(answer)
        : undefined

      console.log('Answer Composer:', {
        prompt_length: user_prompt.length,
        retrieved_count: retrieved.length,
        answer_length: answer.length,
        citations_used: citations_used.length,
        coverage_level,
        has_suggestions: !!suggestions
      })

      return {
        answer,
        citations_used,
        coverage_level,
        suggestions
      }

    } catch (error: any) {
      console.error('Erro ao compor resposta:', error)
      
      // Fallback: resposta básica
      return {
        answer: `Desculpe, ocorreu um erro ao processar sua solicitação: ${error.message || 'Erro desconhecido'}`,
        citations_used: [],
        coverage_level: 'none',
        suggestions: [
          'Tente reformular sua pergunta',
          'Seja mais específico sobre o tema',
          'Inclua palavras-chave jurídicas relevantes'
        ]
      }
    }
  }

  /**
   * Formata documento para snippet
   */
  function formatDocumentSnippet(doc: any, maxLength: number = 300): string {
    const text = doc.text || doc.snippet || ''
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength) + '...'
  }

  /**
   * Converte documentos do VectorSearch para formato RetrievedDocument
   */
  function convertToRetrievedDocuments(docs: any[]): RetrievedDocument[] {
    return docs.map((doc, idx) => ({
      doc_id: doc.id || `doc_${idx}`,
      title: doc.title || doc.article || 'Documento sem título',
      score: doc.score || 0,
      snippet: formatDocumentSnippet(doc),
      source_url: doc.source_url || null,
      date: doc.date || null,
      article: doc.article,
      court: doc.court
    }))
  }

  return {
    composeAnswer,
    convertToRetrievedDocuments,
    buildSystemPrompt,
    buildUserMessage,
    extractCitations,
    assessCoverage
  }
}
