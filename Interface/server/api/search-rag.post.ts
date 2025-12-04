/**
 * API Route para buscar documentos no sistema RAG (DBVECTOR)
 */
export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const { query, k = 5 } = body

  if (!query || !query.trim()) {
    throw createError({
      statusCode: 422,
      message: 'Query é obrigatória'
    })
  }

  const config = useRuntimeConfig()
  const ragApiUrl = config.public.ragApiUrl || 'http://localhost:8000'

  try {
    // Chama o backend DBVECTOR
    const response = await $fetch(`${ragApiUrl}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: {
        q: query,
        k: k
      }
    })

    return response
  } catch (error: any) {
    console.error('Erro ao buscar no RAG:', error)
    
    throw createError({
      statusCode: error.statusCode || 503,
      message: error.message || 'Erro ao conectar com o backend RAG. Verifique se o DBVECTOR está rodando.'
    })
  }
})
