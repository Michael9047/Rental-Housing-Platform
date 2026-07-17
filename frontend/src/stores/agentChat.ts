// AI 租房管家（浮动气泡）会话 store —— 多会话 + 跨页面持久
// 像 Claude 一样支持多个对话：左侧列表可新建/切换/删除，历史消息从后端回放。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { agentService } from '@/services/agent'
import type { AgentChatMessage, AgentSessionSummary } from '@/types/agent'

export const GREETING: AgentChatMessage = {
  role: 'assistant',
  content: '你好，我是租房推荐管家 👋 这些入口可能对你有帮助：',
  isWelcome: true,
}

export const useAgentChatStore = defineStore('agentChat', () => {
  const sessionId = ref<number | null>(null)
  const messages = ref<AgentChatMessage[]>([])
  const aiAvailable = ref(true)

  const sessions = ref<AgentSessionSummary[]>([])
  const loadingHistory = ref(false)

  let creating: Promise<void> | null = null

  /** 拉取会话列表（左侧对话列表） */
  async function fetchSessions(): Promise<void> {
    try {
      sessions.value = await agentService.listSessions()
    } catch {
      // 未登录/接口异常时忽略
    }
  }

  /** 确保有一个可用会话（并发安全，只创建一次）；首次创建时附上欢迎语 */
  async function ensureSession(): Promise<void> {
    if (sessionId.value !== null) return
    if (!creating) {
      creating = (async () => {
        // 优先续用最近一个已有会话，没有再新建
        await fetchSessions()
        if (sessions.value.length > 0) {
          await switchSession(sessions.value[0].id)
          return
        }
        const s = await agentService.createSession()
        sessionId.value = s.session_id
        messages.value = [{ ...GREETING }]
        await fetchSessions()
      })().finally(() => {
        creating = null
      })
    }
    await creating
  }

  /** 新建一个对话（左侧「新对话」按钮） */
  async function newSession(): Promise<void> {
    const s = await agentService.createSession()
    sessionId.value = s.session_id
    messages.value = [{ ...GREETING }]
    await fetchSessions()
  }

  /** 切换到某个历史会话，并回放它的消息 */
  async function switchSession(id: number): Promise<void> {
    loadingHistory.value = true
    try {
      const history = await agentService.getSessionMessages(id)
      sessionId.value = id
      messages.value = history.length
        ? history.map((m) => ({
            id: m.id ?? undefined,
            role: m.role,
            content: m.content,
            recommendations: m.recommendations?.length ? m.recommendations : undefined,
            elicit: m.elicit ?? undefined,
            feedback: m.feedback,
            intent: m.intent,
          }))
        : [{ ...GREETING }]
    } finally {
      loadingHistory.value = false
    }
  }

  /** 删除会话；删掉的是当前会话就自动切到别的（或新建） */
  async function deleteSession(id: number): Promise<void> {
    await agentService.deleteSession(id)
    await fetchSessions()
    if (sessionId.value === id) {
      sessionId.value = null
      messages.value = []
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].id)
      } else {
        await newSession()
      }
    }
  }

  /** 登出等场景清空 */
  function reset(): void {
    sessionId.value = null
    messages.value = []
    sessions.value = []
    aiAvailable.value = true
  }

  return {
    sessionId,
    messages,
    aiAvailable,
    sessions,
    loadingHistory,
    fetchSessions,
    ensureSession,
    newSession,
    switchSession,
    deleteSession,
    reset,
  }
})
