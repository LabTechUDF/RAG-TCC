import { logger } from '../../utils/logger'

interface DBVectorHealthResponse {
  status: string
  backend: string
  documents: number
  embedding_dim: number
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  
  try {
    const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
    const healthUrl = `${dbvectorUrl}/health`
    
    logger.debug('Checking DBVECTOR health', 'DBVECTOR API', { url: healthUrl })

    const response = await $fetch<DBVectorHealthResponse>(healthUrl, {
      method: 'GET'
    })

    logger.info('DBVECTOR health check successful', 'DBVECTOR API', {
      status: response.status,
      backend: response.backend,
      documents: response.documents
    })

    return response
  } catch (error: any) {
    logger.error('DBVECTOR Health Check Error', 'DBVECTOR API', {
      statusCode: error.statusCode,
      message: error.data?.detail || error.message
    }, error)
    
    throw createError({
      statusCode: error.statusCode || 503,
      message: 'DBVECTOR API não está disponível'
    })
  }
})
