<script setup lang="ts">
import { marked } from 'marked'

const logger = useClientLogger()
const input = ref('')
const loading = ref(false)
const response = ref('')
const useRAG = ref(true) // Toggle entre RAG e chat simples

const { model } = useModels()

logger.info('Home page mounted', 'HomePage')

// Configurar marked para renderização segura
marked.setOptions({
  breaks: true,
  gfm: true
})

// Computed property para renderizar Markdown
const renderedMarkdown = computed(() => {
  if (!response.value) return ''
  try {
    return marked.parse(response.value)
  } catch (error) {
    logger.error('Error parsing markdown', 'HomePage', {}, error)
    return `<pre>${response.value}</pre>`
  }
})

async function sendToOpenAI(prompt: string) {
  logger.info('Sending request', 'HomePage', { 
    promptLength: prompt.length,
    model: model.value,
    useRAG: useRAG.value
  })
  
  loading.value = true
  response.value = ''
  input.value = prompt
  
  try {
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

    let finalPrompt = prompt
    let contextInfo = ''

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
            k: 10
          }
        })

        logger.info('DBVECTOR RAG query completed', 'HomePage', {
          responseLength: ragResponse.length,
          responsePreview: ragResponse.substring(0, 100)
        })

        // A resposta já vem formatada em Markdown, pronta para exibição
        response.value = ragResponse
        logger.info('Request completed with RAG', 'HomePage', {
          responseLength: response.value.length,
          responsePreview: response.value.substring(0, 200)
        })
        
        // Retorna sem chamar OpenAI diretamente
        return
        
      } catch (dbvectorError: any) {
        logger.error('Error querying DBVECTOR RAG', 'HomePage', {
          error: dbvectorError.message
        }, dbvectorError)
        
        contextInfo = '⚠️ Erro ao acessar base de conhecimento RAG - usando modo chat simples'
        // Continua com o fluxo normal (chat simples) se houver erro no RAG
      }
    }
    
    // FALLBACK: Modo chat simples ou erro no RAG
    // Usa a API do servidor que tem acesso seguro à chave da OpenAI
    const result = await $fetch<OpenAIResponse>('/api/openai/chat', {
      method: 'POST',
      body: {
        prompt: finalPrompt,
        model: model.value?.replace('openai/', '') || 'gpt-4o-mini'
      }
    })
    
    logger.debug('OpenAI raw response received', 'HomePage', {
      responseId: result?.id,
      choicesCount: result?.choices?.length,
      fullResponse: result
    })
    
    // Extrai o texto da resposta da estrutura da OpenAI
    const extractedText = result?.choices?.[0]?.message?.content || ''
    
    logger.debug('Extracted text from response', 'HomePage', {
      hasExtractedText: !!extractedText,
      extractedTextLength: extractedText.length,
      extractedTextPreview: extractedText.substring(0, 100)
    })
    
    if (!extractedText) {
      logger.warn('No content extracted from OpenAI response', 'HomePage', {
        responseStructure: {
          hasChoices: !!result?.choices,
          choicesLength: result?.choices?.length,
          firstChoice: result?.choices?.[0],
          hasMessage: !!result?.choices?.[0]?.message,
          hasContent: !!result?.choices?.[0]?.message?.content
        }
      })
    }
    
    // Adiciona informação de contexto se estiver em modo RAG
    const finalResponse = contextInfo 
      ? `${contextInfo}\n\n${extractedText || 'Não foi possível extrair a resposta da OpenAI'}`
      : extractedText || 'Não foi possível extrair a resposta da OpenAI'
    
    response.value = finalResponse
    logger.info('Request completed', 'HomePage', {
      responseLength: response.value.length,
      useRAG: useRAG.value,
      responsePreview: response.value.substring(0, 200)
    })
  } catch (error: any) {
    logger.error('Error processing request', 'HomePage', {
      statusCode: error?.statusCode,
      message: error?.data?.message || error?.message
    }, error)
    
    const errorMessage = error?.data?.message || error?.message || 'Desculpe, ocorreu um erro ao processar sua solicitação.'
    response.value = errorMessage
  } finally {
    loading.value = false
  }
}

async function copyToClipboard(text: string) {
  logger.debug('Copying text to clipboard', 'HomePage', { textLength: text.length })
  try {
    await navigator.clipboard.writeText(text)
    logger.info('Text copied to clipboard successfully', 'HomePage')
    // Aqui você pode adicionar um toast de sucesso se quiser
  } catch (error: any) {
    logger.error('Error copying to clipboard', 'HomePage', {}, error)
  }
}

function onSubmit() {
  if (input.value.trim()) {
    logger.debug('Form submitted', 'HomePage', { inputLength: input.value.length })
    sendToOpenAI(input.value)
  } else {
    logger.warn('Form submitted with empty input', 'HomePage')
  }
}
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

        <!-- Seletor de Modo: RAG vs Chat Simples - Design Minimalista -->
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
          
          <!-- Descrição do modo selecionado - Minimalista -->
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
              <!-- Renderiza Markdown -->
              <div v-html="renderedMarkdown" class="text-gray-900 dark:text-gray-100 leading-relaxed markdown-content"></div>
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
