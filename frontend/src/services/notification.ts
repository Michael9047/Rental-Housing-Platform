import api from './api'
import type { Notification, UnreadCount } from '@/types/booking'

export const notificationService = {
  list(params: { page?: number; page_size?: number } = {}): Promise<{ items: Notification[]; total: number; page: number; page_size: number }> {
    return api.get('/notifications', { params }).then((r) => r.data)
  },

  markRead(id: number): Promise<Notification> {
    return api.patch(`/notifications/${id}/read`).then((r) => r.data)
  },

  markAllRead(): Promise<void> {
    return api.patch('/notifications/read-all')
  },

  getUnreadCount(): Promise<UnreadCount> {
    return api.get('/notifications/unread-count').then((r) => r.data)
  },
}
