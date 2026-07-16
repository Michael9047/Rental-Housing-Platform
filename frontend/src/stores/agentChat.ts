// 推荐管家会话 store —— 让聊天记录跨页面切换持久
// AgentView 组件卸载（用户点去别的页面）时，会话 id 和消息都保留在这里，
// 回到 /agent 直接续聊，不再每次进入新建会话。
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
  }

  return { sessionId, messages, aiAvailable, ensureSession, reset }
})
