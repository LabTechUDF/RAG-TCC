import { logger } from '../../utils/logger'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  
  try {
    const body = await readBody(event)
    logger.info('Received OpenAI chat request', 'OpenAI API', { 
      model: body.model,
      promptLength: body.prompt?.length 
    })
    
    if (!body.prompt) {
      logger.warn('Request without prompt', 'OpenAI API')
      throw createError({
        statusCode: 400,
        message: 'Prompt is required'
      })
    }

    const modelName = body.model || 'gpt-5-mini'
    const isReasoningModel = modelName.includes('o1') || modelName.includes('gpt-5')
    
    logger.debug('Sending request to OpenAI', 'OpenAI API', {
      model: modelName,
      isReasoningModel,
      temperature: isReasoningModel ? undefined : 1,
      max_completion_tokens: 10000
    })

    // Configuração base para a API de chat completions
    const requestBody: any = {
      model: modelName,
      messages: [
        {
          role: 'user',
          content: body.prompt
        }
      ],
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
