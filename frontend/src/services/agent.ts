// 租房推荐 Agent API 服务
import api from './api'
import type {
  AgentMessageRequest,
  AgentMessageResponse,
  AgentSession,
  Cart,
  CartItem,
  ComparePriority,
  CompareResponse,
  FaqChip,
} from '@/types/agent'

export const agentService = {
  /** 创建 Agent 会话（返回 session_id 和 cart_id） */
  createSession(): Promise<AgentSession> {
    return api.post('/agent/sessions').then((r) => r.data)
  },

  /** FAQ 快捷入口 chips */
  getFaqs(): Promise<FaqChip[]> {
    return api.get('/agent/faqs').then((r) => r.data)
  },

  /** 发送用户消息（筛选条件 + 自然语言），返回回复和推荐房源 */
  sendMessage(sessionId: number, body: AgentMessageRequest): Promise<AgentMessageResponse> {
    // Agent 推荐涉及 LLM 调用，超时放宽
    return api
      .post(`/agent/sessions/${sessionId}/messages`, body, { timeout: 60000 })
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
