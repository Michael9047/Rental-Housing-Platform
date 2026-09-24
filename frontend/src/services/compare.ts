/** 对比 Agent API 服务 */
import api from './api'
import type {
  CompareSessionCreate,
  CompareSessionResponse,
  CompareMessageRequest,
  CompareMessageResponse,
} from '@/types/compare'

export interface CompareStreamMeta {
  event: 'status' | 'result'
  status?: string
  message?: string
  session?: CompareSessionResponse
}

export interface CompareStreamHandlers {
  onToken?: (token: string) => void
  onMeta?: (meta: CompareStreamMeta) => void
  onError?: (message: string) => void
}

function apiUrl(path: string): string {
  const base = String(api.defaults.baseURL || '').replace(/\/$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

async function consumeCompareStream(
  response: Response,
  handlers: CompareStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`
    try {
      const payload = await response.json() as { detail?: unknown }
      if (typeof payload.detail === 'string') detail = payload.detail
    } catch {
      // 非 JSON 错误响应沿用状态码提示。
    }
    throw new Error(detail)
  }
  if (!(response.headers.get('content-type') || '').toLowerCase().includes('text/event-stream')) {
    throw new Error('服务器未返回流式对比结果')
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
      throw new Error('流式对比响应格式错误')
    }
    if (typeof event.token === 'string' && event.token) handlers.onToken?.(event.token)
    if (event.meta && typeof event.meta === 'object') {
      handlers.onMeta?.(event.meta as CompareStreamMeta)
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
    if (!receivedDone && !signal?.aborted) throw new Error('流式对比连接在完成前中断')
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

export const compareService = {
  /** 创建对比会话并执行首次分析 */
  createSession(body: CompareSessionCreate): Promise<CompareSessionResponse> {
    return api.post('/compare/sessions', body, { timeout: 90_000 }).then(r => r.data)
  },

  /** 创建会话并逐个消费模型原始 token。 */
  async createSessionStream(
    body: CompareSessionCreate,
    handlers: CompareStreamHandlers,
    signal?: AbortSignal,
  ): Promise<void> {
    const token = localStorage.getItem('access_token') || ''
    const response = await fetch(apiUrl('/compare/sessions/stream'), {
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
    await consumeCompareStream(response, handlers, signal)
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
