export function useModels() {
  const models = [
    'gpt-4o-mini',
    'gpt-4o',
    'gpt-4-turbo',
    'gpt-3.5-turbo'
  ]

  const model = useCookie<string>('model', { default: () => 'gpt-4o-mini' })

  return {
    models,
    model
  }
}
