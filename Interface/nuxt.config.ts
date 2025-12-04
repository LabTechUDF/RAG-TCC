// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-12-03',
  
  modules: ['@nuxt/ui'],
  
  future: {
    compatibilityVersion: 4
  },
  
  // Importa o CSS global com Tailwind + Nuxt UI
  css: ['~/assets/css/main.css'],
  
  runtimeConfig: {
    public: {
      openaiApiKey: process.env.NUXT_PUBLIC_OPENAI_API_KEY || '',
      openaiProjectId: process.env.NUXT_PUBLIC_OPENAI_PROJECT_ID || '',
      ragApiUrl: process.env.NUXT_PUBLIC_RAG_API_URL || 'http://localhost:8000'
    }
  },
  
  nitro: {
    preset: 'node-server',
    routeRules: {
      '/api/**': {
        cors: true,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
      }
    }
  },
  
  devtools: { enabled: true },
  
  vite: {
    optimizeDeps: {
      include: ['date-fns', '@ai-sdk/vue', '@vueuse/core']
    }
  }
})
