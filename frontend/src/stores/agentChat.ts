// AI 租房助手状态：管理多会话回放、流式消息与跨会话长期偏好。
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { agentService } from '@/services/agent'
import {
  uniqueAgentRecommendations,
  visibleAgentRecommendations,
} from '@/utils/agentRecommendations'
import type {
  AgentChatMessage,
  AgentFilters,
  AgentHistoryMessage,
  AgentLink,
  AgentRecommendation,
  AgentSearchWorkspace,
  AgentSearchWorkspaceResponse,
  AgentSessionSummary,
  AgentSource,
  AgentStateSummary,
  AgentTaskBoundary,
  QueryRewriteInfo,
  ThinkingStep,
} from '@/types/agent'

export const GREETING: AgentChatMessage = {
  role: 'assistant',
  content:
    '你好，我是租房推荐管家 👋\n' +
    '告诉我学校、国家/地区、预算和户型，我会记住你刚才提到的户型与偏好。' +
    '推荐后可以继续问「这套有健身房吗」「附近通勤方便吗」或「这几套哪个好」。',
  isWelcome: true,
}

function isRecommendation(value: unknown): value is AgentRecommendation {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<AgentRecommendation>
  return Number.isInteger(Number(candidate.property_id))
    && !!candidate.property
    && typeof candidate.property === 'object'
}

function historyToChatMessage(message: AgentHistoryMessage): AgentChatMessage {
  const metadata = message.metadata || {}
  const recommendations = Array.isArray(metadata.recommendations)
    ? metadata.recommendations.filter(isRecommendation)
    : []
  const topPicks = Array.isArray(metadata.top_picks)
    ? metadata.top_picks.filter(isRecommendation)
    : []
  const allRestoredRecommendations = uniqueAgentRecommendations(
    recommendations.length ? recommendations : topPicks,
  )
  const restoredRecommendations = visibleAgentRecommendations(allRestoredRecommendations)
  const persistedTotal = Number(metadata.recommendation_total)
  const recommendationTotal = Number.isInteger(persistedTotal) && persistedTotal >= 0
    ? Math.max(persistedTotal, allRestoredRecommendations.length)
    : allRestoredRecommendations.length

  return {
    id: message.id,
    role: message.role,
    content: message.content,
    recommendations: restoredRecommendations.length ? restoredRecommendations : undefined,
    allRecommendations: restoredRecommendations.length ? restoredRecommendations : undefined,
    recommendationTotal: recommendationTotal || undefined,
    aiAvailable: typeof metadata.ai_available === 'boolean' ? metadata.ai_available : undefined,
    quickReplies: Array.isArray(metadata.quick_replies)
      ? metadata.quick_replies.map(String)
      : undefined,
    guidedOptions: Array.isArray(metadata.guided_options)
      ? metadata.guided_options as AgentChatMessage['guidedOptions']
      : undefined,
    stateSummary: metadata.state_summary
      ? metadata.state_summary as AgentStateSummary
      : undefined,
    turnSummary: metadata.turn_summary
      ? metadata.turn_summary as AgentStateSummary
      : undefined,
    taskBoundary: metadata.task_boundary && typeof metadata.task_boundary === 'object'
      ? metadata.task_boundary as AgentTaskBoundary
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
    thinkingSteps: Array.isArray(metadata.thinking_steps)
      ? metadata.thinking_steps as ThinkingStep[]
      : undefined,
    filterPatch: metadata.filter_patch && typeof metadata.filter_patch === 'object'
      ? metadata.filter_patch as Record<string, unknown>
      : undefined,
    clearedFilters: Array.isArray(metadata.cleared_filters)
      ? metadata.cleared_filters as AgentChatMessage['clearedFilters']
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
  /** 首页等外部页面触发、等待 AI 页面消费的查询。 */
  const pendingQuery = ref<string | null>(null)

  let creating: Promise<void> | null = null
  let preparingSearch: Promise<number> | null = null
  let lifecycleEpoch = 0
  let historyRequestId = 0

  function persistGuestToken(token?: string | null): void {
    if (token && !localStorage.getItem('access_token')) {
      localStorage.setItem('guest_token', token)
    }
  }

  /**
   * 创建一条可被 SSE 回调持续修改的响应式消息。
   * 必须返回 reactive 对象，避免继续修改入队前的普通对象时界面不更新。
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

  /** 拉取会话列表；辅助接口失败不影响当前对话。 */
  async function fetchSessions(): Promise<void> {
    const epoch = lifecycleEpoch
    try {
      const result = await agentService.listSessions()
      if (epoch === lifecycleEpoch) sessions.value = result
    } catch {
      // 保留当前会话，页面仍可继续发送消息。
    }
  }

  /** 拉取用户主动保存的长期偏好。 */
  async function fetchMemory(): Promise<void> {
    const epoch = lifecycleEpoch
    try {
      const memory = await agentService.getMemory()
      if (epoch !== lifecycleEpoch) return
      rememberedPreferences.value = memory.preferences || {}
      memoryLoaded.value = true
    } catch {
      // 未登录或接口暂不可用时不阻断找房。
    }
  }

  /** 并发安全地保证当前存在一个 Agent 会话。 */
  async function ensureSession(): Promise<void> {
    if (sessionId.value !== null) return

    if (!creating) {
      const epoch = lifecycleEpoch
      const task = agentService.createSession().then((session) => {
        persistGuestToken(session.guest_token)
        if (epoch !== lifecycleEpoch) return
        sessionId.value = session.session_id
        if (messages.value.length === 0) messages.value.push({ ...GREETING })
        void fetchSessions()
        if (!memoryLoaded.value) void fetchMemory()
      })
      creating = task
      try {
        await task
      } finally {
        if (creating === task) creating = null
      }
      return
    }

    await creating
  }

  /** 创建全新会话，旧历史仍保留在侧栏。 */
  async function newSession(): Promise<void> {
    lifecycleEpoch += 1
    creating = null
    historyRequestId += 1
    const epoch = lifecycleEpoch
    const session = await agentService.createSession()
    persistGuestToken(session.guest_token)
    if (epoch !== lifecycleEpoch) return
    sessionId.value = session.session_id
    messages.value = [{ ...GREETING }]
    await fetchSessions()
  }

  /**
   * 为一次普通搜索准备干净会话，但不发送搜索文字。
   * 当前会话只有欢迎语时直接复用；刷新后也优先复用服务端最近的空会话。
   */
  async function prepareForSearch(): Promise<number> {
    const hasRealMessages = messages.value.some((message) => !message.isWelcome)
    if (sessionId.value !== null && !hasRealMessages) return sessionId.value
    if (preparingSearch) return preparingSearch

    const task = (async () => {
      if (sessionId.value === null) {
        const hasIdentity = Boolean(
          localStorage.getItem('access_token') || localStorage.getItem('guest_token'),
        )
        if (hasIdentity) {
          await fetchSessions()
          const latestSession = sessions.value[0]
          if (latestSession?.message_count === 0) {
            await switchSession(latestSession.session_id)
            return latestSession.session_id
          }
        }
      }

      await newSession()
      if (sessionId.value === null) throw new Error('普通搜索会话创建失败')
      return sessionId.value
    })()
    preparingSearch = task
    try {
      return await task
    } finally {
      if (preparingSearch === task) preparingSearch = null
    }
  }

  /** 切换并回放指定历史会话。 */
  async function switchSession(id: number): Promise<void> {
    if (sessionId.value === id && messages.value.length > 0) return
    const requestId = ++historyRequestId
    loadingHistory.value = true
    try {
      const history = await agentService.getSessionMessages(id)
      if (requestId !== historyRequestId) return
      sessionId.value = id
      messages.value = [{ ...GREETING }, ...history.items.map(historyToChatMessage)]
    } finally {
      if (requestId === historyRequestId) loadingHistory.value = false
    }
  }

  async function saveSearchWorkspace(
    workspace: AgentSearchWorkspace,
    targetSessionId = sessionId.value,
  ): Promise<AgentSearchWorkspaceResponse> {
    if (targetSessionId === null) throw new Error('当前没有可绑定的 AI 会话')
    const result = await agentService.saveSearchWorkspace(targetSessionId, workspace)
    const summary = sessions.value.find((item) => item.session_id === targetSessionId)
    if (summary) {
      summary.search_id = workspace.search_id
      summary.search_workspace = workspace
    }
    return result
  }

  async function restoreSearchWorkspace(searchId: string): Promise<AgentSearchWorkspaceResponse> {
    const result = await agentService.getSearchWorkspace(searchId)
    await switchSession(result.session_id)
    return result
  }

  async function findAndRestoreSearchWorkspace(
    searchId: string,
  ): Promise<AgentSearchWorkspaceResponse | null> {
    const result = await agentService.findSearchWorkspace(searchId)
    if (!result) return null
    await switchSession(result.session_id)
    return result
  }

  async function claimGuestSessions(guestToken?: string | null): Promise<number> {
    const token = guestToken || localStorage.getItem('guest_token')
    if (!token || !localStorage.getItem('access_token')) return 0
    const result = await agentService.claimGuestSessions(token)
    localStorage.removeItem('guest_token')
    reset()
    await fetchSessions()
    return result.claimed_sessions
  }

  async function saveMemory(preferences: AgentFilters): Promise<void> {
    const memory = await agentService.saveMemory(preferences)
    rememberedPreferences.value = memory.preferences || preferences
    memoryLoaded.value = true
  }

  async function clearMemory(): Promise<void> {
    await agentService.clearMemory()
    rememberedPreferences.value = {}
    memoryLoaded.value = true
  }

  /** 登录身份改变时彻底清空用户相关状态，并使旧异步结果失效。 */
  function reset(): void {
    lifecycleEpoch += 1
    historyRequestId += 1
    creating = null
    preparingSearch = null
    sessionId.value = null
    messages.value = []
    sessions.value = []
    loadingHistory.value = false
    aiAvailable.value = true
    rememberedPreferences.value = {}
    memoryLoaded.value = false
    pendingQuery.value = null
  }

  function openWithQuery(query: string): void {
    pendingQuery.value = query
  }

  function consumeQuery(): string | null {
    const query = pendingQuery.value
    pendingQuery.value = null
    return query
  }

  return {
    sessionId,
    messages,
    aiAvailable,
    sessions,
    loadingHistory,
    rememberedPreferences,
    memoryLoaded,
    pendingQuery,
    appendStreamingAssistant,
    fetchSessions,
    fetchMemory,
    ensureSession,
    newSession,
    prepareForSearch,
    switchSession,
    saveSearchWorkspace,
    restoreSearchWorkspace,
    findAndRestoreSearchWorkspace,
    claimGuestSessions,
    saveMemory,
    clearMemory,
    reset,
    openWithQuery,
    consumeQuery,
  }
})
