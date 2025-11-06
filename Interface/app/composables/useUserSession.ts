export const useUserSession = () => {
  const loggedIn = ref(false)
  
  const openInPopup = (url: string) => {
    console.log('Auth popup not implemented:', url)
  }
  
  return {
    loggedIn,
    openInPopup
  }
}
