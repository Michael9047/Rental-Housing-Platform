import api from './api'
import type { RegisterRequest, LoginRequest, TokenResponse } from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  register(data: RegisterRequest): Promise<User> {
    return api.post('/auth/register', data).then((r) => r.data)
  },

  login(data: LoginRequest): Promise<TokenResponse> {
    return api
      .post('/auth/login', {
        username_or_email: data.username_or_email || data.username || data.email || '',
        password: data.password,
      })
      .then((r) => r.data)
  },

  getMe(): Promise<User> {
    return api.get('/auth/me').then((r) => r.data)
  },
}