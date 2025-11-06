<script setup lang="ts">
const input = ref('')
const loading = ref(false)
const response = ref('')
const vectorResults = ref<any[]>([])
const showVectorResults = ref(false)
const searchMode = ref<'rag' | 'chat'>('rag') // 'rag' usa vector search + GPT, 'chat' usa apenas GPT
const citations = ref<string[]>([])
const coverageLevel = ref<'high' | 'medium' | 'low' | 'none'>('none')
const suggestions = ref<string[]>([])
const lastLog = ref<string>('')

// Dev mode check (import.meta não funciona em template Vue)
const isDev = computed(() => import.meta.dev)

const { model } = useModels()
const { search: vectorSearch } = useVectorSearch()
const { composeAnswer, convertToRetrievedDocuments } = useAnswerComposer()
const { generateRequestId, logToConsole, generateLog } = useRagLogger()

async function createChat(prompt: string) {
  input.value = prompt
  loading.value = true
  const chat = await $fetch('/api/chats', {
    method: 'POST',
    body: { input: prompt }
  })

  refreshNuxtData('chats')
  navigateTo(`/chat/${chat?.id}`)
}

async function sendToRAG(prompt: string) {
  loading.value = true
  response.value = ''
  vectorResults.value = []
  showVectorResults.value = false
  citations.value = []
  suggestions.value = []
  input.value = prompt
  
  // Métricas do pipeline
  const requestId = generateRequestId()
  const pipelineStart = Date.now()
  let g1Start = 0, g1End = 0
  let vdbStart = 0, vdbEnd = 0
  let g2Start = 0, g2End = 0
  let errorMsg = ''
  
  try {
    // 1. G1: Query Builder
    g1Start = Date.now()
    const searchResponse = await vectorSearch(prompt, {
      k: 5,
      optimize: true // Usa GPT-5 Query Builder
    })
    g1End = Date.now()
    
    // Nota: searchResponse já inclui métricas do G1 se retornadas pelo vectorSearch
    vectorResults.value = searchResponse.results
    showVectorResults.value = true
    
    // 2. VDB: Vector Search (já incluído no searchResponse)
    vdbStart = g1End
    vdbEnd = g1End // Ajustar se tivermos separação de métricas
    
    // Converter documentos
    const retrievedDocs = convertToRetrievedDocuments(searchResponse.results)
    
    // 3. G2: Answer Composer
    g2Start = Date.now()
    const answerResult = await composeAnswer({
      user_prompt: prompt,
      recent_history: '', // TODO: integrar histórico real se disponível
      retrieved: retrievedDocs
    })
    g2End = Date.now()
    
    response.value = answerResult.answer
    citations.value = answerResult.citations_used
    coverageLevel.value = answerResult.coverage_level
    suggestions.value = answerResult.suggestions || []
    
    const pipelineEnd = Date.now()
    
    // Calcular scores
    const scores = searchResponse.results.map((r: any) => r.score || 0)
    const avgScore = scores.length > 0 ? scores.reduce((a: number, b: number) => a + b, 0) / scores.length : 0
    const topScore = scores.length > 0 ? Math.max(...scores) : 0
    
    // Gerar log estruturado
    const logEntry = {
      request_id: requestId,
      timestamp: new Date().toISOString(),
      user_query: prompt,
      lang: 'pt-BR', // Detectar automaticamente se necessário
      g1: {
        model: 'gpt-4o-mini',
        optimized_query: prompt, // TODO: capturar query otimizada real
        tokens_count: prompt.split(/\s+/).length,
        used_clusters: [], // TODO: capturar clusters reais
        latency_ms: g1End - g1Start
      },
      vdb: {
        backend: 'faiss' as const,
        k: 5,
        total: searchResponse.results.length,
        avg_score: avgScore,
        top_score: topScore,
        doc_ids: searchResponse.results.map((r: any) => r.id),
        latency_ms: vdbEnd - vdbStart
      },
      g2: {
        model: 'gpt-4o-mini',
        coverage: answerResult.coverage_level,
        citations_used: answerResult.citations_used,
        suggestions_count: answerResult.suggestions?.length || 0,
        answer_chars: answerResult.answer.length,
        latency_ms: g2End - g2Start
      },
      pipeline_total_ms: pipelineEnd - pipelineStart,
      error: errorMsg
    }
    
    // Log para console
    logToConsole(logEntry)
    
    // Salvar último log para exibição (opcional)
    lastLog.value = generateLog(logEntry)
    
  } catch (error: any) {
    console.error('Error in RAG pipeline:', error)
    errorMsg = error?.message || error?.data?.error?.message || 'Erro desconhecido'
    response.value = `Desculpe, ocorreu um erro ao processar sua solicitação: ${errorMsg}`
    
    // Log de erro
    const pipelineEnd = Date.now()
    const errorLogEntry = {
      request_id: requestId,
      timestamp: new Date().toISOString(),
      user_query: prompt,
      lang: 'pt-BR',
      g1: {
        model: 'gpt-4o-mini',
        optimized_query: '',
        tokens_count: 0,
        used_clusters: [],
        latency_ms: g1End - g1Start
      },
      vdb: {
        backend: 'faiss' as const,
        k: 5,
        total: 0,
        avg_score: 0,
        top_score: 0,
        doc_ids: [],
        latency_ms: 0
      },
      g2: {
        model: 'gpt-4o-mini',
        coverage: 'none' as const,
        citations_used: [],
        suggestions_count: 0,
        answer_chars: 0,
        latency_ms: 0
      },
      pipeline_total_ms: pipelineEnd - pipelineStart,
      error: errorMsg
    }
    
    logToConsole(errorLogEntry)
    lastLog.value = generateLog(errorLogEntry)
    
  } finally {
    loading.value = false
  }
}

async function sendToOpenAI(prompt: string) {
  loading.value = true
  response.value = ''
  vectorResults.value = []
  showVectorResults.value = false
  input.value = prompt
  
  try {
    const config = useRuntimeConfig()
    
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
    }
    
    const result = await $fetch<OpenAIResponse>('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.public.openaiApiKey}`,
        'Content-Type': 'application/json',
        'OpenAI-Project': config.public.openaiProjectId as string
      },
      body: {
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'user',
            content: prompt
          }
        ]
      }
    })
    
    const extractedText = result?.choices?.[0]?.message?.content || 'Não foi possível extrair a resposta da OpenAI'
    response.value = extractedText
    
  } catch (error: any) {
    console.error('Error sending to OpenAI:', error)
    const errorMessage = error?.data?.error?.message || error?.message || 'Erro desconhecido'
    response.value = `Desculpe, ocorreu um erro ao processar sua solicitação: ${errorMessage}`
  } finally {
    loading.value = false
  }
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    // Aqui você pode adicionar um toast de sucesso se quiser
  } catch (error) {
    console.error('Error copying to clipboard:', error)
  }
}

async function createChatFromResponse() {
  if (input.value) {
    await createChat(input.value)
  }
}

function onSubmit() {
  if (input.value.trim()) {
    if (searchMode.value === 'rag') {
      sendToRAG(input.value)
    } else {
      sendToOpenAI(input.value)
    }
  }
}

const quickChats = [
  {
    label: 'Explique medidas cautelares art. 319',
    icon: 'i-lucide-scale'
  },
  {
    label: 'Diferença entre prisão preventiva e temporária',
    icon: 'i-lucide-gavel'
  },
  {
    label: 'Jurisprudência sobre liberdade provisória',
    icon: 'i-lucide-book-open'
  }
]
</script>

<template>
  <UDashboardPanel id="home" :ui="{ body: 'p-0 sm:p-0' }">
    <template #header>
      <DashboardNavbar />
    </template>

    <template #body>
      <UContainer class="flex-1 flex flex-col justify-center gap-4 sm:gap-6 py-8">
        <div class="space-y-2">
          <h1 class="text-3xl sm:text-4xl text-highlighted font-bold">
            Como posso ajudar?
          </h1>
          
          <!-- Toggle RAG / Chat Mode -->
          <div class="flex items-center gap-3">
            <span class="text-sm text-gray-600 dark:text-gray-400">Modo:</span>
            <UButton
              :color="searchMode === 'rag' ? 'primary' : 'neutral'"
              :variant="searchMode === 'rag' ? 'solid' : 'outline'"
              size="xs"
              @click="searchMode = 'rag'"
            >
              🔍 RAG (Busca Vetorial)
            </UButton>
            <UButton
              :color="searchMode === 'chat' ? 'primary' : 'neutral'"
              :variant="searchMode === 'chat' ? 'solid' : 'outline'"
              size="xs"
              @click="searchMode = 'chat'"
            >
              💬 Chat Simples
            </UButton>
          </div>
          
          <p v-if="searchMode === 'rag'" class="text-xs text-gray-500 dark:text-gray-400">
            ✨ Busca otimizada com GPT-5 Query Builder + banco vetorial
          </p>
        </div>

        <UChatPrompt
          v-model="input"
          :status="loading ? 'streaming' : 'ready'"
          class="[view-transition-name:chat-prompt]"
          variant="subtle"
          @submit="onSubmit"
        >
          <UChatPromptSubmit color="neutral" />

          <template #footer>
            <ModelSelect v-model="model" />
          </template>
        </UChatPrompt>

        <div class="flex flex-wrap gap-2">
          <UButton
            v-for="quickChat in quickChats"
            :key="quickChat.label"
            :icon="quickChat.icon"
            :label="quickChat.label"
            size="sm"
            color="neutral"
            variant="outline"
            :loading="loading"
            class="cursor-pointer hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:scale-105 transition-all duration-200 hover:shadow-md"
            @click="searchMode === 'rag' ? sendToRAG(quickChat.label) : sendToOpenAI(quickChat.label)"
          />
        </div>

        <!-- Área de Resultados Vetoriais (apenas no modo RAG) -->
        <div v-if="showVectorResults && vectorResults.length > 0" class="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <div class="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300 mb-3">
            <UIcon name="i-lucide-database" class="h-4 w-4" />
            Documentos Relevantes Encontrados ({{ vectorResults.length }})
          </div>
          <div class="space-y-2 max-h-60 overflow-y-auto">
            <div 
              v-for="(doc, idx) in vectorResults" 
              :key="doc.id"
              class="text-xs p-2 bg-white dark:bg-gray-800 rounded border border-blue-100 dark:border-blue-900"
            >
              <div class="font-medium text-blue-600 dark:text-blue-400">
                [{{ idx + 1 }}] {{ doc.article || 'Documento' }} 
                <span class="text-gray-500 ml-2">(score: {{ doc.score.toFixed(3) }})</span>
              </div>
              <div class="text-gray-600 dark:text-gray-300 mt-1">
                {{ doc.text.substring(0, 150) }}{{ doc.text.length > 150 ? '...' : '' }}
              </div>
            </div>
          </div>
        </div>

        <!-- Área de Resposta -->
        <div v-if="response || loading" class="mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div v-if="loading" class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-500"></div>
            <span>{{ searchMode === 'rag' ? 'Buscando e processando...' : 'Processando sua solicitação...' }}</span>
          </div>
          
          <div v-else class="space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                <UIcon name="i-lucide-sparkles" class="h-4 w-4" />
                Resposta da IA {{ searchMode === 'rag' ? '(RAG)' : '' }}
              </div>
              
              <!-- Coverage Badge (apenas no modo RAG) -->
              <div v-if="searchMode === 'rag'" class="flex items-center gap-2">
                <UBadge 
                  :color="coverageLevel === 'high' ? 'green' : coverageLevel === 'medium' ? 'yellow' : coverageLevel === 'low' ? 'orange' : 'red'"
                  variant="subtle"
                  size="xs"
                >
                  {{ coverageLevel === 'high' ? '🎯 Alta Cobertura' : 
                     coverageLevel === 'medium' ? '⚡ Média Cobertura' : 
                     coverageLevel === 'low' ? '⚠️ Baixa Cobertura' : 
                     '❌ Sem Cobertura' }}
                </UBadge>
                <UBadge 
                  v-if="citations.length > 0"
                  color="blue"
                  variant="subtle"
                  size="xs"
                >
                  📚 {{ citations.length }} {{ citations.length === 1 ? 'citação' : 'citações' }}
                </UBadge>
              </div>
            </div>
            
            <div class="prose prose-sm dark:prose-invert max-w-none">
              <p class="text-gray-900 dark:text-gray-100 leading-relaxed whitespace-pre-wrap">{{ response }}</p>
            </div>
            
            <!-- Citations List (apenas no modo RAG se houver citações) -->
            <div v-if="searchMode === 'rag' && citations.length > 0" class="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
              <div class="text-xs font-medium text-blue-700 dark:text-blue-300 mb-2">
                📖 Fontes Citadas:
              </div>
              <div class="flex flex-wrap gap-1">
                <UBadge
                  v-for="citation in citations"
                  :key="citation"
                  size="xs"
                  color="blue"
                  variant="outline"
                  class="font-mono"
                >
                  [{{ citation }}]
                </UBadge>
              </div>
            </div>
            
            <!-- Suggestions (apenas se cobertura baixa) -->
            <div v-if="searchMode === 'rag' && suggestions.length > 0" class="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded border border-yellow-200 dark:border-yellow-800">
              <div class="text-xs font-medium text-yellow-700 dark:text-yellow-300 mb-2">
                💡 Sugestões para melhorar a busca:
              </div>
              <ul class="text-xs text-yellow-600 dark:text-yellow-400 space-y-1 list-disc list-inside">
                <li v-for="(suggestion, idx) in suggestions" :key="idx">
                  {{ suggestion }}
                </li>
              </ul>
            </div>
            
            <div class="flex gap-2">
              <UButton 
                icon="i-lucide-copy" 
                size="xs" 
                variant="outline" 
                @click="copyToClipboard(response)"
              >
                Copiar
              </UButton>
            </div>
          </div>
        </div>
        
        <!-- RAG Ops Log Viewer (apenas modo RAG, para debugging) -->
        <div v-if="searchMode === 'rag' && lastLog && isDev" class="mt-4 p-4 bg-gray-900 dark:bg-gray-950 rounded-lg border border-gray-700">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2 text-xs font-mono text-green-400">
              <UIcon name="i-lucide-terminal" class="h-3 w-3" />
              RAG Ops Log (dev only)
            </div>
            <UButton
              icon="i-lucide-copy"
              size="2xs"
              color="gray"
              variant="ghost"
              @click="copyToClipboard(lastLog)"
            >
              Copy Log
            </UButton>
          </div>
          <pre class="text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">{{ lastLog }}</pre>
        </div>
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
