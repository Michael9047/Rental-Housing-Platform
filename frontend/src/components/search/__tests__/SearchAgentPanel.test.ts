// 搜索页内嵌 Agent 的任务边界同步测试。
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SearchAgentPanel from '@/components/search/SearchAgentPanel.vue'

const RecPropertyCardStub = defineComponent({
  name: 'RecPropertyCard',
  props: {
    rec: { type: Object, required: true },
    selected: { type: Boolean, default: false },
  },
  emits: ['toggle-compare'],
  setup(props, { emit }) {
    return () => h('button', {
      class: 'recommendation-select',
      type: 'button',
      onClick: () => emit(
        'toggle-compare',
        Number((props.rec as { property_id: number }).property_id),
        !props.selected,
      ),
    })
  },
})

function recommendation(propertyId: number) {
  return {
    property_id: propertyId,
    rank: 1,
    match_reason: '测试候选',
    pros: [],
    cons: [],
    property: { id: propertyId, institute_id: propertyId, name: `Room ${propertyId}` },
  }
}

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
}))

const agentServiceMocks = vi.hoisted(() => ({
  getFaqs: vi.fn(),
  sendMessageStream: vi.fn(),
}))

let agentChatStore: any
let cartStore: any

vi.mock('vue-router', () => ({
  useRouter: () => routerMocks,
}))

vi.mock('@/services/agent', () => ({
  agentService: agentServiceMocks,
}))

vi.mock('@/stores/agentChat', () => ({
  useAgentChatStore: () => agentChatStore,
}))

vi.mock('@/stores/cart', () => ({
  useCartStore: () => cartStore,
}))

function createWrapper(filters = {
  city: 'Singapore',
  institution: 'NUS',
  institute_id: 101,
  commute_mode: 'walking',
  commute_minutes: 15,
}) {
  return mount(SearchAgentPanel, {
    props: {
      filters,
      resultCount: 8,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        RecPropertyCard: RecPropertyCardStub,
      },
    },
  })
}

describe('SearchAgentPanel 任务边界同步', () => {
  beforeEach(() => {
    routerMocks.push.mockReset()
    agentServiceMocks.getFaqs.mockReset()
    agentServiceMocks.getFaqs.mockResolvedValue([])
    agentServiceMocks.sendMessageStream.mockReset()

    agentChatStore = {
      sessionId: ref(88),
      messages: ref([]),
      sessions: ref([]),
      appendStreamingAssistant: vi.fn(() => {
        const message = { role: 'assistant', content: '', streaming: true }
        agentChatStore.messages.value.push(message)
        return message
      }),
      fetchSessions: vi.fn().mockResolvedValue(undefined),
      switchSession: vi.fn().mockResolvedValue(undefined),
      ensureSession: vi.fn().mockResolvedValue(undefined),
    }
    cartStore = {
      items: [],
      has: vi.fn().mockReturnValue(false),
      fetch: vi.fn().mockResolvedValue(undefined),
      add: vi.fn().mockResolvedValue(true),
      remove: vi.fn().mockResolvedValue(undefined),
    }
  })

  it('continue 的依赖重置先清旧字段，再用完整状态摘要替换', async () => {
    agentServiceMocks.sendMessageStream.mockImplementationOnce(
      async (_sessionId: number, _body: unknown, handlers: any) => {
        handlers.onMeta?.({
          event: 'result',
          task_boundary: {
            relation: 'continue',
            task_id: 'task-1',
            reason: '用户明确修改当前任务地点',
            reset_fields: [
              'city',
              'institution',
              'institute_id',
              'commute_mode',
              'commute_minutes',
            ],
            clarification_question: null,
          },
          state_summary: {
            stage: 'narrow',
            filters: { city: 'London', institution: 'UCL' },
            chips: [],
          },
          // 有完整摘要时不能只应用这个增量 patch。
          filter_patch: { city: '错误的旧城市' },
          cleared_filters: [],
        })
      },
    )

    const wrapper = createWrapper()
    await flushPromises()
    await wrapper.get('.composer textarea').setValue('把当前搜索改到 UCL')
    await wrapper.get('.send-btn').trigger('click')
    await flushPromises()

    const events = wrapper.emitted('apply-filter-patch') || []
    expect(events).toHaveLength(1)
    expect(events[0][0]).toEqual({ city: 'London', institution: 'UCL' })
    expect(events[0][1]).toBe(true)
    expect(new Set(events[0][2] as string[])).toEqual(new Set([
      'city',
      'institution',
      'institute_id',
      'commute_mode',
      'commute_minutes',
    ]))
    wrapper.unmount()
  })

  it('手动修改搜索栏时只把结构化增量作为本轮信号', async () => {
    const stableFilters = {
      country: 'SG',
      city: 'Singapore',
      institution: 'NUS',
      price_max: 2000,
    }
    const wrapper = createWrapper(stableFilters)
    await flushPromises()
    await wrapper.setProps({
      filters: {
        ...stableFilters,
        country: 'GB',
        city: 'London',
      },
    })

    await wrapper.get('.composer textarea').setValue('按这些条件')
    await wrapper.get('.send-btn').trigger('click')
    await flushPromises()

    const request = agentServiceMocks.sendMessageStream.mock.calls[0][1]
    expect(request.context_filters).toEqual(stableFilters)
    expect(request.filters).toEqual({ country: 'GB', city: 'London' })
    expect(request.filters).not.toHaveProperty('institution')
    expect(request.filters).not.toHaveProperty('price_max')
    wrapper.unmount()
  })

  it('零结果新任务不会把旧任务推荐或购物车作为隐式对比候选', async () => {
    agentChatStore.messages.value = [
      {
        role: 'assistant',
        content: '旧任务推荐',
        recommendations: [recommendation(11), recommendation(12)],
        taskBoundary: {
          relation: 'continue',
          task_id: 'task-old',
          reason: '',
          reset_fields: [],
        },
      },
      {
        role: 'assistant',
        content: '新任务没有结果',
        recommendations: [],
        taskBoundary: {
          relation: 'new',
          task_id: 'task-new',
          reason: '',
          reset_fields: ['country', 'city', 'institution'],
        },
      },
    ]
    cartStore.items = [{ property_id: 11 }, { property_id: 12 }]

    const wrapper = createWrapper()
    await flushPromises()
    await wrapper.get('.composer textarea').setValue('对比这几套')
    await wrapper.get('.send-btn').trigger('click')
    await flushPromises()

    expect(agentServiceMocks.sendMessageStream).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('continue 重置候选后清空手选项且不回捞同 task 的旧推荐', async () => {
    agentChatStore.messages.value = [{
      role: 'assistant',
      content: 'NUS 推荐',
      recommendations: [recommendation(21), recommendation(22)],
      taskBoundary: {
        relation: 'continue',
        task_id: 'task-1',
        reason: '',
        reset_fields: [],
      },
    }]
    agentServiceMocks.sendMessageStream.mockImplementationOnce(
      async (_sessionId: number, _body: unknown, handlers: any) => {
        handlers.onMeta?.({
          event: 'result',
          recommendations: [],
          task_boundary: {
            relation: 'continue',
            task_id: 'task-1',
            reason: '当前任务改地点',
            reset_fields: ['country', 'city', 'district', 'institution'],
          },
          state_summary: {
            stage: 'narrow',
            filters: { country: 'GB', city: 'London', institution: 'UCL' },
            chips: [],
          },
        })
      },
    )

    const wrapper = createWrapper()
    await flushPromises()
    const cards = wrapper.findAll('.recommendation-select')
    expect(cards).toHaveLength(2)
    await cards[0].trigger('click')
    await cards[1].trigger('click')

    await wrapper.get('.composer textarea').setValue('不要 NUS 了，换 UCL')
    await wrapper.get('.send-btn').trigger('click')
    await flushPromises()
    expect(agentServiceMocks.sendMessageStream).toHaveBeenCalledTimes(1)

    await wrapper.get('.composer textarea').setValue('对比这几套')
    await wrapper.get('.send-btn').trigger('click')
    await flushPromises()
    expect(agentServiceMocks.sendMessageStream).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
