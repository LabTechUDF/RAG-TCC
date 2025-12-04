<script setup lang="ts">
const input = ref('')
const loading = ref(false)
const response = ref('')
const ragSources = ref<any[]>([])

const { model } = useModels()
const { ragEnabled } = useRagMode()

async function sendToOpenAI(prompt: string) {
  loading.value = true
  response.value = ''
  ragSources.value = []
  input.value = prompt
  
  // Se RAG está ativo, usa chat-rag
  if (ragEnabled.value) {
    await sendWithRAG(prompt)
    return
  }
  
  try {
    const config = useRuntimeConfig()
    
    // Validação das credenciais
    if (!config.public.openaiApiKey || config.public.openaiApiKey === 'your_openai_api_key_here') {
      response.value = 'API Key da OpenAI não configurada. Configure no arquivo .env'
      loading.value = false
      return
    }
    
    interface OpenAIResponse {
      id: string
      object: string
      status: string
      output: Array<{
        type: string
        content?: Array<{
          type: string
          text: string
        }>
      }>
    }
    
    const result = await $fetch<OpenAIResponse>('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.public.openaiApiKey}`,
        'Content-Type': 'application/json',
        'OpenAI-Project': config.public.openaiProjectId as string
      },
      body: {
        model: model.value?.replace('openai/', '') || 'gpt-5-nano',
        input: prompt
      }
    })
    
    // Extrai o texto da resposta da estrutura da OpenAI
    let extractedText = ''
    
    if (result?.output) {
      for (const outputItem of result.output) {
        if (outputItem.type === 'message' && outputItem.content) {
          for (const contentItem of outputItem.content) {
            if (contentItem.type === 'output_text' && contentItem.text) {
              extractedText = contentItem.text
              break
            }
          }
        }
        if (extractedText) break
      }
    }
    
    response.value = extractedText || 'Não foi possível extrair a resposta da OpenAI'
  } catch (error: any) {
    console.error('Error sending to OpenAI:', error)
    const errorMessage = error?.data?.message || error?.message || 'Erro desconhecido'
    response.value = `Erro ao processar solicitação: ${errorMessage}`
  } finally {
    loading.value = false
  }
}

async function sendWithRAG(prompt: string) {
  try {
    const result = await $fetch<any>('/api/chat-rag', {
      method: 'POST',
      body: { 
        query: prompt, 
        k: 5,  // top-k = 5 documentos
        user_id: 'guest',  // TODO: Integrar com autenticação real
        session_id: `session_${Date.now()}`
      }
    })

    response.value = result.answer || 'Sem resposta'
    
    // Mapeia contextos completos para CitationCards
    ragSources.value = result.contexts?.map((ctx: any) => ({
      id: ctx.id,
      title: ctx.title || 'Documento sem título',
      text: ctx.text,
      court: ctx.court,
      code: ctx.code,
      article: ctx.article,
      date: ctx.date,
      score: ctx.score,
      meta: ctx.meta
    })) || []
    
    // Log de auditoria no console
    console.log('[RAG Query]', {
      query: prompt,
      sources_count: ragSources.value.length,
      backend: result.backend,
      timestamp: new Date().toISOString()
    })
  } catch (error: any) {
    console.error('Error with RAG:', error)
    const errorMessage = error?.data?.message || error?.message || 'Erro ao conectar com RAG'
    response.value = `Erro: ${errorMessage}`
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

function onSubmit() {
  if (input.value.trim()) {
    sendToOpenAI(input.value)
  }
}

const quickChats: Array<{ label: string; icon: string }> = [
  { label: 'O que é um precedente judicial?', icon: 'i-lucide-scale' },
  { label: 'Explique sobre recursos no STF', icon: 'i-lucide-book-open' },
  { label: 'Como funciona a repercussão geral?', icon: 'i-lucide-users' }
]

</script>

<template>
  <UDashboardPanel id="home" :ui="{ body: 'p-4 sm:p-6' }">
    <template #header>
      <DashboardNavbar />
    </template>

    <template #body>
      <UContainer class="flex-1 flex flex-col justify-center gap-6 py-8 max-w-4xl mx-auto">
        <!-- Cabeçalho com Título e Seletor de Modo -->
        <div class="text-center space-y-4">
          <h1 class="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white">
            Como posso ajudar?
          </h1>
          
          <!-- Seletor de Modo RAG/Simples logo abaixo do título -->
          <SearchModeSelector />
        </div>

        <UChatPrompt
          v-model="input"
          :status="loading ? 'streaming' : 'ready'"
          class="[view-transition-name:chat-prompt]"
          variant="subtle"
          @submit="onSubmit"
        >
          <UChatPromptSubmit color="neutral" />
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
            @click="sendToOpenAI(quickChat.label)"
          />
        </div>

        <!-- Área de Resposta -->
        <div v-if="response || loading" class="mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div v-if="loading" class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-500"></div>
            <span>{{ ragEnabled ? 'Buscando documentos e gerando resposta...' : 'Processando sua solicitação...' }}</span>
          </div>
          
          <div v-else class="space-y-4">
            <div class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <UIcon :name="ragEnabled ? 'i-lucide-database' : 'i-lucide-sparkles'" class="h-4 w-4" />
              {{ ragEnabled ? 'Resposta com RAG' : 'Resposta da IA' }}
            </div>
            <div class="prose prose-sm dark:prose-invert max-w-none">
              <p class="text-gray-900 dark:text-gray-100 leading-relaxed">{{ response }}</p>
            </div>

            <!-- Cards de Citações (Componente Dedicado) -->
            <div v-if="ragEnabled && ragSources.length > 0" class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <CitationCards :sources="ragSources" />
            </div>

            <UButton 
              icon="i-lucide-copy" 
              size="xs" 
              variant="outline" 
              @click="copyToClipboard(response)"
            >
              Copiar resposta
            </UButton>
          </div>
        </div>
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
