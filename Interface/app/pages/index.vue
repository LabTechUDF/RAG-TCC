<script setup lang="ts">
import { marked } from 'marked'

const logger = useClientLogger()
const { user } = useAuth()

// Message history state
interface Message {
  id: string
  role: 'user' | 'assistant'
  parts: Array<{ type: 'text', text: string }>
  timestamp: number
}

// API Response interfaces
interface OpenAIResponse {
  id: string
  choices: Array<{
    message: {
      role: string
      content: string
    }
    finish_reason: string
  }>
}

interface DBVectorSearchResult {
  id: string
  title?: string
  text: string
  court?: string
  code?: string
  article?: string
  date?: string
  score: number
}

interface DBVectorSearchResponse {
  query: string
  total: number
  backend: string
  results: DBVectorSearchResult[]
}

const messages = ref<Message[]>([])
const input = ref('')
const status = ref<'ready' | 'submitted' | 'streaming' | 'error'>('ready')
const useRAG = ref(true)

const { model } = useModels()

logger.info('Home page mounted', 'HomePage')

// Configurar marked para renderização segura
marked.setOptions({
  breaks: true,
  gfm: true
})

// Build conversation history for API calls
function buildHistory(): Array<{ role: 'user' | 'assistant', content: string }> {
  return messages.value.map(msg => ({
    role: msg.role,
    content: msg.parts.find(p => p.type === 'text')?.text || ''
  }))
}

async function sendToOpenAI(prompt: string) {
  logger.info('Sending request', 'HomePage', {
    promptLength: prompt.length,
    model: model.value,
    useRAG: useRAG.value
  })

  // Add user message to history
  const userMessage: Message = {
    id: `user-${Date.now()}`,
    role: 'user',
    parts: [{ type: 'text', text: prompt }],
    timestamp: Date.now()
  }
  messages.value.push(userMessage)

  // Set status to submitted (waiting for response to start)
  status.value = 'submitted'

  // Build history BEFORE adding assistant placeholder (excludes current user message from history sent)
  const history = buildHistory().slice(0, -1) // Exclude current user message, it's sent separately

  try {
    let contextInfo = ''
    let responseText = ''

    // Se estiver em modo RAG, usa o novo endpoint RAG otimizado (Markdown direto)
    if (useRAG.value) {
      logger.info('RAG mode enabled - calling DBVECTOR RAG endpoint', 'HomePage', { query: prompt })

      try {
        // Chama o novo endpoint RAG que retorna Markdown formatado direto
        const ragResponse = await $fetch<string>('/api/dbvector/rag-query', {
          method: 'POST',
          body: {
            promptUsuario: prompt,
            useRag: true,
            k: 10,
            history: history
          }
        })

        logger.info('DBVECTOR RAG query completed', 'HomePage', {
          responseLength: ragResponse.length,
          responsePreview: ragResponse.substring(0, 100)
        })

        responseText = ragResponse

      } catch (dbvectorError: any) {
        logger.error('Error querying DBVECTOR RAG', 'HomePage', {
          error: dbvectorError.message
        }, dbvectorError)

        contextInfo = '⚠️ Erro ao acessar base de conhecimento RAG - usando modo chat simples\n\n'
      }
    }

    // FALLBACK: Modo chat simples ou erro no RAG
    if (!responseText) {
      const result = await $fetch<OpenAIResponse>('/api/openai/chat', {
        method: 'POST',
        body: {
          prompt: prompt,
          model: model.value?.replace('openai/', '') || 'gpt-5',
          history: history
        }
      })

      logger.debug('OpenAI raw response received', 'HomePage', {
        responseId: result?.id,
        choicesCount: result?.choices?.length
      })

      // Extrai o texto da resposta da estrutura da OpenAI
      const extractedText = result?.choices?.[0]?.message?.content || ''

      if (!extractedText) {
        logger.warn('No content extracted from OpenAI response', 'HomePage')
        responseText = 'Não foi possível extrair a resposta da OpenAI'
        status.value = 'error'
      } else {
        responseText = contextInfo + extractedText
      }
    }

    // Add assistant message with response (only after we have content)
    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      parts: [{ type: 'text', text: responseText }],
      timestamp: Date.now()
    }
    messages.value.push(assistantMessage)
    status.value = 'ready'

    logger.info('Request completed', 'HomePage', {
      responseLength: responseText.length,
      useRAG: useRAG.value
    })
  } catch (error: any) {
    logger.error('Error processing request', 'HomePage', {
      statusCode: error?.statusCode,
      message: error?.data?.message || error?.message
    }, error)

    const errorMessage = error?.data?.message || error?.message || 'Desculpe, ocorreu um erro ao processar sua solicitação.'

    // Add error message as assistant response
    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      parts: [{ type: 'text', text: errorMessage }],
      timestamp: Date.now()
    }
    messages.value.push(assistantMessage)
    status.value = 'error'
  }
}

async function copyToClipboard(text: string) {
  logger.debug('Copying text to clipboard', 'HomePage', { textLength: text.length })
  try {
    await navigator.clipboard.writeText(text)
    logger.info('Text copied to clipboard successfully', 'HomePage')
  } catch (error: any) {
    logger.error('Error copying to clipboard', 'HomePage', {}, error)
  }
}

function onSubmit() {
  if (input.value.trim()) {
    logger.debug('Form submitted', 'HomePage', { inputLength: input.value.length })
    const prompt = input.value
    input.value = '' // Clear input immediately
    sendToOpenAI(prompt)
  } else {
    logger.warn('Form submitted with empty input', 'HomePage')
  }
}

// Retry last failed message
function onRetry() {
  // Find the last user message
  const lastUserMessage = messages.value.filter(m => m.role === 'user').pop()
  if (lastUserMessage) {
    const prompt = getTextFromMessage(lastUserMessage)
    logger.info('Retrying last message', 'HomePage', { prompt })
    
    // Remove the last assistant message (the failed one)
    const lastAssistantIndex = messages.value.findIndex(
      (m, i) => i > 0 && m.role === 'assistant' && messages.value[i - 1].id === lastUserMessage.id
    )
    if (lastAssistantIndex !== -1) {
      messages.value.splice(lastAssistantIndex, 1)
    }
    
    sendToOpenAI(prompt)
  }
}

// Helper to get text from message for rendering
function getTextFromMessage(message: Message): string {
  return message.parts.find(p => p.type === 'text')?.text || ''
}

// Helper to render markdown
function renderMarkdown(text: string): string {
  try {
    return marked.parse(text)
  } catch (error) {
    logger.error('Error parsing markdown', 'HomePage', {}, error)
    return `<pre>${text}</pre>`
  }
}

</script>

<template>
  <UDashboardPanel id="home" :ui="{ body: 'p-0 sm:p-0' }">
    <template #header>
      <DashboardNavbar />
    </template>

    <template #body>
      <div class="flex flex-col h-full">
        <!-- Chat Messages Area -->
        <div v-if="messages.length > 0" class="flex-1 overflow-y-auto px-4 py-[60px]">
          <UChatMessages 
            :messages="messages" 
            :status="status"
            :user="{
              avatar: user ? { src: user.profilePicture, alt: user.name } : { icon: 'i-lucide-user' },
              variant: 'soft',
              side: 'right'
            }"
            :assistant="{
              avatar: { icon: 'i-lucide-bot' },
              variant: 'outline',
              side: 'left'
            }"
            should-auto-scroll
          >
            <template #content="{ message }">
              <div 
                v-html="renderMarkdown(getTextFromMessage(message))" 
                class="prose prose-sm dark:prose-invert max-w-none markdown-content"
              />
            </template>

            <template #actions="{ message }">
              <UButton 
                v-if="message.role === 'assistant' && getTextFromMessage(message)"
                icon="i-lucide-copy" 
                size="xs" 
                variant="ghost" 
                color="neutral"
                @click="copyToClipboard(getTextFromMessage(message))"
              />
            </template>

            <template #indicator>
              <UButton
                class="px-0"
                color="neutral"
                variant="link"
                loading
                loading-icon="i-lucide-loader-circle"
                label="Thinking..."
              />
            </template>
          </UChatMessages>
        </div>

        <!-- Welcome Screen (when no messages) -->
        <UContainer v-else class="flex-1 flex flex-col justify-center gap-4 sm:gap-6 py-8">
          <h1 class="text-3xl sm:text-4xl text-highlighted font-bold">
            Como posso ajudar?
          </h1>

          <!-- Seletor de Modo: RAG vs Chat Simples -->
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <label class="text-sm font-medium text-gray-600 dark:text-gray-400">
                Modo de Operação
              </label>
              <span class="text-xs text-gray-500 dark:text-gray-500">
                {{ useRAG ? 'Base de Conhecimento' : 'OpenAI Direto' }}
              </span>
            </div>
            
            <div class="grid grid-cols-2 gap-2">
              <!-- RAG Mode -->
              <button
                @click="useRAG = true"
                :class="[
                  'group relative flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-all duration-200',
                  useRAG 
                    ? 'bg-gradient-to-br from-primary-500 to-primary-600 shadow-lg shadow-primary-500/25' 
                    : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-primary-400 dark:hover:border-primary-600 hover:shadow-md'
                ]"
              >
                <div :class="[
                  'flex items-center gap-2 transition-all',
                  useRAG ? 'text-white' : 'text-gray-700 dark:text-gray-300'
                ]">
                  <div :class="[
                    'w-1.5 h-1.5 rounded-full transition-all',
                    useRAG ? 'bg-white shadow-lg shadow-white/50' : 'bg-gray-300 dark:bg-gray-600 group-hover:bg-primary-400'
                  ]" />
                  <span class="text-sm font-medium">RAG</span>
                </div>
              </button>

              <!-- Simple Chat Mode -->
              <button
                @click="useRAG = false"
                :class="[
                  'group relative flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-all duration-200',
                  !useRAG 
                    ? 'bg-gradient-to-br from-primary-500 to-primary-600 shadow-lg shadow-primary-500/25' 
                    : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-primary-400 dark:hover:border-primary-600 hover:shadow-md'
                ]"
              >
                <div :class="[
                  'flex items-center gap-2 transition-all',
                  !useRAG ? 'text-white' : 'text-gray-700 dark:text-gray-300'
                ]">
                  <div :class="[
                    'w-1.5 h-1.5 rounded-full transition-all',
                    !useRAG ? 'bg-white shadow-lg shadow-white/50' : 'bg-gray-300 dark:bg-gray-600 group-hover:bg-primary-400'
                  ]" />
                  <span class="text-sm font-medium">Chat Simples</span>
                </div>
              </button>
            </div>
            
            <!-- Descrição do modo selecionado -->
            <div class="px-3 py-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg border-l-2 border-primary-500">
              <p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                <template v-if="useRAG">
                  Respostas baseadas em documentos jurídicos da base de conhecimento para informações precisas e contextualizadas.
                </template>
                <template v-else>
                  Conversação direta com o modelo OpenAI. Ideal para perguntas gerais sem necessidade de documentação específica.
                </template>
              </p>
            </div>
          </div>
        </UContainer>

        <!-- Chat Prompt - Fixed at bottom -->
        <UContainer class="py-4 sm:py-6">
          <UChatPrompt
            v-model="input"
            :status="status"
            placeholder="Digite sua pergunta..."
            @submit="onSubmit"
          >
            <!-- Custom submit button without stop functionality (no streaming) -->
            <UButton
              v-if="status === 'error'"
              type="button"
              icon="i-lucide-rotate-ccw"
              color="error"
              variant="soft"
              size="md"
              square
              @click="onRetry"
            />
            <UButton
              v-else
              type="submit"
              :icon="status === 'submitted' ? '' : 'i-lucide-arrow-up'"
              :loading="status === 'submitted'"
              :disabled="status === 'submitted'"
              color="primary"
              variant="solid"
              size="md"
              square
            />

            <template #footer>
              <ModelSelect v-model="model" />
            </template>
          </UChatPrompt>
        </UContainer>
      </div>
    </template>
  </UDashboardPanel>
</template>

<style scoped>
/* Estilos para conteúdo Markdown renderizado */
.markdown-content :deep(h1) {
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  color: rgb(17 24 39);
}

.dark .markdown-content :deep(h1) {
  color: rgb(243 244 246);
}

.markdown-content :deep(h2) {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 1.25rem;
  margin-bottom: 0.75rem;
  color: rgb(31 41 55);
  border-bottom: 2px solid rgb(229 231 235);
  padding-bottom: 0.5rem;
}

.dark .markdown-content :deep(h2) {
  color: rgb(229 231 235);
  border-bottom-color: rgb(55 65 81);
}

.markdown-content :deep(h3) {
  font-size: 1.125rem;
  font-weight: 600;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: rgb(31 41 55);
}

.dark .markdown-content :deep(h3) {
  color: rgb(229 231 235);
}

.markdown-content :deep(p) {
  margin-bottom: 0.75rem;
  color: rgb(55 65 81);
  line-height: 1.625;
}

.dark .markdown-content :deep(p) {
  color: rgb(209 213 219);
}

.markdown-content :deep(ul) {
  list-style-type: disc;
  list-style-position: inside;
  margin-bottom: 1rem;
}

.markdown-content :deep(ul li) {
  margin-top: 0.5rem;
}

.markdown-content :deep(ol) {
  list-style-type: decimal;
  list-style-position: inside;
  margin-bottom: 1rem;
}

.markdown-content :deep(ol li) {
  margin-top: 0.5rem;
}

.markdown-content :deep(li) {
  color: rgb(55 65 81);
  margin-left: 1rem;
}

.dark .markdown-content :deep(li) {
  color: rgb(209 213 219);
}

.markdown-content :deep(a) {
  color: rgb(37 99 235);
  text-decoration: underline;
  font-weight: 500;
  transition: color 0.15s ease-in-out;
}

.markdown-content :deep(a:hover) {
  color: rgb(29 78 216);
}

.dark .markdown-content :deep(a) {
  color: rgb(96 165 250);
}

.dark .markdown-content :deep(a:hover) {
  color: rgb(147 197 253);
}

.markdown-content :deep(strong) {
  font-weight: 700;
  color: rgb(17 24 39);
}

.dark .markdown-content :deep(strong) {
  color: rgb(243 244 246);
}

.markdown-content :deep(em) {
  font-style: italic;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid rgb(59 130 246);
  padding-left: 1rem;
  font-style: italic;
  margin: 1rem 0;
  color: rgb(75 85 99);
  background-color: rgb(249 250 251);
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  border-radius: 0 0.25rem 0.25rem 0;
}

.dark .markdown-content :deep(blockquote) {
  color: rgb(156 163 175);
  background-color: rgb(31 41 55);
}

.markdown-content :deep(code) {
  background-color: rgb(243 244 246);
  padding: 0.125rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
  font-family: ui-monospace, monospace;
  color: rgb(37 99 235);
}

.dark .markdown-content :deep(code) {
  background-color: rgb(31 41 55);
  color: rgb(96 165 250);
}

.markdown-content :deep(pre) {
  background-color: rgb(243 244 246);
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin-bottom: 1rem;
}

.dark .markdown-content :deep(pre) {
  background-color: rgb(31 41 55);
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.markdown-content :deep(hr) {
  margin: 1.5rem 0;
  border-color: rgb(209 213 219);
}

.dark .markdown-content :deep(hr) {
  border-color: rgb(55 65 81);
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.markdown-content :deep(th) {
  background-color: rgb(243 244 246);
  border: 1px solid rgb(209 213 219);
  padding: 0.5rem 1rem;
  text-align: left;
  font-weight: 600;
}

.dark .markdown-content :deep(th) {
  background-color: rgb(31 41 55);
  border-color: rgb(55 65 81);
}

.markdown-content :deep(td) {
  border: 1px solid rgb(209 213 219);
  padding: 0.5rem 1rem;
}

.dark .markdown-content :deep(td) {
  border-color: rgb(55 65 81);
}
</style>
