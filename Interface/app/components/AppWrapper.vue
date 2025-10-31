<template>
  <ClientOnly>
    <UApp :toaster="{ position: 'top-right' }">
      <slot />
    </UApp>
    <template #fallback>
      <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
        <div class="flex items-center justify-center min-h-screen">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      </div>
    </template>
  </ClientOnly>
</template>

<script setup lang="ts">
// Wrapper component to handle SSR hydration issues with UApp
</script>