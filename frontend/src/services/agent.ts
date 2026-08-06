// 租房推荐 Agent API 服务
import api from './api'
import type {
  AgentHistoryResponse,
  AgentMemory,
  AgentMessageRequest,
  AgentMessageResponse,
  AgentSessionListResponse,
  AgentSessionSummary,
  AgentStreamMeta,
  AgentSession,
  Cart,
  CartItem,
  ComparePriority,
  CompareResponse,
  FaqChip,
} from '@/types/agent'

export interface AgentStreamHandlers {
  onToken?: (token: string) => void
  onMeta?: (meta: AgentStreamMeta) => void
  onError?: (message: string) => void
}

export const agentService = {
  /** 创建 Agent 会话（返回 session_id 和 cart_id） */
  createSession(): Promise<AgentSession> {
    return api.post('/agent/sessions').then((r) => r.data)
  },

  /** 获取当前用户的 Agent 对话记录。 */
  listSessions(limit = 50, offset = 0): Promise<AgentSessionSummary[]> {
    return api
      .get<AgentSessionListResponse>('/agent/sessions', { params: { limit, offset } })
      .then((r) => r.data.items || [])
  },

  /** 回放指定 Agent 会话的历史消息。 */
  getSessionMessages(sessionId: number, limit = 100): Promise<AgentHistoryResponse> {
    return api
      .get<AgentHistoryResponse>(`/agent/sessions/${sessionId}/messages`, { params: { limit } })
      .then((r) => r.data)
  },

  /** 获取跨会话长期记忆。 */
  getMemory(): Promise<AgentMemory> {
    return api.get<AgentMemory>('/agent/memory').then((r) => r.data)
  },

  /** 将当前明确偏好保存为跨会话长期记忆。 */
  saveMemory(preferences: AgentMemory['preferences'], replace = false): Promise<AgentMemory> {
    return api
      .put<AgentMemory>('/agent/memory', { preferences, replace })
      .then((r) => r.data)
  },

  /** 清空跨会话长期记忆。 */
  clearMemory(): Promise<void> {
    return api.delete('/agent/memory').then(() => undefined)
  },

  /** FAQ 快捷入口 chips */
  getFaqs(): Promise<FaqChip[]> {
    return api.get('/agent/faqs').then((r) => r.data)
  },

  /** 发送用户消息（筛选条件 + 自然语言 + 可选对比房源ID），返回回复和推荐房源 */
  sendMessage(
    sessionId: number,
    body: AgentMessageRequest,
    signal?: AbortSignal,
  ): Promise<AgentMessageResponse> {
    // Agent 推荐涉及 LLM 调用，超时放宽
    const payload: Record<string, unknown> = {
      message: body.message,
      filters: body.filters,
      context_filters: body.context_filters,
    }
    if (body.compare_property_ids?.length) {
      payload.compare_property_ids = body.compare_property_ids
    }
    if (body.mode) payload.mode = body.mode
    return api
      .post(`/agent/sessions/${sessionId}/messages`, payload, {
        timeout: 60000,
        ...(signal ? { signal } : {}),
      })
      .then((r) => r.data)
  },

  /** SSE 流式发送；token 逐段更新气泡，meta 更新卡片、状态、来源和引导项。 */
  async sendMessageStream(
    sessionId: number,
    body: AgentMessageRequest,
    handlers: AgentStreamHandlers,
    signal?: AbortSignal,
  ): Promise<void> {
    const token = localStorage.getItem('access_token') || ''
    const response = await fetch(`/api/v1/agent/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      cache: 'no-store',
      credentials: 'same-origin',
      signal,
    })
    if (!response.ok) {
      let detail = `请求失败（${response.status}）`
      try {
        const payload = await response.json()
        if (typeof payload?.detail === 'string') detail = payload.detail
      } catch {
        // 非 JSON 错误响应沿用状态码提示。
      }
      throw new Error(detail)
    }
    const contentType = response.headers.get('content-type') || ''
    if (!contentType.toLowerCase().includes('text/event-stream')) {
      throw new Error('服务器未返回流式响应')
    }
    if (!response.body) throw new Error('浏览器未返回可读流')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let receivedDone = false

    const consumeBlock = (block: string) => {
      const data = block
        .split(/\r?\n/)
        .map((line) => line.replace(/^\uFEFF/, ''))
        .filter((line) => line === 'data' || line.startsWith('data:'))
        .map((line) => (line === 'data' ? '' : line.slice(5).replace(/^ /, '')))
        .join('\n')
      if (!data) return
      if (data === '[DONE]') {
        receivedDone = true
        return
      }
      let event: {
        token?: string
        meta?: AgentStreamMeta
        error?: string
      }
      try {
        event = JSON.parse(data)
      } catch {
        throw new Error('流式响应格式错误')
      }
      if (typeof event.token === 'string' && event.token.length > 0) {
        handlers.onToken?.(event.token)
      }
      if (event.meta && typeof event.meta === 'object') {
        handlers.onMeta?.(event.meta)
      }
      if (event.error) {
        handlers.onError?.(event.error)
        throw new Error(event.error)
      }
    }

    const consumeBufferedBlocks = () => {
      let boundary = buffer.search(/\r?\n\r?\n/)
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        const separator = buffer.slice(boundary).match(/^\r?\n\r?\n/)?.[0] || '\n\n'
        buffer = buffer.slice(boundary + separator.length)
        consumeBlock(block)
        if (receivedDone) return
        boundary = buffer.search(/\r?\n\r?\n/)
      }
    }

    try {
      while (!receivedDone) {
        const { value, done } = await reader.read()
        if (done) {
          buffer += decoder.decode()
          break
        }
        buffer += decoder.decode(value, { stream: true })
        consumeBufferedBlocks()
      }
      if (!receivedDone && buffer.trim()) consumeBlock(buffer)
      if (signal?.aborted) {
        // 用户主动中止，静默返回
        return
      }
      if (!receivedDone) {
        throw new Error('流式连接在完成前中断')
      }
    } finally {
      await reader.cancel().catch(() => undefined)
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
   * - poiPrefKeys：用户一路选过的周边偏好（transit/supermarket/...），纳入对比展示
   */
  compareCart(
    propertyIds?: number[],
    priority?: ComparePriority,
    poiPrefKeys?: string[],
  ): Promise<CompareResponse> {
    const body: Record<string, unknown> = {}
    if (propertyIds && propertyIds.length) body.property_ids = propertyIds
    if (priority) body.priority = priority
    if (poiPrefKeys && poiPrefKeys.length) body.poi_pref_keys = poiPrefKeys
    return api.post('/agent/cart/compare', body, { timeout: 60000 }).then((r) => r.data)
  },
}
