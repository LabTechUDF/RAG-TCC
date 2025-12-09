<script setup lang="ts">
const logger = useClientLogger()
const colorMode = useColorMode()
const { initAuth } = useAuth()

// Initialize auth on app mount
onMounted(() => {
  initAuth()
})

logger.info('Application started', 'App')

logger.info('Application started', 'App')

const color = computed(() => colorMode.value === 'dark' ? '#1b1718' : 'white')

// Log color mode changes
watch(() => colorMode.value, (newMode) => {
  logger.debug('Color mode changed', 'App', { mode: newMode })
})

useHead({
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: 'en'
  }
})

const title = 'Nuxt AI Chatbot template'
const description = 'A full-featured, hackable Nuxt AI chatbot template made with Nuxt UI.'

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description,
  ogImage: 'https://ui.nuxt.com/assets/templates/nuxt/chat-light.png',
  twitterImage: 'https://ui.nuxt.com/assets/templates/nuxt/chat-light.png',
  twitterCard: 'summary_large_image'
})

// Log navigation changes
const router = useRouter()
router.afterEach((to, from) => {
  logger.info('Navigation', 'App', { from: from.path, to: to.path })
})
</script>

<template>
  <AppWrapper>
    <NuxtLoadingIndicator color="var(--ui-primary)" />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>

    <AuthModal />
  </AppWrapper>
</template>
