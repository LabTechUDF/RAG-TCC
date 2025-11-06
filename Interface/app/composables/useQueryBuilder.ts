/**
 * GPT-5 Query Builder Composable
 * 
 * Otimiza consultas do usuário para busca vetorial/híbrida no DBVECTOR.
 * Gera UMA ÚNICA STRING DE BUSCA otimizada baseada em:
 * - user_query: texto livre do usuário
 * - recent_history: histórico recente de conversação (opcional)
 * - cluster_names: clusters/artigos disponíveis no banco vetorial
 */

interface QueryBuilderInput {
  user_query: string
  recent_history?: string
  cluster_names?: string[]
}

interface QueryBuilderOutput {
  optimized_query: string
  tokens_count: number
  used_clusters: string[]
}

export function useQueryBuilder() {
  const config = useRuntimeConfig()

  /**
   * Constrói a string de prompt para o GPT-5 Query Builder
   */
  function buildPrompt(input: QueryBuilderInput): string {
    const { user_query, recent_history = '', cluster_names = [] } = input

    return `Você é o **GPT-5 Query Builder**, executado via camada /interface do nosso código.
Gere **UMA ÚNICA STRING DE BUSCA** (apenas uma linha) otimizada para consulta **vetorial/híbrida**.
A aplicação já injeta os dados necessários; **responda somente com a string final**, sem rótulos, sem aspas, sem markdown.

ENTRADAS (injetadas pela aplicação):
- user_query: ${user_query}
- recent_history: ${recent_history || '(vazio)'}
- cluster_names: ${JSON.stringify(cluster_names)}

REGRAS (obrigatórias):
1) Saída: **exatamente uma linha** com a string de busca. Nada mais.
2) Idioma da saída = idioma de user_query.
3) Priorize **termos de alto sinal**: entidades, artigos (ex.: art. 330), leis (ex.: Lei 8.666/93), súmulas, datas, siglas/instituições.
4) Use até **3 cluster_names** mais alinhados à intenção do usuário; se irrelevantes ou ausentes, ignore e baseie-se em user_query + recent_history.
5) Tamanho sugerido: **6–20 palavras**. Remova stopwords; evite artigos/preposições desnecessárias.
6) **Não invente** identificadores (leis, números de artigos/processos). Use literalmente quando fornecidos.
7) Não use operadores avançados a menos que explicitamente suportados. Operadores simples (AND/OR) só se o cliente indicar suporte.
8) Se user_query for ambígua, **não faça perguntas**; gere a melhor string possível.
9) Use **aspas** apenas quando absolutamente necessário (ex.: título oficial que deva permanecer como expressão exata).

VALIDAÇÕES (implícitas):
- Se a string final ficar vazia ou com **< 2 tokens relevantes**, extraia termos-chave de recent_history; se ainda insuficiente, gere uma string curta com as palavras-chave de user_query.

OBSERVAÇÃO:
- A saída desta etapa alimenta diretamente a requisição ao **banco vetorial/híbrido**; qualquer texto adicional fora da string invalidará a operação.

SAÍDA EXATA:
- Uma única linha contendo a string de busca final.`
  }

  /**
   * Otimiza a query do usuário usando GPT-5
   */
  async function optimizeQuery(input: QueryBuilderInput): Promise<QueryBuilderOutput> {
    const { user_query, cluster_names = [] } = input

    // Validação básica
    if (!user_query || user_query.trim().length < 2) {
      throw new Error('Query deve ter pelo menos 2 caracteres')
    }

    try {
      const prompt = buildPrompt(input)

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
          model: 'gpt-4o-mini', // Modelo rápido e eficiente para query building
          messages: [
            {
              role: 'user',
              content: prompt
            }
          ],
          temperature: 0.3, // Mais determinístico para queries
          max_tokens: 100 // Queries devem ser curtas
        }
      })

      const optimized_query = result?.choices?.[0]?.message?.content?.trim() || user_query
      
      // Remove aspas extras se houver
      const cleanQuery = optimized_query.replace(/^["']|["']$/g, '').trim()

      // Validação de saída: se muito curto, usa query original
      if (cleanQuery.length < 2) {
        console.warn('Query otimizada muito curta, usando query original')
        return {
          optimized_query: user_query,
          tokens_count: user_query.split(/\s+/).length,
          used_clusters: []
        }
      }

      // Detecta quais clusters foram usados (busca simples por substring)
      const used_clusters = cluster_names.filter(cluster => 
        cleanQuery.toLowerCase().includes(cluster.toLowerCase())
      )

      return {
        optimized_query: cleanQuery,
        tokens_count: cleanQuery.split(/\s+/).length,
        used_clusters
      }

    } catch (error: any) {
      console.error('Erro ao otimizar query:', error)
      
      // Fallback: usa query original em caso de erro
      return {
        optimized_query: user_query,
        tokens_count: user_query.split(/\s+/).length,
        used_clusters: []
      }
    }
  }

  /**
   * Função simplificada para casos onde não há necessidade de otimização
   */
  function buildSimpleQuery(user_query: string, cluster_names: string[] = []): string {
    // Remove stopwords básicas em português
    const stopwords = ['o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'em', 'no', 'na', 'para', 'com', 'por']
    
    const tokens = user_query
      .toLowerCase()
      .split(/\s+/)
      .filter(token => token.length > 2 && !stopwords.includes(token))

    // Adiciona até 2 clusters relevantes se houver
    const relevantClusters = cluster_names
      .filter(cluster => user_query.toLowerCase().includes(cluster.toLowerCase()))
      .slice(0, 2)

    return [...tokens, ...relevantClusters].join(' ')
  }

  return {
    optimizeQuery,
    buildSimpleQuery,
    buildPrompt
  }
}
