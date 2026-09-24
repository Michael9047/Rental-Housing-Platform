import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService } from '@/services/auth'
import type { User } from '@/types/user'
import type { LoginRequest, RegisterRequest, PhoneLoginRequest, PhoneRegisterRequest } from '@/types/auth'
import router from '@/router'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value)
  // 管理员使用独立的精简后台，不继承 BM/房东工作台权限。
  const isLandlord = computed(() => user.value?.role === 'landlord')
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isMaintenance = computed(() => user.value?.role === 'maintenance_worker')

  function setAuth(newToken: string, newUser: User) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('access_token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function setRefreshToken(refreshToken?: string | null) {
    if (refreshToken) localStorage.setItem('refresh_token', refreshToken)
  }

  async function finishLogin(newToken: string, refreshToken?: string | null): Promise<User> {
    const guestToken = localStorage.getItem('guest_token')
    setAuth(newToken, {} as User)
    setRefreshToken(refreshToken)
    const currentUser = await authService.getMe()
    setAuth(newToken, currentUser)
    if (guestToken) {
      try {
        await useAgentChatStore().claimGuestSessions(guestToken)
      } catch {
        // 认领失败时保留 guest_token，之后登录或进入 AI 页面可再次尝试。
      }
    }
    return currentUser
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    // AI 历史/长期偏好和候选清单都属于当前账号，身份失效时必须同步隔离。
    useAgentChatStore().reset()
    useCartStore().clear()
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
      return await finishLogin(tokenResp.access_token)
    } finally {
      loading.value = false
    }
  }

  /** 手机号 + 短信验证码登录（已注册用户直接登录，新用户返回 is_new_user） */
  async function phoneLogin(data: PhoneLoginRequest) {
    loading.value = true
    try {
      const resp = await authService.phoneLogin(data)
      if (!resp.is_new_user && resp.access_token) {
        await finishLogin(resp.access_token)
      }
      return resp
    } finally {
      loading.value = false
    }
  }

  /** 新用户手机号注册（验证码验证后设置用户名密码） */
  async function phoneRegister(data: PhoneRegisterRequest) {
    loading.value = true
    try {
      const tokenResp = await authService.phoneRegister(data)
      return await finishLogin(tokenResp.access_token)
    } finally {
      loading.value = false
    }
  }

  async function wechatQrLogin(data: { code: string; state: string }) {
    loading.value = true
    try {
      const tokenResp = await authService.wechatQrLogin(data)
      return await finishLogin(tokenResp.access_token)
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
    register,
    login,
    phoneLogin,
    phoneRegister,
    wechatQrLogin,
    logout,
    fetchCurrentUser,
    loadFromStorage,
    setAuth,
    clearAuth,
  }
})
