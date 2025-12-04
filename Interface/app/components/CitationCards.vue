<script setup lang="ts">
interface CitationSource {
  id: string
  title: string
  text: string
  court?: string
  code?: string
  article?: string
  date?: string
  score: number
  meta?: Record<string, any>
}

interface Props {
  sources: CitationSource[]
  totalDocs?: number
  backend?: string
}

const props = defineProps<Props>()

const expandedCards = ref<Set<string>>(new Set())

function toggleCard(id: string) {
  if (expandedCards.value.has(id)) {
    expandedCards.value.delete(id)
  } else {
    expandedCards.value.add(id)
  }
}

function isExpanded(id: string): boolean {
  return expandedCards.value.has(id)
}

function formatScore(score: number): string {
  return (score * 100).toFixed(1)
}

function truncateText(text: string, maxLength: number = 200): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

function getCourtBadgeColor(court: string | undefined): string {
  if (!court) return 'neutral'
  const courtUpper = court.toUpperCase()
  if (courtUpper.includes('STF')) return 'red'
  if (courtUpper.includes('STJ')) return 'blue'
  if (courtUpper.includes('TST')) return 'green'
  if (courtUpper.includes('TSE')) return 'purple'
  return 'neutral'
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch (error) {
    console.error('Error copying text:', error)
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h3 class="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <UIcon name="i-lucide-book-open" class="h-5 w-5" />
        Fontes Consultadas
        <UBadge v-if="totalDocs" color="primary" variant="subtle">
          {{ sources.length }} de {{ totalDocs }}
        </UBadge>
      </h3>
      <UBadge v-if="backend" color="neutral" variant="subtle">
        {{ backend.toUpperCase() }}
      </UBadge>
    </div>

    <!-- Cards de Citações -->
    <div class="space-y-3">
      <div
        v-for="(source, index) in sources"
        :key="source.id"
        class="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 shadow-sm hover:shadow-md transition-shadow duration-200"
      >
        <!-- Card Header -->
        <div class="p-4 cursor-pointer" @click="toggleCard(source.id)">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <!-- Número e Score -->
              <div class="flex items-center gap-2 mb-2">
                <UBadge color="neutral" variant="outline" size="xs">
                  #{{ index + 1 }}
                </UBadge>
                <UBadge color="primary" variant="subtle" size="xs">
                  Relevância: {{ formatScore(source.score) }}%
                </UBadge>
              </div>

              <!-- Título -->
              <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-2">
                {{ source.title || 'Documento sem título' }}
              </h4>

              <!-- Metadados -->
              <div class="flex flex-wrap gap-2 text-xs">
                <UBadge
                  v-if="source.court"
                  :color="getCourtBadgeColor(source.court)"
                  variant="subtle"
                  size="xs"
                >
                  <UIcon name="i-lucide-landmark" class="h-3 w-3 mr-1" />
                  {{ source.court }}
                </UBadge>

                <UBadge
                  v-if="source.code"
                  color="neutral"
                  variant="subtle"
                  size="xs"
                >
                  <UIcon name="i-lucide-file-text" class="h-3 w-3 mr-1" />
                  {{ source.code }}
                </UBadge>

                <UBadge
                  v-if="source.article"
                  color="neutral"
                  variant="subtle"
                  size="xs"
                >
                  <UIcon name="i-lucide-scroll-text" class="h-3 w-3 mr-1" />
                  Art. {{ source.article }}
                </UBadge>

                <UBadge
                  v-if="source.date"
                  color="neutral"
                  variant="subtle"
                  size="xs"
                >
                  <UIcon name="i-lucide-calendar" class="h-3 w-3 mr-1" />
                  {{ source.date }}
                </UBadge>
              </div>

              <!-- Preview do texto (quando fechado) -->
              <p
                v-if="!isExpanded(source.id)"
                class="mt-3 text-sm text-gray-600 dark:text-gray-400 line-clamp-2"
              >
                {{ truncateText(source.text) }}
              </p>
            </div>

            <!-- Botão Expandir -->
            <div class="flex-shrink-0">
              <UIcon
                :name="isExpanded(source.id) ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                class="h-5 w-5 text-gray-400 transition-transform duration-200"
              />
            </div>
          </div>
        </div>

        <!-- Card Body Expandido -->
        <div
          v-if="isExpanded(source.id)"
          class="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800"
        >
          <!-- Texto Completo -->
          <div class="prose prose-sm dark:prose-invert max-w-none mb-4">
            <p class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
              {{ source.text }}
            </p>
          </div>

          <!-- Metadados Adicionais -->
          <div v-if="source.meta && Object.keys(source.meta).length > 0" class="mb-4">
            <details class="text-xs">
              <summary class="cursor-pointer text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200">
                Metadados adicionais
              </summary>
              <pre class="mt-2 p-2 bg-gray-100 dark:bg-gray-900 rounded text-xs overflow-x-auto">{{ JSON.stringify(source.meta, null, 2) }}</pre>
            </details>
          </div>

          <!-- Ações -->
          <div class="flex gap-2">
            <UButton
              icon="i-lucide-copy"
              size="xs"
              variant="outline"
              @click="copyText(source.text)"
            >
              Copiar texto
            </UButton>

            <UButton
              v-if="source.id"
              icon="i-lucide-external-link"
              size="xs"
              variant="outline"
              :title="`ID: ${source.id}`"
            >
              Referência: {{ source.id.substring(0, 8) }}...
            </UButton>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="sources.length === 0"
      class="text-center py-8 text-gray-500 dark:text-gray-400"
    >
      <UIcon name="i-lucide-search-x" class="h-12 w-12 mx-auto mb-2 opacity-50" />
      <p class="text-sm">Nenhum documento encontrado</p>
    </div>
  </div>
</template>
