// 租房推荐 Agent API 服务
import api from './api'
import type {
  AgentHistoryMessage,
  AgentMessageRequest,
  AgentMessageResponse,
  AgentSession,
  AgentSessionSummary,
  Cart,
  CartItem,
  ComparePriority,
  CompareResponse,
  FaqChip,
  MessageFeedback,
} from '@/types/agent'

export const agentService = {
  /** 创建 Agent 会话（返回 session_id 和 cart_id） */
  createSession(): Promise<AgentSession> {
    return api.post('/agent/sessions').then((r) => r.data)
  },

  /**
   * AI 管家历史会话。
   * 当前后端的通用聊天接口已经提供会话列表，前端在这里做兼容映射。
   */
  listSessions(): Promise<AgentSessionSummary[]> {
    return api.get('/chat/sessions').then((r) =>
      (r.data as AgentSessionSummary[]).map((session) => ({
        id: session.id,
        title: session.title,
        created_at: session.created_at,
        updated_at: session.updated_at,
      })),
    )
  },

  /** 回放历史消息；推荐详情无法从旧 metadata 还原时保留纯文本 */
  getSessionMessages(sessionId: number): Promise<AgentHistoryMessage[]> {
    return api.get(`/chat/sessions/${sessionId}/messages`).then((r) =>
      (r.data as Array<Record<string, any>>).map((message) => {
        const metadata = message.metadata || message.metadata_ || {}
        return {
          id: message.id ?? null,
          role: message.role === 'user' ? 'user' : 'assistant',
          content: String(message.content || ''),
          recommendations: [],
          elicit: metadata.elicit || null,
          feedback: metadata.feedback || null,
          intent: metadata.intent || null,
          created_at: String(message.created_at || ''),
        }
      }),
    )
  },

  /** 删除历史会话 */
  deleteSession(sessionId: number): Promise<void> {
    return api.delete(`/chat/sessions/${sessionId}`).then(() => undefined)
  },

  /** FAQ 快捷入口 chips */
  getFaqs(): Promise<FaqChip[]> {
    return api.get('/agent/faqs').then((r) => r.data)
  },

  /** 发送用户消息（筛选条件 + 自然语言 + 可选对比房源ID），返回回复和推荐房源 */
  sendMessage(sessionId: number, body: AgentMessageRequest): Promise<AgentMessageResponse> {
    // Agent 推荐涉及 LLM 调用，超时放宽
    const payload: Record<string, unknown> = {
      message: body.message,
      filters: body.filters,
    }
    if (body.compare_property_ids?.length) {
      payload.compare_property_ids = body.compare_property_ids
    }
    if (body.slot_answers) payload.slot_answers = body.slot_answers
    if (body.mode) payload.mode = body.mode
    return api
      .post(`/agent/sessions/${sessionId}/messages`, payload, { timeout: 60000 })
      .then((r) => r.data)
  },

  /** 获取当前用户购物车 */
  getCart(): Promise<Cart> {
    return api.get('/agent/cart').then((r) => r.data)
  },

  /** 添加房源到购物车 */
  addCartItem(propertyId: number, reason?: string): Promise<CartItem> {
    return api
      .post('/agent/cart/items', { property_id: propertyId, reason: reason ?? null })
      .then((r) => r.data)
  },

  /** 从购物车移除房源 */
  removeCartItem(propertyId: number): Promise<void> {
    return api.delete(`/agent/cart/items/${propertyId}`).then(() => undefined)
  },

  /**
   * 当前后端尚未提供消息反馈接口，先保持视频中的前端交互状态；
   * 接口补齐后只需把这里替换成 PATCH 请求。
   */
  setMessageFeedback(
    messageId: number,
    feedback: MessageFeedback,
  ): Promise<{ message_id: number; feedback: MessageFeedback }> {
    return Promise.resolve({ message_id: messageId, feedback })
  },

  /**
   * 对比房源。
   * - 传 propertyIds：只对比这些房源（来自推荐横条或购物车勾选，不要求已加购）
   * - 不传：对比整个购物车
   * - priority：加权评分优先级（balanced/budget/commute/space）
   */
  compareCart(propertyIds?: number[], priority?: ComparePriority): Promise<CompareResponse> {
    const body: Record<string, unknown> = {}
    if (propertyIds && propertyIds.length) body.property_ids = propertyIds
    if (priority) body.priority = priority
    return api.post('/agent/cart/compare', body, { timeout: 60000 }).then((r) => r.data)
  },
}
