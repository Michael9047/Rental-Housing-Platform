import api from './api'
import type { User, UserProfileUpdate } from '@/types/user'

export const userService = {
  getMyProfile(): Promise<User> {
    return api.get('/users/me').then((r) => r.data)
  },

  updateMyProfile(data: UserProfileUpdate): Promise<User> {
    return api.patch('/users/me', data).then((r) => r.data)
  },

  list(params?: { skip?: number; limit?: number }): Promise<User[]> {
    return api.get('/users', { params }).then((r) => r.data)
  },
}
