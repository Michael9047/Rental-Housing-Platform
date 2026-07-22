// AI 租房助手会话 store —— 让聊天记录跨页面切换持久
// 会话 id 和消息保留在这里，在不同页面之间切换不会丢失对话。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { agentService } from '@/services/agent'
import type { AgentChatMessage } from '@/types/agent'

export const GREETING: AgentChatMessage = {
  role: 'assistant',
  content:
    '你好，我是租房推荐管家 👋\n' +
    '告诉我地区、预算和户型，我来帮你找房并给出推荐理由；' +
    '也可以直接问「押金怎么退」「合同怎么签」这类问题。\n' +
    '看中的房源可以加入候选清单，凑够两套随时让我对比。',
}

export const useAgentChatStore = defineStore('agentChat', () => {
  const sessionId = ref<number | null>(null)
  const messages = ref<AgentChatMessage[]>([])
  const aiAvailable = ref(true)
  /** 外部页面（如首页）触发的待发送查询 */
  const pendingQuery = ref<string | null>(null)

  let creating: Promise<void> | null = null

  /** 确保会话存在（并发安全，只创建一次）；首次创建时附上欢迎语 */
  async function ensureSession(): Promise<void> {
    if (sessionId.value !== null) return
    if (!creating) {
      creating = agentService
        .createSession()
        .then((s) => {
          sessionId.value = s.session_id
          if (messages.value.length === 0) messages.value.push({ ...GREETING })
        })
        .finally(() => {
          creating = null
        })
    }
    await creating
  }

  /** 登出等场景清空 */
  function reset(): void {
    sessionId.value = null
    messages.value = []
    aiAvailable.value = true
    pendingQuery.value = null
  }

  /** 外部页面触发：设置待发送查询（AssistantBubble 会监听并消费） */
  function openWithQuery(query: string): void {
    pendingQuery.value = query
  }

  /** 消费待发送查询，返回后清空 */
  function consumeQuery(): string | null {
    const q = pendingQuery.value
    pendingQuery.value = null
    return q
  }

  return { sessionId, messages, aiAvailable, pendingQuery, ensureSession, reset, openWithQuery, consumeQuery }
})
