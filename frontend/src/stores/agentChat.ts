// AI 租房助手会话 store —— 管理会话记录、历史回放与跨会话长期记忆。
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { agentService } from '@/services/agent'
import { uniqueAgentRecommendations } from '@/utils/agentRecommendations'
import type {
  AgentChatMessage,
  AgentFilters,
  AgentHistoryMessage,
  AgentLink,
  AgentRecommendation,
  AgentSessionSummary,
  AgentSource,
  AgentStateSummary,
  QueryRewriteInfo,
} from '@/types/agent'

export const GREETING: AgentChatMessage = {
  role: 'assistant',
  content:
    '你好，我是租房推荐管家 👋\n' +
    '告诉我学校、国家/地区、预算和户型，我会记住你刚才提到的房源与偏好。' +
    '推荐后可以继续问「这套有健身房吗」「附近有自习空间吗」或「这几套哪个好」。',
  isWelcome: true,
}

function historyToChatMessage(message: AgentHistoryMessage): AgentChatMessage {
  const metadata = message.metadata || {}
  const recommendations = Array.isArray(metadata.recommendations)
    ? metadata.recommendations.filter((item): item is AgentRecommendation => (
        typeof item === 'object' && item !== null && typeof item.property === 'object'
      ))
    : []
  const topPicks = Array.isArray(metadata.top_picks)
    ? metadata.top_picks.filter((item): item is AgentRecommendation => (
        typeof item === 'object' && item !== null && typeof item.property === 'object'
      ))
    : []
  const restoredRecommendations = uniqueAgentRecommendations(
    recommendations.length ? recommendations : topPicks,
  )
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    recommendations: restoredRecommendations.length ? restoredRecommendations : undefined,
    allRecommendations: restoredRecommendations.length ? restoredRecommendations : undefined,
    aiAvailable: typeof metadata.ai_available === 'boolean'
      ? metadata.ai_available
      : undefined,
    quickReplies: Array.isArray(metadata.quick_replies)
      ? metadata.quick_replies.map(String)
      : undefined,
    guidedOptions: Array.isArray(metadata.guided_options)
      ? metadata.guided_options as AgentChatMessage['guidedOptions']
      : undefined,
    stateSummary: metadata.state_summary
      ? metadata.state_summary as AgentStateSummary
      : undefined,
    queryRewrite: metadata.query_rewrite
      ? metadata.query_rewrite as QueryRewriteInfo
      : undefined,
    sources: Array.isArray(metadata.sources)
      ? metadata.sources as AgentSource[]
      : undefined,
    links: Array.isArray(metadata.links)
      ? metadata.links as AgentLink[]
      : undefined,
  }
}

export const useAgentChatStore = defineStore('agentChat', () => {
  const sessionId = ref<number | null>(null)
  const messages = ref<AgentChatMessage[]>([])
  const aiAvailable = ref(true)
  const sessions = ref<AgentSessionSummary[]>([])
  const loadingHistory = ref(false)
  const rememberedPreferences = ref<AgentFilters>({})
  const memoryLoaded = ref(false)
  const searchPanelOpen = ref(false)
  /** 外部页面（如首页）触发的待发送查询 */
  const pendingQuery = ref<string | null>(null)

  let creating: Promise<void> | null = null

  /**
   * 创建并追加一条可流式更新的助手消息。
   *
   * Vue 3 不会跟踪「普通对象入队后，继续通过原对象引用修改」。
   * 流式回调必须持有这里返回的响应式对象，才会在每个 SSE 文本块到达时立即重绘。
   */
  function appendStreamingAssistant(
    initial: Partial<AgentChatMessage> = {},
  ): AgentChatMessage {
    const message = reactive<AgentChatMessage>({
      ...initial,
      role: 'assistant',
      content: initial.content ?? '',
      streaming: true,
    })
    messages.value.push(message)
    return message
  }

  /** 拉取会话记录；失败不影响当前对话继续使用。 */
  async function fetchSessions(): Promise<void> {
    try {
      sessions.value = await agentService.listSessions()
    } catch {
      // 历史记录属于辅助能力，接口异常时保留当前会话。
    }
  }

  /** 拉取跨会话长期记忆。 */
  async function fetchMemory(): Promise<void> {
    try {
      const memory = await agentService.getMemory()
      rememberedPreferences.value = memory.preferences || {}
      memoryLoaded.value = true
    } catch {
      // 未登录或接口暂不可用时，不阻断找房对话。
    }
  }

  /** 确保会话存在（并发安全，只创建一次）；首次创建时附上欢迎语。 */
  async function ensureSession(): Promise<void> {
    if (sessionId.value !== null) return
    if (!creating) {
      creating = agentService
        .createSession()
        .then((s) => {
          sessionId.value = s.session_id
          if (messages.value.length === 0) messages.value.push({ ...GREETING })
          void fetchSessions()
          if (!memoryLoaded.value) void fetchMemory()
        })
        .finally(() => {
          creating = null
        })
    }
    await creating
  }

  /** 开始一个全新对话。 */
  async function newSession(): Promise<void> {
    const session = await agentService.createSession()
    sessionId.value = session.session_id
    messages.value = [{ ...GREETING }]
    await fetchSessions()
  }

  /** 切换并回放历史会话。 */
  async function switchSession(id: number): Promise<void> {
    if (sessionId.value === id && messages.value.length > 0) return
    loadingHistory.value = true
    try {
      const history = await agentService.getSessionMessages(id)
      sessionId.value = id
      messages.value = [
        { ...GREETING },
        ...history.items.map(historyToChatMessage),
      ]
    } finally {
      loadingHistory.value = false
    }
  }

  /** 保存明确偏好，供之后的新会话继续使用。 */
  async function saveMemory(preferences: AgentFilters): Promise<void> {
    const memory = await agentService.saveMemory(preferences)
    rememberedPreferences.value = memory.preferences || preferences
    memoryLoaded.value = true
  }

  /** 清空长期记忆。 */
  async function clearMemory(): Promise<void> {
    await agentService.clearMemory()
    rememberedPreferences.value = {}
    memoryLoaded.value = true
  }

  /** 登出等场景清空 */
  function reset(): void {
    sessionId.value = null
    messages.value = []
    sessions.value = []
    aiAvailable.value = true
    rememberedPreferences.value = {}
    memoryLoaded.value = false
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

  return {
    sessionId,
    messages,
    aiAvailable,
    sessions,
    loadingHistory,
    rememberedPreferences,
    memoryLoaded,
    searchPanelOpen,
    pendingQuery,
    appendStreamingAssistant,
    fetchSessions,
    fetchMemory,
    ensureSession,
    newSession,
    switchSession,
    saveMemory,
    clearMemory,
    reset,
    openWithQuery,
    consumeQuery,
  }
})
