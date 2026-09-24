// 租房 Agent API：会话、长期偏好、流式回复、候选清单与对比。
import api from './api'
import type {
  AgentHistoryResponse,
  AgentMemory,
  AgentMessageRequest,
  AgentMessageResponse,
  AgentSession,
  AgentSessionListResponse,
  AgentSessionSummary,
  AgentSearchWorkspace,
  AgentSearchWorkspaceResponse,
  AgentStreamMeta,
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

function apiUrl(path: string): string {
  const base = String(api.defaults.baseURL || '').replace(/\/$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

export const agentService = {
  /** 新建 Agent 会话；推荐与候选清单仍以 UnitType 为实体。 */
  createSession(): Promise<AgentSession> {
    return api.post<AgentSession>('/agent/sessions').then((response) => response.data)
  },

  /** 获取当前用户的历史 Agent 会话。 */
  listSessions(limit = 50, offset = 0): Promise<AgentSessionSummary[]> {
    return api
      .get<AgentSessionListResponse>('/agent/sessions', { params: { limit, offset } })
      .then((response) => response.data.items || [])
  },

  /** 按时间正序回放会话消息。 */
  getSessionMessages(
    sessionId: number,
    limit = 100,
    beforeId?: number,
  ): Promise<AgentHistoryResponse> {
    return api
      .get<AgentHistoryResponse>(`/agent/sessions/${sessionId}/messages`, {
        params: { limit, ...(beforeId ? { before_id: beforeId } : {}) },
      })
      .then((response) => response.data)
  },

  saveSearchWorkspace(
    sessionId: number,
    workspace: AgentSearchWorkspace,
  ): Promise<AgentSearchWorkspaceResponse> {
    return api
      .put<AgentSearchWorkspaceResponse>(
        `/agent/sessions/${sessionId}/search-workspace`,
        workspace,
      )
      .then((response) => response.data)
  },

  getSearchWorkspace(searchId: string): Promise<AgentSearchWorkspaceResponse> {
    return api
      .get<AgentSearchWorkspaceResponse>(`/agent/search-workspaces/${encodeURIComponent(searchId)}`)
      .then((response) => response.data)
  },

  async findSearchWorkspace(searchId: string): Promise<AgentSearchWorkspaceResponse | null> {
    try {
      return await this.getSearchWorkspace(searchId)
    } catch (error: unknown) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 404) return null
      throw error
    }
  },

  claimGuestSessions(guestToken: string): Promise<{ claimed_sessions: number }> {
    return api
      .post<{ claimed_sessions: number }>('/agent/claim-guest-sessions', {
        guest_token: guestToken,
      })
      .then((response) => response.data)
  },

  /** 获取跨会话长期偏好。 */
  getMemory(): Promise<AgentMemory> {
    return api.get<AgentMemory>('/agent/memory').then((response) => response.data)
  },

  /** 保存明确偏好；默认只覆盖本次提交的字段。 */
  saveMemory(preferences: AgentMemory['preferences'], replace = false): Promise<AgentMemory> {
    return api
      .put<AgentMemory>('/agent/memory', { preferences, replace })
      .then((response) => response.data)
  },

  clearMemory(): Promise<void> {
    return api.delete('/agent/memory').then(() => undefined)
  },

  getFaqs(): Promise<FaqChip[]> {
    return api.get<FaqChip[]>('/agent/faqs').then((response) => response.data)
  },

  /** 非流式消息接口，供不支持 SSE 的调用方使用。 */
  sendMessage(sessionId: number, body: AgentMessageRequest): Promise<AgentMessageResponse> {
    return api
      .post<AgentMessageResponse>(`/agent/sessions/${sessionId}/messages`, body, { timeout: 60000 })
      .then((response) => response.data)
  },

  /**
   * SSE 流式发送。
   *
   * 解析完整 SSE event block，而不是逐行假设一个 JSON，避免代理分块、CRLF
   * 或多行 data 导致丢 token。signal 用于切换会话/离开页面时取消旧请求。
   */
  async sendMessageStream(
    sessionId: number,
    body: AgentMessageRequest,
    handlers: AgentStreamHandlers,
    signal?: AbortSignal,
  ): Promise<void> {
    const token = localStorage.getItem('access_token') || localStorage.getItem('guest_token') || ''
    const response = await fetch(apiUrl(`/agent/sessions/${sessionId}/messages/stream`), {
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
        const payload = await response.json() as { detail?: unknown; error?: { message?: unknown } }
        if (typeof payload.detail === 'string') detail = payload.detail
        else if (typeof payload.error?.message === 'string') detail = payload.error.message
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

    const consumeBlock = (block: string): void => {
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

      let event: { token?: unknown; meta?: unknown; error?: unknown }
      try {
        event = JSON.parse(data) as { token?: unknown; meta?: unknown; error?: unknown }
      } catch {
        throw new Error('流式响应格式错误')
      }

      if (typeof event.token === 'string' && event.token.length > 0) {
        handlers.onToken?.(event.token)
      }
      if (event.meta && typeof event.meta === 'object') {
        handlers.onMeta?.(event.meta as AgentStreamMeta)
      }
      if (typeof event.error === 'string' && event.error) {
        handlers.onError?.(event.error)
        throw new Error(event.error)
      }
    }

    const consumeBufferedBlocks = (): void => {
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
      if (!receivedDone && !signal?.aborted) {
        throw new Error('流式连接在完成前中断')
      }
    } finally {
      await reader.cancel().catch(() => undefined)
      reader.releaseLock()
    }
  },

  /** 请求在结构化工作的安全边界停止当前流式轮次。 */
  stopMessageStream(
    sessionId: number,
    requestId: string,
  ): Promise<{ outcome: 'rolled_back' | 'pending' | 'completed' }> {
    return api
      .post(`/agent/sessions/${sessionId}/messages/${encodeURIComponent(requestId)}/stop`)
      .then((response) => response.data)
  },

  getCart(): Promise<Cart> {
    return api.get<Cart>('/agent/cart').then((response) => response.data)
  },

  /** propertyId 必须是 UnitType ID。 */
  addCartItem(propertyId: number, reason?: string): Promise<CartItem> {
    return api
      .post<CartItem>('/agent/cart/items', { property_id: propertyId, reason: reason ?? null })
      .then((response) => response.data)
  },

  removeCartItem(propertyId: number): Promise<void> {
    return api.delete(`/agent/cart/items/${propertyId}`).then(() => undefined)
  },

  compareCart(
    propertyIds?: number[],
    priority?: ComparePriority,
    poiPrefKeys?: string[],
  ): Promise<CompareResponse> {
    const body: Record<string, unknown> = {}
    if (propertyIds?.length) body.property_ids = propertyIds
    if (priority) body.priority = priority
    if (poiPrefKeys?.length) body.poi_pref_keys = poiPrefKeys
    return api
      .post<CompareResponse>('/agent/cart/compare', body, { timeout: 60000 })
      .then((response) => response.data)
  },
}
