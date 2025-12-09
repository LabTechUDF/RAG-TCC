export function useModels() {
  const models = [
    { name: 'GPT-5', value: 'gpt-5' },
  ]

  const model = useCookie<string>('model', { default: () => 'gpt-5' })

  return {
    models,
    model
  }
}
