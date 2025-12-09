<script setup lang="ts">
const { model, models } = useModels()

const items = computed(() => models.map(m => ({
  label: m.name,
  value: m.value,
  icon: 'i-lucide-brain'
})))
</script>

<template>
  <USelectMenu
    v-model="model"
    :items="items"
    icon="i-lucide-brain"
    variant="ghost"
    value-key="value"
    class="hover:bg-default focus:bg-default data-[state=open]:bg-default"
    :ui="{
      trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200'
    }"
  />
</template>
