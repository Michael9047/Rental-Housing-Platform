import api from './api'
import type { RegisterRequest, LoginRequest, TokenResponse } from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  register(data: RegisterRequest): Promise<User> {
    return api.post('/auth/register', data).then((r) => r.data)
  },

  login(data: LoginRequest): Promise<TokenResponse> {
    // Use URLSearchParams for OAuth2 password flow compatibility
    const formData = new URLSearchParams()
    formData.append('username', data.username_or_email || data.username || data.email || '')
    formData.append('password', data.password)
    return api
      .post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      .then((r) => r.data)
  },

  getMe(): Promise<User> {
    return api.get('/auth/me').then((r) => r.data)
  },
}
