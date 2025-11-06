/**
 * Vector Search Composable
 * 
 * Integração com o backend DBVECTOR (FastAPI) para busca vetorial em documentos jurídicos.
 */

interface SearchDocument {
  id: string
  title?: string
  text: string
  court?: string
  code?: string
  article?: string
  date?: string
  case_number?: string  // Número do processo/caso
  relator?: string      // Relator do caso
  source?: string       // Fonte do documento (STF, STJ, etc)
  meta?: Record<string, any>
  score: number
}

interface SearchResponse {
  query: string
  total: number
  backend: string
  results: SearchDocument[]
}

interface SearchOptions {
  k?: number // Número de resultados (padrão: 5)
  optimize?: boolean // Se deve otimizar a query (padrão: true)
  recent_history?: string
  cluster_names?: string[]
}

export function useVectorSearch() {
  const config = useRuntimeConfig()
  const { optimizeQuery, buildSimpleQuery } = useQueryBuilder()

  /**
   * Obtém clusters/artigos disponíveis no banco vetorial
   * (Por enquanto retorna lista hardcoded, pode ser feito dinâmico via API)
   */
  function getAvailableClusters(): string[] {
    return [
      'art. 179',
      'art. 205',
      'art. 244',
      'art. 312',
      'art. 319-A',
      'art. 323',
      'art. 325',
      'art. 330',
      'art. 345',
      'art. 346'
    ]
  }

  /**
   * Busca documentos no banco vetorial
   */
  async function search(
    query: string,
    options: SearchOptions = {}
  ): Promise<SearchResponse> {
    const {
      k = 5,
      optimize = true,
      recent_history = '',
      cluster_names = getAvailableClusters()
    } = options

    if (!query || query.trim().length < 2) {
      throw new Error('Query deve ter pelo menos 2 caracteres')
    }

    let finalQuery = query

    // Otimiza a query se solicitado
    if (optimize) {
      try {
        const optimized = await optimizeQuery({
          user_query: query,
          recent_history,
          cluster_names
        })
        finalQuery = optimized.optimized_query
        console.log('Query otimizada:', {
          original: query,
          optimized: finalQuery,
          tokens: optimized.tokens_count,
          clusters: optimized.used_clusters
        })
      } catch (error) {
        console.warn('Falha ao otimizar query, usando original:', error)
        finalQuery = query
      }
    }

    // Busca no DBVECTOR
    try {
      const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
      
      const response = await $fetch<SearchResponse>(`${dbvectorUrl}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: {
          q: finalQuery,
          k
        }
      })

      return response

    } catch (error: any) {
      console.error('Erro ao buscar no DBVECTOR:', error)
      
      // Mensagens de erro mais amigáveis
      if (error.statusCode === 503) {
        throw new Error('Banco vetorial não está disponível. Verifique se o DBVECTOR está rodando.')
      } else if (error.statusCode === 404) {
        throw new Error('Nenhum documento indexado. Execute o pipeline de build.')
      } else {
        throw new Error(`Erro ao buscar documentos: ${error.message || 'Erro desconhecido'}`)
      }
    }
  }

  /**
   * Verifica saúde do backend DBVECTOR
   */
  async function healthCheck(): Promise<{
    status: string
    backend: string
    documents: number
    embedding_dim: number
  }> {
    try {
      const dbvectorUrl = config.public.dbvectorApiUrl || 'http://localhost:8000'
      
      const response = await $fetch<any>(`${dbvectorUrl}/health`)
      return response

    } catch (error) {
      console.error('Erro ao verificar saúde do DBVECTOR:', error)
      throw new Error('DBVECTOR não está respondendo')
    }
  }

  return {
    search,
    healthCheck,
    getAvailableClusters
  }
}
