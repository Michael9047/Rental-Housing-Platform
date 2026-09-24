import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { compareService } from '@/services/compare'
import type { CompareSessionResponse } from '@/types/compare'

const encoder = new TextEncoder()

function chunkBytes(text: string, pattern = [1, 4, 2, 9, 3, 7]): Uint8Array[] {
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

function streamResponse(text: string): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunkBytes(text)) controller.enqueue(chunk)
      controller.close()
    },
  })
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'text/event-stream; charset=utf-8' }),
    body,
  } as Response
}

function resultSession(): CompareSessionResponse {
  return {
    id: 31,
    user_id: 7,
    property_ids: [101, 202],
    priority: 'commute',
    status: 'active',
    result_cache: {
      scores: {},
      property_data: {},
      reply: '最终对比建议',
    },
    created_at: '2026-08-10T00:00:00Z',
    messages: [],
  }
}

describe('compareService.createSessionStream', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    localStorage.clear()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('parses arbitrary byte chunks across status, token, result and DONE events', async () => {
    localStorage.setItem('access_token', 'compare-token')
    const session = resultSession()
    const payload = [
      ': connected\r\n\r\n',
      'data: {"meta":{"event":"status","status":"comparing","message":"正在整理对比数据"}}\r\n\r\n',
      'event: message\r\n',
      'data: {"token":\r\n',
      'data: "对"}\r\n\r\n',
      'data: {"token":"比"}\r\n\r\n',
      `data: ${JSON.stringify({ meta: { event: 'result', session } })}\r\n\r\n`,
      'data: [DONE]\r\n\r\n',
      'data: {"token":"不应读取"}\r\n\r\n',
    ].join('')
    fetchMock.mockResolvedValue(streamResponse(payload))
    const onToken = vi.fn()
    const onMeta = vi.fn()

    await compareService.createSessionStream(
      { property_ids: [101, 202], priority: 'commute' },
      { onToken, onMeta },
    )

    expect(onToken.mock.calls.map(([token]) => token)).toEqual(['对', '比'])
    expect(onMeta).toHaveBeenCalledTimes(2)
    expect(onMeta).toHaveBeenNthCalledWith(1, {
      event: 'status',
      status: 'comparing',
      message: '正在整理对比数据',
    })
    expect(onMeta).toHaveBeenNthCalledWith(2, {
      event: 'result',
      session,
    })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/compare/sessions/stream',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Accept: 'text/event-stream',
          Authorization: 'Bearer compare-token',
        }),
        body: JSON.stringify({ property_ids: [101, 202], priority: 'commute' }),
      }),
    )
  })

  it('rejects a stream that closes before DONE even after delivering partial tokens', async () => {
    fetchMock.mockResolvedValue(streamResponse([
      'data: {"meta":{"event":"status","status":"generating","message":"正在生成"}}\n\n',
      'data: {"token":"部分结果"}\n\n',
    ].join('')))
    const onToken = vi.fn()
    const onMeta = vi.fn()

    await expect(compareService.createSessionStream(
      { property_ids: [1, 2] },
      { onToken, onMeta },
    )).rejects.toThrow('流式对比连接在完成前中断')

    expect(onMeta).toHaveBeenCalledWith({
      event: 'status',
      status: 'generating',
      message: '正在生成',
    })
    expect(onToken).toHaveBeenCalledOnce()
    expect(onToken).toHaveBeenCalledWith('部分结果')
  })
})
