export default defineNuxtPlugin((nuxtApp) => {
  const logger = useClientLogger()

  // Captura erros do Vue
  nuxtApp.hook('vue:error', (error, instance, info) => {
    logger.error('Vue Error', 'ErrorHandler', {
      componentName: instance?.$options?.name,
      info
    }, error)
  })

  // Captura erros globais do navegador
  if (process.client) {
    window.addEventListener('error', (event) => {
      logger.error('Global Error', 'ErrorHandler', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno
      }, event.error)
    })

    window.addEventListener('unhandledrejection', (event) => {
      logger.error('Unhandled Promise Rejection', 'ErrorHandler', {
        reason: event.reason
      }, event.reason)
    })
  }

  logger.info('Error handler plugin initialized', 'ErrorHandler')
})
