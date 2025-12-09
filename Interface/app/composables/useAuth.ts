export interface User {
  email: string
  name: string
  profilePicture: string
}

export const useAuth = () => {
  const user = useState<User | null>('auth-user', () => null)
  const isAuthenticated = computed(() => !!user.value)

  const login = async (email: string, password: string) => {
    try {
      const response = await $fetch<{ success: boolean; user: User }>('/api/auth/login', {
        method: 'POST',
        body: { email, password }
      })

      if (response.success) {
        user.value = response.user
        // Store in localStorage for persistence
        if (process.client) {
          localStorage.setItem('auth-user', JSON.stringify(response.user))
        }
        return { success: true, error: null }
      }
    } catch (error: any) {
      return { 
        success: false, 
        error: error?.data?.statusMessage || 'Invalid email or password' 
      }
    }
    return { success: false, error: 'Unknown error' }
  }

  const logout = () => {
    user.value = null
    if (process.client) {
      localStorage.removeItem('auth-user')
    }
  }

  const initAuth = () => {
    // Check localStorage on mount
    if (process.client) {
      const storedUser = localStorage.getItem('auth-user')
      if (storedUser) {
        try {
          user.value = JSON.parse(storedUser)
        } catch {
          localStorage.removeItem('auth-user')
        }
      }
    }
  }

  return {
    user,
    isAuthenticated,
    login,
    logout,
    initAuth
  }
}
