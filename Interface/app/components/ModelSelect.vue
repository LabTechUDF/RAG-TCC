<script setup lang="ts">
const { model, models } = useModels()

// Mapeia modelos para ícones disponíveis
function getModelIcon(modelName: string): string {
  const provider = modelName.split('/')[0]
  
  const iconMap: Record<string, string> = {
    'openai': 'i-simple-icons-openai',
    'anthropic': 'i-simple-icons-anthropic',
    'google': 'i-simple-icons-google',
    'gpt-5-nano': 'i-lucide-sparkles', // Ícone genérico para modelos sem provider
    'default': 'i-lucide-bot'
  }
  
  return iconMap[provider] || iconMap[modelName] || iconMap.default
}

const items = computed(() => models.map(m => ({
  label: m,
  value: m,
  icon: getModelIcon(m)
})))
</script>

<template>
  <USelectMenu
    v-model="model"
    :items="items"
    :icon="getModelIcon(model)"
    variant="ghost"
    value-key="value"
    class="hover:bg-default focus:bg-default data-[state=open]:bg-default"
    :ui="{
      trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200'
    }"
  />
</template>
