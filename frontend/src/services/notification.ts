import api from './api'
import type { Notification, UnreadCount } from '@/types/notification'

export const notificationService = {
  list(params?: Record<string, string>): Promise<Notification[]> {
    return api.get('/notifications', { params }).then((r) => r.data)
  },

  markRead(id: number): Promise<Notification> {
    return api.patch(`/notifications/${id}/read`).then((r) => r.data)
  },

  markAllRead(): Promise<{ detail: string; affected: number }> {
    return api.patch('/notifications/read-all').then((r) => r.data)
  },

  getUnreadCount(): Promise<UnreadCount> {
    return api.get('/notifications/unread-count').then((r) => r.data)
  },
}
