// AI 找房主页面大型对比工作台浮层的交互与状态保留测试。
import {
  defineComponent,
  h,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AiSearch from '@/views/AiSearch.vue'

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  resolve: vi.fn(),
}))

const agentServiceMocks = vi.hoisted(() => ({
  getFaqs: vi.fn(),
  sendMessageStream: vi.fn(),
}))

let agentChatStore: any
let cartStore: any
let authStore: any

vi.mock('vue-router', () => ({
  useRoute: () => ({ fullPath: '/ai-search', params: {}, query: {} }),
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

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authStore,
}))

const recommendations = [101, 202].map((id) => ({
  property_id: id,
  match_reason: `推荐户型 ${id}`,
  property: {
    id,
    institute_id: id + 1000,
    institute_name: `公寓 ${id}`,
    name: `户型 ${id}`,
    title: `户型 ${id}`,
    price_monthly: 1000 + id,
    images: [],
  },
}))

const RecPropertyCardStub = defineComponent({
  name: 'RecPropertyCard',
  props: {
    rec: { type: Object, required: true },
    selected: { type: Boolean, default: false },
    inCart: { type: Boolean, default: false },
  },
  emits: ['toggle-compare'],
  setup(props, { emit }) {
    return () => h('button', {
      class: 'unit-select-stub',
      type: 'button',
      'data-unit-id': String((props.rec as { property_id: number }).property_id),
      'aria-pressed': String(props.selected),
      onClick: () => emit(
        'toggle-compare',
        (props.rec as { property_id: number }).property_id,
        !props.selected,
      ),
    }, `选择 ${(props.rec as { property_id: number }).property_id}`)
  },
})

/**
 * 模拟 Element Plus Dialog 的默认生命周期：第一次打开后保留插槽，关闭时只隐藏。
 * 如果页面额外给 CompareWorkspace 加 v-if，本测试仍会捕获到错误卸载。
 */
const DialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    destroyOnClose: { type: Boolean, default: false },
  },
  setup(props, { slots }) {
    const rendered = ref(props.modelValue)
    watch(() => props.modelValue, (opened) => {
      if (opened) rendered.value = true
    })

    return () => rendered.value
      ? h('div', {
        class: 'dialog-stub',
        'data-open': String(props.modelValue),
        style: { display: props.modelValue ? '' : 'none' },
      }, slots.default?.())
      : null
  },
})

const lifecycle = {
  mounts: 0,
  unmounts: 0,
  nextInstanceId: 0,
}

const CompareWorkspaceStub = defineComponent({
  name: 'CompareWorkspace',
  props: {
    mode: { type: String, default: 'page' },
    initialIds: { type: Array, default: () => [] },
  },
  emits: ['close', 'open-new-page'],
  setup(props, { emit }) {
    const instanceId = ++lifecycle.nextInstanceId
    onMounted(() => { lifecycle.mounts += 1 })
    onBeforeUnmount(() => { lifecycle.unmounts += 1 })

    return () => h('section', {
      'data-testid': 'compare-workspace-stub',
      'data-instance-id': String(instanceId),
      'data-mode': props.mode,
      'data-ids': (props.initialIds as number[]).join(','),
    }, [
      h('button', {
        class: 'close-workspace-stub',
        type: 'button',
        onClick: () => emit('close'),
      }, '关闭对比工作台'),
      h('button', {
        class: 'open-new-page-stub',
        type: 'button',
        onClick: () => emit('open-new-page', [...props.initialIds as number[]]),
      }, '新页面打开'),
    ])
  },
})

function createWrapper() {
  return mount(AiSearch, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        RecPropertyCard: RecPropertyCardStub,
        CompareWorkspace: CompareWorkspaceStub,
        ElDialog: DialogStub,
      },
    },
  })
}

async function selectUnit(wrapper: ReturnType<typeof createWrapper>, id: number) {
  await wrapper.get(`[data-unit-id="${id}"]`).trigger('click')
  await nextTick()
}

describe('AiSearch 大型对比工作台浮层', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    lifecycle.mounts = 0
    lifecycle.unmounts = 0
    lifecycle.nextInstanceId = 0
    routerMocks.push.mockReset()
    routerMocks.replace.mockReset()
    routerMocks.resolve.mockReset()
    routerMocks.resolve.mockReturnValue({ href: '/compare?ids=101%2C202' })
    agentServiceMocks.getFaqs.mockReset()
    agentServiceMocks.getFaqs.mockResolvedValue([])
    agentServiceMocks.sendMessageStream.mockReset()
    agentServiceMocks.sendMessageStream.mockResolvedValue(undefined)

    agentChatStore = {
      sessionId: ref(88),
      messages: ref([{
        role: 'assistant',
        content: '为你找到两个可比较的户型。',
        recommendations,
      }]),
      sessions: ref([]),
      loadingHistory: ref(false),
      rememberedPreferences: ref({}),
      aiAvailable: ref(true),
      fetchSessions: vi.fn().mockResolvedValue(undefined),
      fetchMemory: vi.fn().mockResolvedValue(undefined),
      ensureSession: vi.fn().mockResolvedValue(undefined),
      switchSession: vi.fn().mockResolvedValue(undefined),
      consumeQuery: vi.fn().mockReturnValue(null),
      appendStreamingAssistant: vi.fn(() => {
        const message = { role: 'assistant', content: '', streaming: true }
        agentChatStore.messages.value.push(message)
        return message
      }),
    }
    cartStore = {
      has: vi.fn().mockReturnValue(false),
      fetch: vi.fn().mockResolvedValue(undefined),
      add: vi.fn().mockResolvedValue(true),
      remove: vi.fn().mockResolvedValue(undefined),
    }
    authStore = { isLoggedIn: true }
  })

  it('不足两个户型时不展示操作栏，选中一个后按钮禁用且无法打开', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.find('.compare-bar').exists()).toBe(false)
    expect(lifecycle.mounts).toBe(0)

    await selectUnit(wrapper, 101)
    const openButton = wrapper.get('.open-compare-workspace')
    expect(openButton.attributes('disabled')).toBeDefined()

    await openButton.trigger('click')
    await nextTick()

    expect(lifecycle.mounts).toBe(0)
    expect(wrapper.find('[data-testid="compare-workspace-stub"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('选中两个户型后打开浮层，关闭和再次打开不会销毁工作台实例', async () => {
    const wrapper = createWrapper()
    await flushPromises()
    await selectUnit(wrapper, 101)
    await selectUnit(wrapper, 202)

    const openButton = wrapper.get('.open-compare-workspace')
    expect(openButton.attributes('disabled')).toBeUndefined()
    await openButton.trigger('click')
    await nextTick()

    const workspace = wrapper.get('[data-testid="compare-workspace-stub"]')
    const instanceId = workspace.attributes('data-instance-id')
    expect(workspace.attributes('data-mode')).toBe('overlay')
    expect(workspace.attributes('data-ids')).toBe('101,202')
    expect(lifecycle.mounts).toBe(1)

    await wrapper.get('.close-workspace-stub').trigger('click')
    await nextTick()
    expect(lifecycle.unmounts).toBe(0)
    expect(wrapper.get('.dialog-stub').attributes('data-open')).toBe('false')

    await openButton.trigger('click')
    await nextTick()
    expect(lifecycle.mounts).toBe(1)
    expect(wrapper.get('[data-testid="compare-workspace-stub"]').attributes('data-instance-id'))
      .toBe(instanceId)
    wrapper.unmount()
  })

  it('“新页面打开”携带当前工作台的户型 IDs', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    const wrapper = createWrapper()
    await flushPromises()
    await selectUnit(wrapper, 101)
    await selectUnit(wrapper, 202)
    await wrapper.get('.open-compare-workspace').trigger('click')
    await nextTick()

    await wrapper.get('.open-new-page-stub').trigger('click')

    expect(routerMocks.resolve).toHaveBeenCalledWith({
      name: 'compare',
      query: { ids: '101,202' },
    })
    expect(openSpy).toHaveBeenCalledWith('/compare?ids=101%2C202', '_blank', 'noopener')
    wrapper.unmount()
  })

  it('新任务边界清空对比选择，并以状态摘要替换后续请求上下文', async () => {
    agentChatStore.messages.value[0].stateSummary = {
      stage: 'results',
      filters: { city: 'Singapore', institution: 'NUS' },
      chips: [],
    }
    agentServiceMocks.sendMessageStream
      .mockImplementationOnce(async (_sessionId: number, _body: unknown, handlers: any) => {
        const taskBoundary = {
          relation: 'new',
          task_id: 'task-ucl',
          reason: '用户开始在伦敦找房',
          reset_fields: ['city', 'institution'],
        }
        handlers.onMeta?.({ event: 'status', task_boundary: taskBoundary })
        handlers.onMeta?.({
          event: 'result',
          task_boundary: taskBoundary,
          state_summary: {
            stage: 'results',
            filters: { city: 'London', institution: 'UCL' },
            chips: [],
          },
        })
        // 即使增量 patch 在后续事件才到达，也不得把旧任务条件重新注入。
        handlers.onMeta?.({
          event: 'result',
          filter_patch: { city: 'Singapore', institution: 'NUS' },
        })
      })
      .mockResolvedValueOnce(undefined)

    const wrapper = createWrapper()
    await flushPromises()
    await selectUnit(wrapper, 101)
    await selectUnit(wrapper, 202)
    expect(wrapper.find('.compare-bar').exists()).toBe(true)

    await wrapper.get('.composer textarea').setValue('改为在 UCL 附近找房')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.compare-bar').exists()).toBe(false)
    expect(agentServiceMocks.sendMessageStream.mock.calls[0][1]).toMatchObject({
      context_filters: { city: 'Singapore', institution: 'NUS' },
    })
    expect(agentServiceMocks.sendMessageStream.mock.calls[0][1]).not.toHaveProperty('filters')

    await wrapper.get('.composer textarea').setValue('继续推荐')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(agentServiceMocks.sendMessageStream.mock.calls[1][1]).toMatchObject({
      context_filters: { city: 'London', institution: 'UCL' },
    })
    wrapper.unmount()
  })

  it('继续任务但重置条件时清空候选选择并关闭对比工作台', async () => {
    agentServiceMocks.sendMessageStream.mockImplementationOnce(
      async (_sessionId: number, _body: unknown, handlers: any) => {
        handlers.onMeta?.({
          event: 'result',
          task_boundary: {
            relation: 'continue',
            task_id: 'task-current',
            reason: '用户明确取消原有位置条件',
            reset_fields: ['city', 'institution'],
          },
          state_summary: {
            stage: 'results',
            filters: { price_max: 1800 },
            chips: [],
          },
        })
      },
    )

    const wrapper = createWrapper()
    await flushPromises()
    await selectUnit(wrapper, 101)
    await selectUnit(wrapper, 202)
    await wrapper.get('.open-compare-workspace').trigger('click')
    await nextTick()
    expect(wrapper.get('.dialog-stub').attributes('data-open')).toBe('true')

    await wrapper.get('.composer textarea').setValue('取消学校和城市限制')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.compare-bar').exists()).toBe(false)
    expect(wrapper.get('.dialog-stub').attributes('data-open')).toBe('false')
    expect(wrapper.get('[data-testid="compare-workspace-stub"]').attributes('data-ids')).toBe('')
    wrapper.unmount()
  })

  it('澄清关系保留当前对比选择和筛选上下文', async () => {
    agentChatStore.messages.value[0].stateSummary = {
      stage: 'results',
      filters: { city: 'Singapore', institution: 'NUS' },
      chips: [],
    }
    agentServiceMocks.sendMessageStream.mockImplementationOnce(
      async (_sessionId: number, _body: unknown, handlers: any) => {
        handlers.onMeta?.({
          event: 'result',
          task_boundary: {
            relation: 'clarify',
            task_id: 'task-current',
            reason: '学校简称存在歧义',
            reset_fields: ['city', 'institution'],
            clarification_question: '你指的是哪所学校？',
          },
          state_summary: { stage: 'calibrate', filters: {}, chips: [] },
          cleared_filters: ['city', 'institution'],
        })
      },
    )

    const wrapper = createWrapper()
    await flushPromises()
    await selectUnit(wrapper, 101)
    await selectUnit(wrapper, 202)

    await wrapper.get('.composer textarea').setValue('学校附近')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.compare-bar').exists()).toBe(true)

    await wrapper.get('.composer textarea').setValue('我指的是伦敦那所')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()
    expect(agentServiceMocks.sendMessageStream.mock.calls[1][1]).toMatchObject({
      context_filters: { city: 'Singapore', institution: 'NUS' },
    })
    wrapper.unmount()
  })
})
