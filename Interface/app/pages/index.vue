<script setup lang="ts">
const input = ref('')
const loading = ref(false)
const response = ref('')

const { model } = useModels()

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

async function sendToOpenAI(prompt: string) {
  loading.value = true
  response.value = ''
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
        model: model.value?.replace('openai/', '') || 'gpt-4o-mini',
        messages: [
          {
            role: 'user',
            content: prompt
          }
        ]
      }
    })
    
    // Extrai o texto da resposta da estrutura da OpenAI
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
    sendToOpenAI(input.value)
  }
}

const quickChats = [
  {
    label: 'Explique um conceito jurídico',
    icon: 'i-lucide-book-open'
  },
  {
    label: 'Analise uma jurisprudência',
    icon: 'i-lucide-scale'
  },
  {
    label: 'Resuma um artigo de lei',
    icon: 'i-lucide-file-text'
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
        <h1 class="text-3xl sm:text-4xl text-highlighted font-bold">
          Como posso ajudar?
        </h1>

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
            @click="sendToOpenAI(quickChat.label)"
          />
        </div>

        <!-- Área de Resposta -->
        <div v-if="response || loading" class="mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div v-if="loading" class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-500"></div>
            <span>Processando sua solicitação...</span>
          </div>
          
          <div v-else class="space-y-3">
            <div class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <UIcon name="i-lucide-sparkles" class="h-4 w-4" />
              Resposta da IA
            </div>
            <div class="prose prose-sm dark:prose-invert max-w-none">
              <p class="text-gray-900 dark:text-gray-100 leading-relaxed">{{ response }}</p>
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
      </UContainer>
    </template>
  </UDashboardPanel>
</template>
