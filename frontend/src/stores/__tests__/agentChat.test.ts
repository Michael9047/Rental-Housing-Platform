import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type {
  AgentHistoryMessage,
  AgentHistoryResponse,
  AgentRecommendation,
  AgentSearchWorkspaceResponse,
} from '@/types/agent'
import { GREETING, useAgentChatStore } from '@/stores/agentChat'

const agentServiceMocks = vi.hoisted(() => ({
  createSession: vi.fn(),
  listSessions: vi.fn(),
  getSessionMessages: vi.fn(),
  getMemory: vi.fn(),
  saveMemory: vi.fn(),
  clearMemory: vi.fn(),
  saveSearchWorkspace: vi.fn(),
  getSearchWorkspace: vi.fn(),
  findSearchWorkspace: vi.fn(),
  claimGuestSessions: vi.fn(),
}))

vi.mock('@/services/agent', () => ({
  agentService: agentServiceMocks,
}))

function recommendation(
  propertyId: number,
  instituteId: number,
  unitTypeName: string,
): AgentRecommendation {
  return {
    property_id: propertyId,
    match_reason: '符合条件',
    pros: ['近学校'],
    cons: [],
    property: {
      id: propertyId,
      institute_id: instituteId,
      institute_name: `Institute ${instituteId}`,
      name: unitTypeName,
      title: unitTypeName,
    } as AgentRecommendation['property'],
  }
}

function historyMessage(
  id: number,
  role: AgentHistoryMessage['role'],
  content: string,
  metadata: Record<string, unknown> | null = null,
): AgentHistoryMessage {
  return {
    id,
    session_id: 1,
    role,
    content,
    metadata,
    created_at: '2026-08-09T00:00:00Z',
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('useAgentChatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    agentServiceMocks.createSession.mockReset()
    agentServiceMocks.listSessions.mockReset()
    agentServiceMocks.getSessionMessages.mockReset()
    agentServiceMocks.getMemory.mockReset()
    agentServiceMocks.saveMemory.mockReset()
    agentServiceMocks.clearMemory.mockReset()
    agentServiceMocks.saveSearchWorkspace.mockReset()
    agentServiceMocks.getSearchWorkspace.mockReset()
    agentServiceMocks.findSearchWorkspace.mockReset()
    agentServiceMocks.claimGuestSessions.mockReset()
    agentServiceMocks.listSessions.mockResolvedValue([])
  })

  it('restores structured history metadata and preserves cross-Institute UnitTypes', async () => {
    const first = recommendation(101, 10, 'Studio')
    const duplicateId = recommendation(101, 99, 'Ensuite')
    const duplicateNameInInstitute = recommendation(102, 10, ' stu-dio ')
    const sameNameAtAnotherInstitute = recommendation(103, 11, 'Studio')
    const fallbackTopPick = recommendation(104, 12, '1 Bed')
    agentServiceMocks.getSessionMessages.mockResolvedValue({
      items: [
        historyMessage(1, 'user', '想找 Studio'),
        historyMessage(2, 'assistant', '给你两套建议', {
          recommendations: [
            first,
            duplicateId,
            duplicateNameInInstitute,
            sameNameAtAnotherInstitute,
          ],
          ai_available: false,
          quick_replies: ['只看便宜的', 7],
          guided_options: [{
            label: '伦敦',
            message: '看伦敦',
            filter_patch: { city: 'London' },
            kind: 'city',
            icon: 'location',
          }],
          state_summary: { stage: 'results', filters: { city: 'London' }, chips: [] },
          task_boundary: {
            relation: 'new',
            task_id: 'task-london',
            reason: '用户改为在伦敦找房',
            reset_fields: ['country', 'institution'],
            clarification_question: null,
          },
          query_rewrite: {
            original: '那里',
            rewritten: 'London',
            kind: 'reference',
            used_llm: false,
          },
          sources: [{ label: '房源库', status: 'verified' }],
          links: [{ label: '候选清单', to: '/cart' }],
          thinking_steps: [{
            agent_id: 'search',
            agent_name: '搜索',
            status: 'success',
            summary: '找到两套',
            duration_ms: 20,
          }],
          filter_patch: { city: 'London', price_max: 1500 },
        }),
        historyMessage(3, 'assistant', '另一个结果', {
          recommendations: [],
          top_picks: [fallbackTopPick],
        }),
      ],
      has_more: false,
    } satisfies AgentHistoryResponse)
    const store = useAgentChatStore()

    await store.switchSession(42)

    expect(store.sessionId).toBe(42)
    expect(store.messages[0]).toMatchObject({
      content: GREETING.content,
      isWelcome: true,
    })
    expect(store.messages[2].recommendations?.map((item) => item.property_id)).toEqual([101, 103])
    expect(store.messages[2].allRecommendations?.map((item) => item.property_id)).toEqual([101, 103])
    expect(store.messages[2]).toMatchObject({
      aiAvailable: false,
      quickReplies: ['只看便宜的', '7'],
      filterPatch: { city: 'London', price_max: 1500 },
      stateSummary: { stage: 'results' },
      taskBoundary: {
        relation: 'new',
        task_id: 'task-london',
        reset_fields: ['country', 'institution'],
      },
      queryRewrite: { rewritten: 'London' },
      sources: [{ label: '房源库', status: 'verified' }],
      links: [{ label: '候选清单', to: '/cart' }],
    })
    expect(store.messages[3].recommendations?.map((item) => item.property_id)).toEqual([104])
  })

  it('keeps the latest session when older history resolves after a newer switch', async () => {
    const firstHistory = deferred<AgentHistoryResponse>()
    const secondHistory = deferred<AgentHistoryResponse>()
    agentServiceMocks.getSessionMessages.mockImplementation((id: number) => (
      id === 1 ? firstHistory.promise : secondHistory.promise
    ))
    const store = useAgentChatStore()

    const firstSwitch = store.switchSession(1)
    const secondSwitch = store.switchSession(2)
    secondHistory.resolve({
      items: [historyMessage(20, 'assistant', '第二个会话')],
      has_more: false,
    })
    await secondSwitch
    firstHistory.resolve({
      items: [historyMessage(10, 'assistant', '过期的第一个会话')],
      has_more: false,
    })
    await firstSwitch

    expect(store.sessionId).toBe(2)
    expect(store.loadingHistory).toBe(false)
    expect(store.messages.map((message) => message.content)).toEqual([
      GREETING.content,
      '第二个会话',
    ])
  })

  it('restores the real recommendation total but only keeps twenty cards', async () => {
    const recommendations = Array.from({ length: 111 }, (_, index) => (
      recommendation(index + 1, index + 1, `Unit ${index + 1}`)
    ))
    agentServiceMocks.getSessionMessages.mockResolvedValue({
      items: [historyMessage(1, 'assistant', '共有 111 个户型', {
        recommendations,
        recommendation_total: 111,
      })],
      has_more: false,
    } satisfies AgentHistoryResponse)
    const store = useAgentChatStore()

    await store.switchSession(8)

    expect(store.messages[1].recommendationTotal).toBe(111)
    expect(store.messages[1].recommendations).toHaveLength(20)
    expect(store.messages[1].allRecommendations).toHaveLength(20)
  })

  it('loads, saves and clears long-term preferences independently of chat history', async () => {
    agentServiceMocks.getMemory.mockResolvedValue({
      preferences: { city: 'London', price_max: 1800, bedrooms: 1 },
      updated_at: '2026-08-09T00:00:00Z',
    })
    agentServiceMocks.saveMemory.mockResolvedValue({
      preferences: { city: 'London', price_max: 1500, amenities: ['gym'] },
      updated_at: '2026-08-09T00:01:00Z',
    })
    agentServiceMocks.clearMemory.mockResolvedValue(undefined)
    const store = useAgentChatStore()

    await store.fetchMemory()
    expect(store.memoryLoaded).toBe(true)
    expect(store.rememberedPreferences).toEqual({
      city: 'London',
      price_max: 1800,
      bedrooms: 1,
    })

    await store.saveMemory({ price_max: 1500, amenities: ['gym'] })
    expect(agentServiceMocks.saveMemory).toHaveBeenCalledWith({
      price_max: 1500,
      amenities: ['gym'],
    })
    expect(store.rememberedPreferences).toEqual({
      city: 'London',
      price_max: 1500,
      amenities: ['gym'],
    })

    await store.clearMemory()
    expect(agentServiceMocks.clearMemory).toHaveBeenCalledOnce()
    expect(store.rememberedPreferences).toEqual({})
    expect(store.memoryLoaded).toBe(true)
  })

  it('reuses the current empty session for a normal search', async () => {
    const store = useAgentChatStore()
    agentServiceMocks.createSession.mockResolvedValue({
      session_id: 31, session_uuid: 'session-31', cart_id: 1, title: null,
    })
    await store.newSession()

    const sessionId = await store.prepareForSearch()

    expect(sessionId).toBe(31)
    expect(agentServiceMocks.createSession).toHaveBeenCalledTimes(1)
    expect(store.messages).toEqual([{ ...GREETING }])
  })

  it('creates a new empty session when the current session has real messages', async () => {
    agentServiceMocks.createSession
      .mockResolvedValueOnce({ session_id: 41, session_uuid: 'session-41', cart_id: 1, title: null })
      .mockResolvedValueOnce({ session_id: 42, session_uuid: 'session-42', cart_id: 1, title: null })
    const store = useAgentChatStore()
    await store.newSession()
    store.messages.push({ role: 'user', content: '具体需求' })

    const sessionId = await store.prepareForSearch()

    expect(sessionId).toBe(42)
    expect(agentServiceMocks.createSession).toHaveBeenCalledTimes(2)
    expect(store.messages).toEqual([{ ...GREETING }])
  })

  it('reuses the latest server-side empty session after a page refresh', async () => {
    localStorage.setItem('access_token', 'test-token')
    agentServiceMocks.listSessions.mockResolvedValue([{
      session_id: 51,
      session_uuid: 'session-51',
      title: null,
      status: 'active',
      message_count: 0,
      last_message: null,
      created_at: '2026-08-12T00:00:00Z',
      updated_at: '2026-08-12T00:00:00Z',
    }])
    agentServiceMocks.getSessionMessages.mockResolvedValue({ items: [], has_more: false })
    const store = useAgentChatStore()

    const sessionId = await store.prepareForSearch()

    expect(sessionId).toBe(51)
    expect(agentServiceMocks.createSession).not.toHaveBeenCalled()
    expect(agentServiceMocks.getSessionMessages).toHaveBeenCalledWith(51)
  })

  it('persists the guest token on the first ensured session', async () => {
    agentServiceMocks.createSession.mockResolvedValue({
      session_id: 61,
      session_uuid: 'session-61',
      cart_id: 1,
      title: null,
      guest_token: 'guest-token-61',
    })
    const store = useAgentChatStore()

    await store.ensureSession()

    expect(store.sessionId).toBe(61)
    expect(localStorage.getItem('guest_token')).toBe('guest-token-61')
  })

  it('restores the conversation bound to an existing search workspace', async () => {
    localStorage.setItem('access_token', 'test-token')
    const restored = {
      session_id: 71,
      workspace: {
        search_id: 'search-a',
        route_query: { q: 'UCL', search_id: 'search-a' },
        manual_filters: { price_max: 1200 },
        ui_state: { sort_by: 'price_asc' },
      },
      conversation_filters: { institution: 'UCL' },
    } satisfies AgentSearchWorkspaceResponse
    agentServiceMocks.findSearchWorkspace.mockResolvedValue(restored)
    agentServiceMocks.getSessionMessages.mockResolvedValue({ items: [], has_more: false })
    const store = useAgentChatStore()

    const result = await store.findAndRestoreSearchWorkspace('search-a')

    expect(result).toEqual(restored)
    expect(store.sessionId).toBe(71)
    expect(agentServiceMocks.createSession).not.toHaveBeenCalled()
  })
})
