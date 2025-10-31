export function useModels() {
  const models = [
    'gpt-5-nano',
  ]

  const model = useCookie<string>('model', { default: () => 'gpt-5-nano' })

  return {
    models,
    model
  }
}
