/**
 * Exemplo de Uso do GPT-5 Query Builder
 * 
 * Este arquivo demonstra como usar o Query Builder e Vector Search
 * de forma programática (fora do contexto Vue/Nuxt).
 */

// ============================================
// EXEMPLO 1: Query Builder Básico
// ============================================

async function exemploQueryBuilderBasico() {
  const { optimizeQuery } = useQueryBuilder()
  
  const input = {
    user_query: "o que é prisão preventiva e quando pode ser decretada",
    cluster_names: ['art. 312', 'art. 313', 'art. 315']
  }
  
  const resultado = await optimizeQuery(input)
  
  console.log('Query Original:', input.user_query)
  console.log('Query Otimizada:', resultado.optimized_query)
  console.log('Tokens:', resultado.tokens_count)
  console.log('Clusters Usados:', resultado.used_clusters)
  
  // Saída esperada:
  // Query Original: o que é prisão preventiva e quando pode ser decretada
  // Query Otimizada: prisão preventiva art. 312 requisitos decreto garantia ordem pública
  // Tokens: 9
  // Clusters Usados: ['art. 312']
}

// ============================================
// EXEMPLO 2: Query Builder com Histórico
// ============================================

async function exemploQueryBuilderComHistorico() {
  const { optimizeQuery } = useQueryBuilder()
  
  const input = {
    user_query: "E as medidas cautelares alternativas?",
    recent_history: "Usuário perguntou sobre prisão preventiva art. 312. Explicamos requisitos e hipóteses.",
    cluster_names: ['art. 312', 'art. 319', 'art. 319-A', 'art. 320']
  }
  
  const resultado = await optimizeQuery(input)
  
  console.log('Query Original:', input.user_query)
  console.log('Histórico:', input.recent_history)
  console.log('Query Otimizada:', resultado.optimized_query)
  
  // Saída esperada:
  // Query Original: E as medidas cautelares alternativas?
  // Histórico: Usuário perguntou sobre prisão preventiva art. 312...
  // Query Otimizada: medidas cautelares alternativas art. 319 art. 320 prisão preventiva
}

// ============================================
// EXEMPLO 3: Vector Search Completo (RAG)
// ============================================

async function exemploVectorSearchRAG() {
  const { search } = useVectorSearch()
  
  try {
    const results = await search(
      "Quais são os requisitos para prisão preventiva?",
      {
        k: 5,              // 5 resultados
        optimize: true     // Usa Query Builder
      }
    )
    
    console.log(`\nEncontrados ${results.total} documentos`)
    console.log(`Backend: ${results.backend}`)
    console.log(`Query processada: ${results.query}`)
    
    results.results.forEach((doc, idx) => {
      console.log(`\n[${idx + 1}] ${doc.article || 'Documento'}`)
      console.log(`Score: ${doc.score.toFixed(4)}`)
      console.log(`Texto: ${doc.text.substring(0, 100)}...`)
    })
    
  } catch (error) {
    console.error('Erro:', error.message)
  }
}

// ============================================
// EXEMPLO 4: Vector Search sem Otimização
// ============================================

async function exemploVectorSearchSemOtimizacao() {
  const { search } = useVectorSearch()
  
  // Busca direta sem otimização (útil para queries já bem formatadas)
  const results = await search(
    "art. 312 CPP prisão preventiva requisitos",
    {
      k: 10,
      optimize: false  // Não otimiza
    }
  )
  
  console.log(`Resultados: ${results.total}`)
  return results
}

// ============================================
// EXEMPLO 5: Health Check do DBVECTOR
// ============================================

async function exemploHealthCheck() {
  const { healthCheck } = useVectorSearch()
  
  try {
    const health = await healthCheck()
    
    console.log('Status:', health.status)
    console.log('Backend:', health.backend)
    console.log('Documentos Indexados:', health.documents)
    console.log('Dimensão dos Embeddings:', health.embedding_dim)
    
    if (health.documents === 0) {
      console.warn('⚠️ Nenhum documento indexado! Execute o pipeline de build.')
    }
    
  } catch (error) {
    console.error('❌ DBVECTOR não está disponível')
  }
}

// ============================================
// EXEMPLO 6: Pipeline RAG Completo
// ============================================

async function pipelineRAGCompleto(userQuery: string) {
  const { search } = useVectorSearch()
  
  console.log('📝 Query do usuário:', userQuery)
  
  // 1. Busca vetorial (com otimização automática)
  console.log('\n🔍 Buscando documentos relevantes...')
  const searchResults = await search(userQuery, {
    k: 5,
    optimize: true
  })
  
  console.log(`✅ ${searchResults.total} documentos encontrados`)
  console.log(`🎯 Query otimizada: "${searchResults.query}"`)
  
  // 2. Monta contexto para GPT
  const context = searchResults.results
    .map((doc, idx) => {
      return `[Documento ${idx + 1}]\n` +
             `Artigo: ${doc.article || 'N/A'}\n` +
             `Score: ${doc.score.toFixed(4)}\n` +
             `Texto: ${doc.text}\n`
    })
    .join('\n---\n\n')
  
  console.log('\n📚 Contexto montado para GPT:')
  console.log(context.substring(0, 500) + '...')
  
  // 3. Envia para GPT (pseudocódigo - já implementado no index.vue)
  console.log('\n🤖 Enviando para GPT com contexto...')
  
  // Aqui você usaria $fetch para chamar OpenAI com o contexto
  // Veja implementação completa em index.vue
  
  return {
    query: searchResults.query,
    documents: searchResults.results,
    context
  }
}

// ============================================
// EXEMPLO 7: Comparação RAG vs. Chat Simples
// ============================================

async function compararRAGvsChat() {
  const query = "Explique a prisão preventiva"
  
  console.log('='.repeat(50))
  console.log('COMPARAÇÃO: RAG vs. Chat Simples')
  console.log('='.repeat(50))
  
  // RAG: Com contexto vetorial
  console.log('\n🔍 RAG (com busca vetorial):')
  const ragResults = await pipelineRAGCompleto(query)
  console.log(`- Documentos usados: ${ragResults.documents.length}`)
  console.log(`- Query otimizada: "${ragResults.query}"`)
  console.log('- Resposta: Fundamentada em jurisprudência real')
  
  // Chat: Sem contexto
  console.log('\n💬 Chat Simples (sem busca):')
  console.log(`- Documentos usados: 0`)
  console.log(`- Query original: "${query}"`)
  console.log('- Resposta: Baseada em conhecimento geral do GPT')
}

// ============================================
// EXEMPLO 8: Tratamento de Erros
// ============================================

async function exemploTratamentoErros() {
  const { search } = useVectorSearch()
  
  try {
    // Query muito curta
    await search("a")
    
  } catch (error) {
    console.error('Erro esperado:', error.message)
    // "Query deve ter pelo menos 2 caracteres"
  }
  
  try {
    // DBVECTOR offline
    await search("teste", { k: 5 })
    
  } catch (error) {
    console.error('Erro de conexão:', error.message)
    // "Banco vetorial não está disponível. Verifique se o DBVECTOR está rodando."
  }
}

// ============================================
// EXEMPLO 9: Uso dos Clusters Disponíveis
// ============================================

function exemploClusters() {
  const { getAvailableClusters } = useVectorSearch()
  
  const clusters = getAvailableClusters()
  
  console.log('📋 Clusters/Artigos Disponíveis:')
  clusters.forEach((cluster, idx) => {
    console.log(`  ${idx + 1}. ${cluster}`)
  })
  
  // Pode usar para sugerir ao usuário
  console.log('\n💡 Sugestão: "Busque por ' + clusters[0] + '"')
}

// ============================================
// EXEMPLO 10: Performance Monitoring
// ============================================

async function exemploPerformanceMonitoring() {
  const { optimizeQuery } = useQueryBuilder()
  const { search } = useVectorSearch()
  
  const query = "requisitos prisão preventiva"
  
  // 1. Tempo de otimização
  console.time('Query Builder')
  const optimized = await optimizeQuery({
    user_query: query,
    cluster_names: ['art. 312']
  })
  console.timeEnd('Query Builder')
  // Esperado: ~500ms
  
  // 2. Tempo de busca vetorial
  console.time('Vector Search')
  const results = await search(optimized.optimized_query, {
    k: 5,
    optimize: false // Já otimizada
  })
  console.timeEnd('Vector Search')
  // Esperado: ~100-200ms
  
  console.log('\n📊 Estatísticas:')
  console.log(`- Query original: ${query.length} chars`)
  console.log(`- Query otimizada: ${optimized.optimized_query.length} chars`)
  console.log(`- Tokens: ${optimized.tokens_count}`)
  console.log(`- Documentos encontrados: ${results.total}`)
  console.log(`- Score médio: ${(results.results.reduce((acc, r) => acc + r.score, 0) / results.total).toFixed(4)}`)
}

// ============================================
// EXECUTAR EXEMPLOS
// ============================================

// Descomente para executar:

// exemploQueryBuilderBasico()
// exemploQueryBuilderComHistorico()
// exemploVectorSearchRAG()
// exemploHealthCheck()
// pipelineRAGCompleto("O que é prisão preventiva?")
// compararRAGvsChat()
// exemploClusters()
// exemploPerformanceMonitoring()

export {
  exemploQueryBuilderBasico,
  exemploQueryBuilderComHistorico,
  exemploVectorSearchRAG,
  exemploVectorSearchSemOtimizacao,
  exemploHealthCheck,
  pipelineRAGCompleto,
  compararRAGvsChat,
  exemploTratamentoErros,
  exemploClusters,
  exemploPerformanceMonitoring
}
