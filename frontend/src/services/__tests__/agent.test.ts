import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { agentService } from '@/services/agent'

const encoder = new TextEncoder()

function chunkBytes(text: string, pattern = [1, 2, 7, 3, 11]): Uint8Array[] {
  const bytes = encoder.encode(text)
  const chunks: Uint8Array[] = []
  let offset = 0
  let index = 0
  while (offset < bytes.length) {
    const size = pattern[index % pattern.length]
    chunks.push(bytes.slice(offset, offset + size))
    offset += size
    index += 1
  }
  return chunks
}

function streamResponse(text: string, contentType = 'text/event-stream; charset=utf-8'): Response {
  const chunks = chunkBytes(text)
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk)
      controller.close()
    },
  })

  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': contentType }),
    body,
  } as Response
}

describe('agentService.sendMessageStream', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    localStorage.clear()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses arbitrary byte chunks, CRLF blocks and multiline data fields', async () => {
    localStorage.setItem('access_token', 'agent-token')
    const payload = [
      'data: {"meta":{"event":"status","status":"searching","message":"正在检索符合条件的户型"}}\r\n',
      '\r\n',
      '\uFEFFevent: message\r\n',
      'id: 1\r\n',
      'data: {"token":\r\n',
      'data: "你"}\r\n',
      '\r\n',
      'event: message\r\n',
      'data: {"meta":{"event":"result","quick_replies":["继续"]}}\r\n',
      '\r\n',
      'data: [DONE]\r\n',
      '\r\n',
    ].join('')
    fetchMock.mockResolvedValue(streamResponse(payload))
    const onToken = vi.fn()
    const onMeta = vi.fn()

    await agentService.sendMessageStream(
      12,
      {
        message: '找 Studio',
        context_filters: { city: 'London' },
        clear_fields: ['district'],
        task_mode: 'new',
      },
      { onToken, onMeta },
    )

    expect(onToken).toHaveBeenCalledOnce()
    expect(onToken).toHaveBeenCalledWith('你')
    expect(onMeta).toHaveBeenCalledTimes(2)
    expect(onMeta).toHaveBeenNthCalledWith(1, {
      event: 'status',
      status: 'searching',
      message: '正在检索符合条件的户型',
    })
    expect(onMeta).toHaveBeenNthCalledWith(2, {
      event: 'result',
      quick_replies: ['继续'],
    })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/agent/sessions/12/messages/stream',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Accept: 'text/event-stream',
          Authorization: 'Bearer agent-token',
        }),
        body: JSON.stringify({
          message: '找 Studio',
          context_filters: { city: 'London' },
          clear_fields: ['district'],
          task_mode: 'new',
        }),
      }),
    )
  })

  it('stops at DONE and ignores any trailing event data', async () => {
    fetchMock.mockResolvedValue(streamResponse([
      'data: {"token":"first"}\n\n',
      'data: [DONE]\n\n',
      'data: {"token":"must-not-be-read"}\n\n',
    ].join('')))
    const onToken = vi.fn()

    await agentService.sendMessageStream(8, { message: 'compare' }, { onToken })

    expect(onToken).toHaveBeenCalledTimes(1)
    expect(onToken).toHaveBeenCalledWith('first')
  })

  it('reports an SSE error to the callback and rejects the request', async () => {
    fetchMock.mockResolvedValue(streamResponse([
      'data: {"token":"partial"}\n\n',
      'data: {"error":"模型暂不可用"}\n\n',
    ].join('')))
    const onToken = vi.fn()
    const onError = vi.fn()

    await expect(agentService.sendMessageStream(
      9,
      { message: '继续' },
      { onToken, onError },
    )).rejects.toThrow('模型暂不可用')

    expect(onToken).toHaveBeenCalledWith('partial')
    expect(onError).toHaveBeenCalledOnce()
    expect(onError).toHaveBeenCalledWith('模型暂不可用')
  })

  it('rejects a stream that closes without DONE', async () => {
    fetchMock.mockResolvedValue(streamResponse('data: {"token":"partial"}\n\n'))

    await expect(agentService.sendMessageStream(
      10,
      { message: '继续' },
      {},
    )).rejects.toThrow('流式连接在完成前中断')
  })

  it('uses the backend detail for non-success responses', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ 'content-type': 'application/json' }),
      body: null,
      json: vi.fn().mockResolvedValue({ detail: '会话不存在' }),
    } as unknown as Response)

    await expect(agentService.sendMessageStream(
      999,
      { message: 'hello' },
      {},
    )).rejects.toThrow('会话不存在')
  })

  it('rejects successful responses with the wrong content type', async () => {
    fetchMock.mockResolvedValue(streamResponse('{}', 'application/json'))

    await expect(agentService.sendMessageStream(
      11,
      { message: 'hello' },
      {},
    )).rejects.toThrow('服务器未返回流式响应')
  })
})
