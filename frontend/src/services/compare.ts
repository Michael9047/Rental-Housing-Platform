/** 对比 Agent API 服务 */
import api from './api'
import type {
  CompareSessionCreate,
  CompareSessionResponse,
  CompareMessageRequest,
  CompareMessageResponse,
} from '@/types/compare'

export const compareService = {
  /** 创建对比会话并执行首次分析 */
  createSession(body: CompareSessionCreate): Promise<CompareSessionResponse> {
    return api.post('/compare/sessions', body, { timeout: 90_000 }).then(r => r.data)
  },

  /** 发送追问 */
  sendMessage(sessionId: number, body: CompareMessageRequest): Promise<CompareMessageResponse> {
    return api.post(`/compare/sessions/${sessionId}/messages`, body, { timeout: 90_000 }).then(r => r.data)
  },

  /** 获取历史会话 */
  getSession(sessionId: number): Promise<CompareSessionResponse> {
    return api.get(`/compare/sessions/${sessionId}`).then(r => r.data)
  },
}
