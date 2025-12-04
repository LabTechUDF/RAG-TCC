export function useRagMode() {
  // Estado persistente do modo RAG (usa cookie para manter entre reloads)
  // RAG é o modo padrão (true)
  const ragEnabled = useCookie<boolean>('rag-enabled', { 
    default: () => true 
  })

  // Toggle para ligar/desligar RAG
  const toggleRag = () => {
    ragEnabled.value = !ragEnabled.value
  }

  // Setter explícito
  const setRagEnabled = (enabled: boolean) => {
    ragEnabled.value = enabled
  }

  return {
    ragEnabled,
    toggleRag,
    setRagEnabled
  }
}
