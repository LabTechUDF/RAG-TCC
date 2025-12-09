// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-12-08',
  
  future: {
    compatibilityVersion: 4
  },

  modules: [
    '@nuxt/ui'
  ],

  devtools: {
    enabled: false
  },

  vue: {
    compilerOptions: {
      isCustomElement: (tag: string) => false
    }
  },

  vite: {
    build: {
      sourcemap: false
    }
  },

  css: [
    '~/assets/css/main.css'
  ],

  runtimeConfig: {
    openaiApiKey: process.env.OPENAI_API_KEY,
    openaiProjectId: process.env.OPENAI_PROJECT_ID,
    public: {
      dbvectorApiUrl: process.env.NUXT_PUBLIC_DBVECTOR_API_URL || 'http://localhost:8000'
    }
  }
})
