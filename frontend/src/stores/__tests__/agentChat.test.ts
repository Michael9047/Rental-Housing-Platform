// Agent 会话 store 的流式响应式更新测试。
import { createPinia, setActivePinia } from 'pinia'
import { watch } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'
import { useAgentChatStore } from '@/stores/agentChat'

describe('useAgentChatStore 流式消息', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('每个 token 到达时都会触发消息内容更新', () => {
    const store = useAgentChatStore()
    const contents: string[] = []
    const stop = watch(
      () => store.messages[store.messages.length - 1]?.content,
      (content) => contents.push(content ?? ''),
      { flush: 'sync' },
    )

    const message = store.appendStreamingAssistant()
    message.content += '你'
    message.content += '好'

    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('你好')
    expect(contents).toEqual(['', '你', '你好'])
    stop()
  })
})
