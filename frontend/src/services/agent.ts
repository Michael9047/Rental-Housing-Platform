// 租房推荐 Agent API 服务
import api from './api'
import type {
  AgentMessageRequest,
  AgentMessageResponse,
  AgentRecommendation,
  AgentSession,
  Cart,
  CartItem,
  ComparePriority,
  CompareResponse,
  FaqChip,
} from '@/types/agent'

/** SSE 流式消息的元数据事件 */
export interface AgentStreamMeta {
  intent?: string
  recommendations?: Array<{ property_id: number; match_reason: string }>
  top_picks?: Array<{ property_id: number; match_reason: string }>
  quick_replies?: string[]
  cart_changed?: boolean
  ai_available?: boolean
}

/** SSE 流式回调 */
export interface AgentStreamCallbacks {
  onToken: (token: string) => void
  onMeta: (meta: AgentStreamMeta) => void
}

export const agentService = {
  /** 创建 Agent 会话（返回 session_id 和 cart_id） */
  createSession(): Promise<AgentSession> {
    return api.post('/agent/sessions').then((r) => r.data)
  },

  /** FAQ 快捷入口 chips */
  getFaqs(): Promise<FaqChip[]> {
    return api.get('/agent/faqs').then((r) => r.data)
  },

  /** 发送用户消息（非流式），返回完整回复和推荐房源 */
  sendMessage(sessionId: number, body: AgentMessageRequest): Promise<AgentMessageResponse> {
    const payload: Record<string, unknown> = {
      message: body.message,
      filters: body.filters,
    }
    if (body.compare_property_ids?.length) {
      payload.compare_property_ids = body.compare_property_ids
    }
    return api
      .post(`/agent/sessions/${sessionId}/messages`, payload, { timeout: 60000 })
      .then((r) => r.data)
  },

  /**
   * 流式发送消息 —— SSE 逐 token 返回。
   * 通过 onToken/onMeta 回调实时更新 UI，返回 Promise 在流结束时 resolve。
   */
  async sendMessageStream(
    sessionId: number,
    body: AgentMessageRequest,
    callbacks: AgentStreamCallbacks,
  ): Promise<void> {
    const baseUrl = api.defaults.baseURL || ''
    const token = api.defaults.headers.common?.['Authorization'] as string | undefined

    const payload: Record<string, unknown> = {
      message: body.message,
      filters: body.filters,
    }
    if (body.compare_property_ids?.length) {
      payload.compare_property_ids = body.compare_property_ids
    }

    const resp = await fetch(`${baseUrl}/agent/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: token } : {}),
      },
      body: JSON.stringify(payload),
    })

    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}))
      throw new Error((errBody as any).detail || `HTTP ${resp.status}`)
    }

    const reader = resp.body?.getReader()
    if (!reader) throw new Error('浏览器不支持流式读取')

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6)
          if (raw === '[DONE]') continue
          try {
            const parsed = JSON.parse(raw)
            if (parsed.token) {
              callbacks.onToken(parsed.token as string)
            }
            if (parsed.meta) {
              callbacks.onMeta(parsed.meta as AgentStreamMeta)
            }
            if (parsed.error) {
              throw new Error(parsed.error as string)
            }
          } catch (e) {
            // JSON 解析失败则忽略该行；如果是我们主动抛的 error 则继续抛
            if (e instanceof Error && e.message !== 'JSON 解析失败') throw e
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
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
