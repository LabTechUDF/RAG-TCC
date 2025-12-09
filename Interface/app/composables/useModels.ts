export function useModels() {
  const models = [
    { name: 'GPT-4', value: 'gpt-4' },
    { name: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' },
  ]

  const model = useCookie<string>('model', { default: () => 'gpt-4' })

  return {
    models,
    model
  }
}
