// Matches backend: app/models/user.py
export type UserRole = 'tenant' | 'landlord' | 'admin'
export type UserStatus = 'active' | 'disabled' | 'deleted'

// Matches backend: app/schemas/user.py UserRead
export interface User {
  id: number
  username: string
  phone: string | null
  wechat_openid: string | null
  email: string | null
  role: UserRole
  status: UserStatus
  created_at: string
  updated_at: string
}

// Matches backend: app/schemas/user.py UserProfileUpdate
export interface UserProfileUpdate {
  username?: string
  phone?: string
  email?: string
}
