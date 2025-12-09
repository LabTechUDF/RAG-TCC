import { logger } from '../../utils/logger'

interface RagQueryRequest {
  promptUsuario: string
  useRag?: boolean
  metadados?: {
    tribunal?: string
    anoMin?: number
    anoMax?: number
    tipoConsulta?: string
  }
  k?: number
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  
  try {
    const body = await readBody<RagQueryRequest>(event)
    
    logger.info('Received RAG query request', 'DBVECTOR RAG API', {
      promptLength: body.promptUsuario?.length,
      useRag: body.useRag ?? true,
      k: body.k || 10
    })
    
    if (!body.promptUsuario || !body.promptUsuario.trim()) {
      logger.warn('Request without promptUsuario', 'DBVECTOR RAG API')
      throw createError({
        statusCode: 400,
        message: 'promptUsuario is required'
      })
    }

    const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
    const ragQueryUrl = `${dbvectorUrl}/api/rag/query-markdown`
    
    logger.debug('Sending RAG request to DBVECTOR', 'DBVECTOR RAG API', {
      url: ragQueryUrl,
      promptLength: body.promptUsuario.length,
      k: body.k || 10
    })

    // Faz a requisição para o DBVECTOR endpoint RAG Markdown
    const response = await $fetch<string>(ragQueryUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/markdown'
      },
      body: {
        promptUsuario: body.promptUsuario,
        useRag: body.useRag ?? true,
        metadados: body.metadados || {},
        k: body.k || 10
      }
    })

    logger.info('DBVECTOR RAG query successful', 'DBVECTOR RAG API', {
      responseLength: response.length,
      responsePreview: response.substring(0, 100)
    })

    // Retorna o Markdown diretamente
    return response
  } catch (error: any) {
    logger.error('DBVECTOR RAG API Error', 'DBVECTOR RAG API', {
      statusCode: error.statusCode,
      message: error.data?.detail || error.message
    }, error)
    
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.data?.detail || 'Erro ao processar requisição RAG com DBVECTOR'
    })
  }
})
