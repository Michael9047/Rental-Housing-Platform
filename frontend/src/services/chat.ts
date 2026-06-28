import api from './api'
import type { ChatSession, ChatMessage } from '@/types/chat'

export const chatService = {
  async createSession(title?: string): Promise<ChatSession> {
    const { data } = await api.post('/chat/sessions', { title })
    return data
  },

  async listSessions(): Promise<ChatSession[]> {
    const { data } = await api.get('/chat/sessions')
    return data
  },

  async getMessages(sessionId: number): Promise<ChatMessage[]> {
    const { data } = await api.get(`/chat/sessions/${sessionId}/messages`)
    return data
  },

  async deleteSession(sessionId: number): Promise<void> {
    await api.delete(`/chat/sessions/${sessionId}`)
  },
}
