import { logger } from '../../utils/logger'

interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()

  try {
    const body = await readBody(event)
    const history: HistoryMessage[] = body.history || []

    logger.info('Received OpenAI chat request', 'OpenAI API', {
      model: body.model,
      promptLength: body.prompt?.length,
      historyLength: history.length
    })

    if (!body.prompt) {
      logger.warn('Request without prompt', 'OpenAI API')
      throw createError({
        statusCode: 400,
        message: 'Prompt is required'
      })
    }

    const modelName = body.model || 'gpt-5'
    const isReasoningModel = modelName.includes('o1') || modelName.includes('gpt-5')

    logger.debug('Sending request to OpenAI', 'OpenAI API', {
      model: modelName,
      isReasoningModel,
      temperature: isReasoningModel ? undefined : 1,
      max_completion_tokens: 10000
    })

    // System prompt para modo Chat Simples - assistente de jurisprudência brasileira
    const systemPrompt = `Você é um assistente jurídico especializado em direito brasileiro.
Seu papel é auxiliar com questões relacionadas à legislação brasileira amplamente conhecida, incluindo:
- Constituição Federal
- Código Civil
- Código Penal
- Código de Processo Civil
- Código de Processo Penal
- Código de Defesa do Consumidor
- Consolidação das Leis do Trabalho (CLT)
- Código Tributário Nacional
- E outras leis federais de conhecimento público

Responda de forma clara, objetiva e didática. Quando apropriado, cite artigos e dispositivos legais relevantes.
Lembre-se: você está fornecendo informações educativas, não aconselhamento jurídico profissional.
Sempre recomende que o usuário consulte um advogado para casos específicos.`

    // Build messages array with history
    let messages: Array<{ role: string, content: string }> = []

    // Modelos de reasoning (o1, gpt-5) não suportam role 'system'
    if (isReasoningModel) {
      // For reasoning models, include system prompt in first user message
      if (history.length > 0) {
        // Include history with system context in first message
        const firstUserContent = `${systemPrompt}\n\n---\n\nHistórico da conversa:\n${history.map(h => `${h.role === 'user' ? 'Usuário' : 'Assistente'}: ${h.content}`).join('\n\n')}\n\n---\n\nPergunta atual do usuário: ${body.prompt}`
        messages = [{ role: 'user', content: firstUserContent }]
      } else {
        messages = [{ role: 'user', content: `${systemPrompt}\n\n---\n\nPergunta do usuário: ${body.prompt}` }]
      }
    } else {
      // For regular models, use system message + history + current prompt
      messages = [{ role: 'system', content: systemPrompt }]

      // Add conversation history
      for (const msg of history) {
        messages.push({ role: msg.role, content: msg.content })
      }

      // Add current user message
      messages.push({ role: 'user', content: body.prompt })
    }

    // Configuração base para a API de chat completions
    const requestBody: any = {
      model: modelName,
      messages,
      max_completion_tokens: 10000
    }

    // Modelos de reasoning (o1, gpt-5) não suportam temperature
    // e usam tokens de reasoning que não aparecem na resposta
    if (!isReasoningModel) {
      requestBody.temperature = 1
    }

    // Usando a API de chat completions da OpenAI
    const response = await $fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.openaiApiKey}`,
        'Content-Type': 'application/json',
        ...(config.openaiProjectId ? { 'OpenAI-Project': config.openaiProjectId } : {})
      },
      body: requestBody
    })

    // Extrair o conteúdo da resposta para logar
    const responseContent = (response as any)?.choices?.[0]?.message?.content || ''
    const finishReason = (response as any)?.choices?.[0]?.finish_reason || ''
    const usage = (response as any)?.usage || {}

    // Log detalhado para debugging
    if (responseContent.length === 0) {
      logger.warn('OpenAI returned empty content', 'OpenAI API', {
        responseId: (response as any)?.id,
        model: (response as any)?.model,
        finishReason,
        usage: {
          completion_tokens: usage.completion_tokens,
          reasoning_tokens: usage.completion_tokens_details?.reasoning_tokens,
          total_tokens: usage.total_tokens
        },
        fullResponse: JSON.stringify(response).substring(0, 500)
      })
    }

    logger.info('OpenAI request successful', 'OpenAI API', {
      responseId: (response as any)?.id,
      model: (response as any)?.model,
      finishReason: finishReason,
      contentLength: responseContent.length,
      reasoningTokens: usage.completion_tokens_details?.reasoning_tokens || 0,
      content: responseContent.substring(0, 200) + (responseContent.length > 200 ? '...' : '')
    })

    return response
  } catch (error: any) {
    logger.error('OpenAI API Error', 'OpenAI API', {
      statusCode: error.statusCode,
      message: error.data?.error?.message || error.message
    }, error)
    
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.data?.error?.message || 'Erro ao processar requisição com OpenAI'
    })
  }
})
