// Agent SSE 客户端的逐块读取测试。
import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentService } from '@/services/agent'

describe('agentService.sendMessageStream', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('连接结束前就把已到达的 token 交给页面', async () => {
    const encoder = new TextEncoder()
    let streamController: ReadableStreamDefaultController<Uint8Array> | undefined
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream; charset=utf-8' },
    })))

    const tokens: string[] = []
    let completed = false
    const request = agentService.sendMessageStream(
      1,
      { message: '测试真流式' },
      { onToken: (token) => tokens.push(token) },
    ).then(() => {
      completed = true
    })

    streamController!.enqueue(encoder.encode('data: {"token":"你"}\n\n'))
    await vi.waitFor(() => expect(tokens).toEqual(['你']))
    expect(completed).toBe(false)

    streamController!.enqueue(encoder.encode('data: {"token":"好"}\n\ndata: [DONE]\n\n'))
    streamController!.close()
    await request

    expect(tokens).toEqual(['你', '好'])
    expect(completed).toBe(true)
  })
})
