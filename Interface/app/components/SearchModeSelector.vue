<script setup lang="ts">
const { ragEnabled, setRagEnabled } = useRagMode()

type SearchMode = 'rag' | 'simple'

const searchMode = computed<SearchMode>({
  get: () => ragEnabled.value ? 'rag' : 'simple',
  set: (value: SearchMode) => setRagEnabled(value === 'rag')
})

function selectMode(mode: SearchMode) {
  searchMode.value = mode
}
</script>

<template>
  <div class="flex flex-col items-center gap-3">
    <!-- Container com Label e Botões alinhados -->
    <div class="flex items-center gap-3">
      <!-- Label "Modo:" à esquerda -->
      <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Modo:</span>

      <!-- Botões de Seleção de Modo -->
      <div class="flex items-center gap-2" role="group" aria-label="Seleção de modo de busca">
        <!-- Botão RAG (Busca Vetorial) -->
        <button
          type="button"
          @click="selectMode('rag')"
          :aria-pressed="searchMode === 'rag'"
          aria-label="Modo RAG com Busca Vetorial"
          :class="[
            'flex items-center gap-2 px-5 py-2.5 rounded-full font-bold text-sm transition-all duration-200',
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-50 dark:focus:ring-offset-gray-900',
            searchMode === 'rag'
              ? 'bg-blue-600 text-white shadow-lg hover:bg-blue-700 focus:ring-blue-500 dark:bg-blue-500 dark:hover:bg-blue-600'
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-gray-300 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-gray-400'
          ]"
        >
          <span class="text-base" aria-hidden="true">🔍</span>
          <span class="whitespace-nowrap">RAG (Busca Vetorial)</span>
        </button>

        <!-- Botão Chat Simples -->
        <button
          type="button"
          @click="selectMode('simple')"
          :aria-pressed="searchMode === 'simple'"
          aria-label="Modo Chat Simples"
          :class="[
            'flex items-center gap-2 px-5 py-2.5 rounded-full font-bold text-sm transition-all duration-200',
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-50 dark:focus:ring-offset-gray-900',
            searchMode === 'simple'
              ? 'bg-gray-300 text-gray-900 shadow-lg hover:bg-gray-400 focus:ring-gray-400 dark:bg-gray-600 dark:text-white dark:hover:bg-gray-500'
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-gray-300 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-gray-400'
          ]"
        >
          <span class="text-base" aria-hidden="true">💬</span>
          <span class="whitespace-nowrap">Chat Simples</span>
        </button>
      </div>
    </div>

    <!-- Texto Explicativo (aparece sempre quando RAG está ativo) -->
    <transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <p
        v-if="searchMode === 'rag'"
        class="text-xs text-gray-500 dark:text-gray-400 text-center"
      >
        <span class="inline-block mr-1">✨</span>
        Busca otimizada com GPT-5 Query Builder + banco vetorial
      </p>
    </transition>
  </div>
</template>

