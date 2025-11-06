export default defineNuxtConfig({
  modules: ['@nuxt/ui'],
  
  css: ['~/assets/css/main.css'],
  
  devtools: { enabled: true },
  
  compatibilityDate: '2024-11-01',
  
  runtimeConfig: {
    // Private keys (server-side only)
    sessionPassword: process.env.NUXT_SESSION_PASSWORD,
    databaseUrl: process.env.DATABASE_URL,
    
    // Public keys (exposed to client)
    public: {
      openaiApiKey: process.env.OPENAI_API_KEY,
      openaiProjectId: process.env.OPENAI_PROJECT_ID
    }
  }
})
