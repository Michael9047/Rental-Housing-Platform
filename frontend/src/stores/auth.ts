import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService } from '@/services/auth'
import type { User } from '@/types/user'
import type { LoginRequest, RegisterRequest } from '@/types/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  const isLandlord = computed(() => user.value?.role === 'landlord' || user.value?.role === 'admin')
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isMaintenance = computed(() => user.value?.role === 'maintenance_worker')
  const isBdManager = computed(() => user.value?.role === 'bd_manager')

  function setAuth(newToken: string, newUser: User) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('access_token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
  }

  function loadFromStorage() {
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')
    if (storedToken && storedUser) {
      token.value = storedToken
      try {
        user.value = JSON.parse(storedUser)
      } catch {
        clearAuth()
      }
    }
  }

  async function register(data: RegisterRequest): Promise<User> {
    loading.value = true
    try {
      const newUser = await authService.register(data)
      return newUser
    } finally {
      loading.value = false
    }
  }

  async function login(data: LoginRequest) {
    loading.value = true
    try {
      const tokenResp = await authService.login(data)
      setAuth(tokenResp.access_token, { } as User)
      // Fetch full user profile
      const currentUser = await authService.getMe()
      setAuth(tokenResp.access_token, currentUser)
      return currentUser
    } finally {
      loading.value = false
    }
  }

  async function fetchCurrentUser() {
    try {
      const currentUser = await authService.getMe()
      user.value = currentUser
      localStorage.setItem('user', JSON.stringify(currentUser))
    } catch {
      clearAuth()
    }
  }

  function logout() {
    clearAuth()
    router.push('/login')
  }

  // Initialize from storage on store creation
  loadFromStorage()

  return {
    user,
    token,
    loading,
    isLoggedIn,
    isLandlord,
    isAdmin,
    isMaintenance,
    isBdManager,
    register,
    login,
    logout,
    fetchCurrentUser,
    loadFromStorage,
    setAuth,
  }
})
