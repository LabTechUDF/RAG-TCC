import { logger } from '../../utils/logger'

interface DBVectorSearchRequest {
  q: string
  k?: number
}

interface DBVectorSearchResult {
  id: string
  title?: string
  text: string
  court?: string
  code?: string
  article?: string
  date?: string
  meta?: any
  score: number
}

interface DBVectorSearchResponse {
  query: string
  total: number
  backend: string
  results: DBVectorSearchResult[]
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  
  try {
    const body = await readBody<DBVectorSearchRequest>(event)
    
    logger.info('Received DBVECTOR search request', 'DBVECTOR API', {
      query: body.q,
      k: body.k || 5
    })
    
    if (!body.q || !body.q.trim()) {
      logger.warn('Request without query', 'DBVECTOR API')
      throw createError({
        statusCode: 400,
        message: 'Query (q) is required'
      })
    }

    const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
    const searchUrl = `${dbvectorUrl}/search`
    
    logger.debug('Sending request to DBVECTOR', 'DBVECTOR API', {
      url: searchUrl,
      query: body.q,
      k: body.k || 5
    })

    // Faz a requisição para o DBVECTOR
    const response = await $fetch<DBVectorSearchResponse>(searchUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: {
        q: body.q,
        k: body.k || 5
      }
    })

    logger.info('DBVECTOR search successful', 'DBVECTOR API', {
      query: response.query,
      total: response.total,
      backend: response.backend,
      resultsCount: response.results.length
    })

    return response
  } catch (error: any) {
    logger.error('DBVECTOR API Error', 'DBVECTOR API', {
      statusCode: error.statusCode,
      message: error.data?.detail || error.message
    }, error)
    
    throw createError({
      statusCode: error.statusCode || 500,
      message: error.data?.detail || 'Erro ao processar requisição com DBVECTOR'
    })
  }
})
