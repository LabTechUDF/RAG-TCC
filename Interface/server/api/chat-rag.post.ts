/**
 * API Route para chat com RAG integrado com telemetria
 * 
 * Fluxo completo conforme TCC:
 * 1. Recebe query do usuário com metadados (user_id, session_id)
 * 2. Chama DBVECTOR para buscar documentos relevantes (RAG)
 * 3. Monta contexto com documentos recuperados
 * 4. Envia para LLM (OpenAI) com contexto aumentado
 * 5. Retorna resposta + citações + metadados de telemetria
 */
export default defineEventHandler(async (event) => {
  const startTime = Date.now()
  const body = await readBody(event)
  const { query, k = 5, user_id, session_id, court_filter, article_filter, conversation_history = [] } = body

  if (!query || !query.trim()) {
    throw createError({
      statusCode: 422,
      message: 'Query é obrigatória'
    })
  }

  const config = useRuntimeConfig()
  const ragApiUrl = config.public.ragApiUrl || 'http://localhost:8000'
  const openaiApiKey = config.public.openaiApiKey

  if (!openaiApiKey || openaiApiKey === 'your_openai_api_key_here') {
    throw createError({
      statusCode: 500,
      message: 'API Key da OpenAI não configurada'
    })
  }

  let retrievalLatency = 0
  let llmLatency = 0

  try {
    // 1. Busca contexto relevante no RAG com filtros e telemetria
    const retrievalStart = Date.now()
    const ragResponse = await $fetch<any>(`${ragApiUrl}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: {
        q: query,
        k: k,
        user_id: user_id,
        session_id: session_id,
        court_filter: court_filter,
        article_filter: article_filter,
        conversation_history: conversation_history
      }
    })
    retrievalLatency = Date.now() - retrievalStart

    // 2. Extrai textos dos documentos recuperados
    const contexts = ragResponse.results?.map((result: any) => {
      const metadata = [
        result.court && `Tribunal: ${result.court}`,
        result.code && `Código: ${result.code}`,
        result.article && `Artigo: ${result.article}`,
        result.date && `Data: ${result.date}`,
        result.title && `Título: ${result.title}`
      ].filter(Boolean).join(' | ')
      
      return `[${metadata}]\n${result.text}`
    }) || []

    if (contexts.length === 0) {
      return {
        answer: 'Não foram encontrados documentos relevantes para sua pergunta.',
        contexts: [],
        sources: []
      }
    }

    // 3. Monta prompt com contexto
    const contextText = contexts.join('\n\n---\n\n')
    const systemPrompt = `Você é um assistente jurídico especializado. Use APENAS as informações dos documentos fornecidos abaixo para responder a pergunta do usuário. Se a informação não estiver nos documentos, diga que não encontrou informações suficientes.

DOCUMENTOS RELEVANTES:
${contextText}

Responda de forma clara, objetiva e cite os documentos quando relevante.`

    // 4. Chama OpenAI com contexto
    const llmStart = Date.now()
    const openaiResponse = await $fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${openaiApiKey}`,
        'Content-Type': 'application/json'
      },
      body: {
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: query }
        ],
        temperature: 0.3,
        max_tokens: 1000
      }
    })
    llmLatency = Date.now() - llmStart

    const answer = (openaiResponse as any).choices?.[0]?.message?.content || 'Não foi possível gerar uma resposta.'
    const totalLatency = Date.now() - startTime

    // 5. Log de telemetria do chat completo
    console.log('[RAG Chat Telemetry]', {
      timestamp: new Date().toISOString(),
      user_id,
      session_id,
      query,
      mode: 'rag',
      total_latency_ms: totalLatency,
      retrieval_latency_ms: retrievalLatency,
      llm_latency_ms: llmLatency,
      documents_retrieved: ragResponse.results?.length || 0,
      backend: ragResponse.backend,
      filters_applied: ragResponse.filters_applied || {}
    })

    // 6. Retorna resposta + contextos completos + metadados
    return {
      answer,
      contexts: ragResponse.results || [],
      sources: ragResponse.results?.map((r: any) => ({
        id: r.id,
        title: r.title || 'Sem título',
        court: r.court,
        score: r.score
      })) || [],
      backend: ragResponse.backend,
      totalDocs: ragResponse.total,
      // Metadados de telemetria
      telemetry: {
        total_latency_ms: totalLatency,
        retrieval_latency_ms: retrievalLatency,
        llm_latency_ms: llmLatency,
        canonical_query: ragResponse.canonical_query,
        filters_applied: ragResponse.filters_applied || {}
      }
    }

  } catch (error: any) {
    console.error('Erro no chat RAG:', error)
    
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.data?.message || error.message || 'Erro ao processar chat com RAG'
    })
  }
})
