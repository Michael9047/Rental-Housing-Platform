// Matches backend: app/schemas/auth.py RegisterRequest / LoginRequest / TokenResponse
import type { UserRole } from './user'

export interface RegisterRequest {
  username: string
  password: string
  phone?: string
  email?: string
  role?: UserRole
}

export interface LoginRequest {
  username_or_email?: string
  username?: string
  email?: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}
