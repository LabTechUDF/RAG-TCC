// Mock user session composable
// Em produção, isso deveria usar autenticação real
export function useUserSession() {
  const loggedIn = ref(false)
  const user = ref(null)
  
  function openInPopup() {
    // Mock para login
    console.log('Login would open here')
  }
  
  function clear() {
    loggedIn.value = false
    user.value = null
  }
  
  return {
    loggedIn,
    user,
    openInPopup,
    clear
  }
}
