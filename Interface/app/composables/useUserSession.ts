export const useUserSession = () => {
  const loggedIn = ref(false)
  const user = ref(null)

  const openInPopup = (url: string) => {
    const width = 600
    const height = 700
    const left = window.screen.width / 2 - width / 2
    const top = window.screen.height / 2 - height / 2
    
    return window.open(
      url,
      'oauth',
      `width=${width},height=${height},left=${left},top=${top}`
    )
  }

  const clear = () => {
    user.value = null
    loggedIn.value = false
  }

  return {
    loggedIn,
    user,
    openInPopup,
    clear
  }
}
