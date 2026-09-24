<!-- 搜索页内嵌 AI 面板：流式对话、条件同步、UnitType 推荐与独立对比入口。 -->
<template>
  <section class="agent-panel" aria-label="AI 租房管家">
    <header class="agent-header">
      <div class="agent-title">
        <span class="agent-icon"><el-icon><ChatDotRound /></el-icon></span>
        <div>
          <strong>AI 租房管家</strong>
          <span>{{ starting ? '正在连接' : startupFailed ? '连接失败' : '结合当前筛选继续问' }}</span>
        </div>
      </div>
      <div class="agent-header-actions">
        <el-tooltip content="在全页 AI 中继续" placement="bottom">
          <el-button
            class="agent-action-button"
            aria-label="在全页 AI 中继续"
            :disabled="starting || sending || creatingSession"
            @click="openFullPage"
          >
            <el-icon><FullScreen /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="新建对话" placement="bottom">
          <el-button
            class="agent-action-button"
            aria-label="新建对话"
            :loading="creatingSession"
            :disabled="starting || sending"
            @click="startNewSession"
          >
            <el-icon><Plus /></el-icon>
          </el-button>
        </el-tooltip>
        <el-button text circle aria-label="关闭 AI 租房管家" @click="emit('close')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </header>

    <div v-if="overallRequirementChips.length" class="requirement-summary overall">
      <span>本次对话需求</span>
      <div>
        <i v-for="chip in overallRequirementChips" :key="chip.key">{{ chip.label }}</i>
      </div>
    </div>

    <div ref="messageListRef" class="message-list" aria-live="polite">
      <section class="welcome-panel">
        <strong>说说你的预算、学校和生活偏好</strong>
        <span>我会把明确条件同步回左侧，并推荐可直接加入候选的具体户型。</span>
        <div class="welcome-actions">
          <button :disabled="unavailable" @click="send('帮我根据当前条件推荐合适的户型')">
            <el-icon><Search /></el-icon>
            <span><b>智能找房</b><small>结合左侧筛选</small></span>
          </button>
          <button
            :disabled="unavailable || comparisonCandidateIds.length < 2"
            @click="openCompare(comparisonCandidateIds)"
          >
            <el-icon><DataAnalysis /></el-icon>
            <span>
              <b>综合对比</b>
              <small>{{ comparisonCandidateIds.length >= 2 ? `${comparisonCandidateIds.length} 个具体户型` : '至少需要 2 个户型' }}</small>
            </span>
          </button>
        </div>
      </section>

      <article
        v-for="(message, index) in conversationMessages"
        :key="message.id || `${message.role}-${index}`"
        class="message-block"
      >
        <div v-if="message.role === 'assistant' && uniqueRecommendations(message.recommendations).length" class="recommendation-group">
          <div class="recommendation-head">
            <div>
              <strong>共有 {{ recommendationCount(message) }} 个可选户型</strong>
              <span>当前展示前 {{ uniqueRecommendations(message.recommendations).length }} 个</span>
            </div>
          </div>
          <div v-horizontal-wheel-scroll v-sync-match-reason-heights class="recommendation-row">
            <RecPropertyCard
              v-for="recommendation in uniqueRecommendations(message.recommendations)"
              :key="recommendation.property_id"
              :rec="recommendation"
              :selected="selectedCompareIds.includes(recommendation.property_id)"
              :in-cart="cartStore.has(recommendation.property_id)"
              @toggle-compare="toggleCompare"
              @toggle-cart="handleToggleCart"
              @detail="openProperty"
            />
          </div>
          <div v-if="selectedCompareIds.length" class="compare-selection">
            <span>已选 {{ selectedCompareIds.length }} / 5</span>
            <el-button
              size="small"
              type="primary"
              :disabled="selectedCompareIds.length < 2"
              @click="openCompare(selectedCompareIds)"
            >
              对比已选户型
            </el-button>
            <el-button size="small" text @click="selectedCompareIds = []">清空</el-button>
          </div>
        </div>

        <div class="bubble-row" :class="message.role">
          <div v-if="message.role === 'assistant' && message.streaming && !message.content" class="bubble assistant typing">
            <el-icon class="is-loading"><Loading /></el-icon>
            正在整理回复
          </div>
          <div v-else class="bubble" :class="message.role">{{ message.content }}</div>
        </div>

        <div
          v-if="message.role === 'assistant' && visibleRequirementChips(message.turnSummary).length"
          class="requirement-summary turn"
        >
          <span>本轮提取</span>
          <div>
            <i
              v-for="chip in visibleRequirementChips(message.turnSummary)"
              :key="chip.key"
            >
              {{ chip.label }}
            </i>
          </div>
        </div>

        <div
          v-if="message.role === 'assistant' && message.streaming && currentStep(message)"
          class="processing-chip"
        >
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ currentStep(message)?.summary || '正在处理' }}</span>
        </div>

        <div v-if="message.role === 'assistant' && message.stateSummary?.chips.length" class="memory-row">
          <span v-for="chip in message.stateSummary.chips.slice(0, 6)" :key="chip.key">{{ chip.label }}</span>
        </div>

        <div v-if="message.role === 'assistant' && message.guidedOptions?.length" class="quick-row">
          <button
            v-for="option in message.guidedOptions.slice(0, 4)"
            :key="`${option.kind}-${option.label}`"
            :disabled="sending"
            @click="applyGuidedOption(option)"
          >
            {{ option.label }}
          </button>
        </div>

        <div v-if="message.role === 'assistant' && message.quickReplies?.length" class="quick-row">
          <button
            v-for="reply in message.quickReplies.slice(0, 4)"
            :key="reply"
            :disabled="sending"
            @click="send(reply)"
          >
            {{ reply }}
          </button>
        </div>

        <div v-if="message.role === 'assistant' && message.links?.length" class="quick-row">
          <el-button
            v-for="link in message.links"
            :key="`${link.to}-${link.label}`"
            size="small"
            plain
            type="primary"
            @click="openAgentLink(link.to)"
          >
            {{ link.label }} →
          </el-button>
        </div>
      </article>
    </div>

    <footer class="composer">
      <div class="faq-row">
        <button v-for="faq in faqChips" :key="faq.id" :disabled="unavailable" @click="send(faq.chip)">
          {{ faq.chip }}
        </button>
      </div>
      <div class="composer-row">
        <el-input
          v-model="inputText"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          :maxlength="4000"
          resize="none"
          :disabled="unavailable"
          placeholder="例如：NUS 附近，预算 2000 新币，要独立卫浴"
          @keydown.enter.exact.prevent="send()"
        />
        <el-button
          class="send-btn"
          :type="sending ? 'danger' : 'primary'"
          circle
          :disabled="sending ? stopRequested : unavailable || !inputText.trim()"
          :aria-label="sending ? (stopRequested ? '正在停止' : '停止生成') : '发送'"
          @click="sending ? requestStop() : send()"
        >
          <el-icon v-if="!sending"><Promotion /></el-icon>
          <span v-else class="stop-square" aria-hidden="true" />
        </el-button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  ChatDotRound,
  Close,
  DataAnalysis,
  FullScreen,
  Loading,
  Plus,
  Promotion,
  Search,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import RecPropertyCard from '@/components/RecPropertyCard.vue'
import { vHorizontalWheelScroll } from '@/directives/horizontalWheelScroll'
import { vSyncMatchReasonHeights } from '@/directives/syncMatchReasonHeights'
import { agentService } from '@/services/agent'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'
import {
  compactAgentFilters,
  deriveClearedFilterFields,
  mergeAgentFilterSnapshot,
} from '@/utils/agentFilterSync'
import {
  uniqueAgentRecommendations,
  visibleAgentRecommendations,
} from '@/utils/agentRecommendations'
import type {
  AgentChatMessage,
  AgentFilterField,
  AgentFilters,
  AgentRecommendation,
  AgentStreamMeta,
  FaqChip,
  GuidedOption,
  ThinkingStep,
} from '@/types/agent'

const props = defineProps<{
  filters: AgentFilters
  pendingClearedFilters?: AgentFilterField[]
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (
    event: 'apply-filter-patch',
    patch: Record<string, unknown>,
    refreshResults?: boolean,
    clearedFilters?: AgentFilterField[],
  ): void
  (
    event: 'show-recommendations',
    recommendations: AgentRecommendation[],
    total: number,
  ): void
  (event: 'clear-filters-consumed', fields: AgentFilterField[]): void
  (event: 'new-session'): void
  (event: 'open-full-page'): void
}>()

const router = useRouter()
const agentChatStore = useAgentChatStore()
const cartStore = useCartStore()
const { sessionId, messages, sessions } = storeToRefs(agentChatStore)
const inputText = ref('')
const starting = ref(true)
const startupFailed = ref(false)
const sending = ref(false)
const stopRequested = ref(false)
const creatingSession = ref(false)
const selectedCompareIds = ref<number[]>([])
const messageListRef = ref<HTMLElement | null>(null)
const submittedFilterSnapshot = ref<AgentFilters>(compactAgentFilters(props.filters))
let controller: AbortController | null = null
let activeRequestId: string | null = null
let activeTurnStartIndex: number | null = null
let scrollFrame: number | null = null

const requiredFaqChips: FaqChip[] = [
  { id: 'find_house', chip: '我要找房' },
  { id: 'booking', chip: '预订流程' },
  { id: 'contract', chip: '合同如何签' },
  { id: 'deposit', chip: '押金怎么退' },
]
const faqChips = ref<FaqChip[]>([...requiredFaqChips])
const unavailable = computed(() => starting.value || startupFailed.value || sending.value)
const conversationMessages = computed(() => messages.value.filter((message) => !message.isWelcome))

const latestStateSummary = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const summary = messages.value[index].stateSummary
    if (summary?.chips?.length) return summary
  }
  return null
})

const overallRequirementChips = computed(() => visibleRequirementChips(latestStateSummary.value))

const currentTaskId = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const taskId = messages.value[index].taskBoundary?.task_id
    if (taskId && taskId !== 'pending') return taskId
  }
  return null
})

const currentCandidateEpochStart = computed(() => {
  if (!currentTaskId.value) return 0
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const boundary = messages.value[index].taskBoundary
    if (boundary?.task_id !== currentTaskId.value) continue
    if (boundary.relation === 'new' || boundary.reset_fields.length) return index
  }
  return 0
})

const latestRecommendationIds = computed(() => {
  for (
    let index = messages.value.length - 1;
    index >= currentCandidateEpochStart.value;
    index -= 1
  ) {
    if (
      currentTaskId.value
      && messages.value[index].taskBoundary?.task_id !== currentTaskId.value
    ) continue
    const recommendations = uniqueRecommendations(messages.value[index].recommendations)
    if (recommendations.length) return recommendations.map((item) => item.property_id).slice(0, 5)
  }
  return []
})

/** 这里只可能返回 UnitType ID：推荐结果优先，其次才是候选清单。 */
const comparisonCandidateIds = computed(() => {
  if (selectedCompareIds.value.length) return selectedCompareIds.value
  if (latestRecommendationIds.value.length) return latestRecommendationIds.value
  // 已有任务边界时，购物车可能来自旧任务，不能作为当前任务的隐式候选。
  if (currentTaskId.value) return []
  return cartStore.items.map((item) => item.property_id).slice(0, 5)
})

/** 保留 Pinia 中的当前会话，切换到全页 AI 继续对话。 */
function openFullPage() {
  if (starting.value || sending.value || creatingSession.value) return
  emit('open-full-page')
}

/** 与全页 AI 共用同一个会话创建动作，并清理当前面板的临时交互状态。 */
async function startNewSession() {
  if (starting.value || sending.value || creatingSession.value) return
  creatingSession.value = true
  try {
    await agentChatStore.newSession()
    inputText.value = ''
    selectedCompareIds.value = []
    submittedFilterSnapshot.value = compactAgentFilters(props.filters)
    emit('new-session')
    await scrollToBottom()
  } catch {
    ElMessage.error('新对话创建失败，请稍后重试')
  } finally {
    creatingSession.value = false
  }
}

onMounted(async () => {
  try {
    // 侧边栏重开或放大前后均复用当前会话；只有用户明确点击新建时才创建新会话。
    await ensureSharedSession()
    await Promise.all([
      cartStore.fetch(),
      agentService.getFaqs().then((remote) => {
        const merged = [...requiredFaqChips]
        for (const chip of remote) {
          if (!merged.some((item) => item.id === chip.id || item.chip === chip.chip)) merged.push(chip)
        }
        faqChips.value = merged.slice(0, 6)
      }).catch(() => undefined),
    ])
    await scrollToBottom()
  } catch {
    startupFailed.value = true
    ElMessage.error('AI 租房管家启动失败，请稍后重新打开')
  } finally {
    starting.value = false
  }
})

/** 内嵌面板与独立 AI 页共用最近会话；只有无历史时才新建。 */
async function ensureSharedSession(): Promise<void> {
  if (sessionId.value !== null) return
  if (!localStorage.getItem('access_token') && !localStorage.getItem('guest_token')) {
    await agentChatStore.ensureSession()
    return
  }
  await agentChatStore.fetchSessions()
  if (sessionId.value === null && sessions.value.length) {
    await agentChatStore.switchSession(sessions.value[0].session_id)
    return
  }
  await agentChatStore.ensureSession()
}

onBeforeUnmount(() => {
  controller?.abort()
  if (scrollFrame !== null) window.cancelAnimationFrame(scrollFrame)
})

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) messageListRef.value.scrollTop = messageListRef.value.scrollHeight
}

function scheduleScroll() {
  if (scrollFrame !== null) return
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = null
    void scrollToBottom()
  })
}

function requestFilters(): AgentFilters {
  return compactAgentFilters(props.filters)
}

function filterValuesEqual(previous: unknown, current: unknown): boolean {
  if (Object.is(previous, current)) return true
  if (
    (Array.isArray(previous) && Array.isArray(current))
    || (
      previous !== null
      && current !== null
      && typeof previous === 'object'
      && typeof current === 'object'
    )
  ) {
    return JSON.stringify(previous) === JSON.stringify(current)
  }
  return false
}

/** 搜索栏相对稳定快照的有值变化；只把这些字段作为本轮明确结构化输入。 */
function deriveTurnFilterDelta(previous: AgentFilters, current: AgentFilters): AgentFilters {
  const delta: Record<string, unknown> = {}
  for (const [field, value] of Object.entries(current)) {
    if (!filterValuesEqual(previous[field as AgentFilterField], value)) delta[field] = value
  }
  return compactAgentFilters(delta)
}

function removeActiveTurn(): void {
  if (activeTurnStartIndex !== null) messages.value.splice(activeTurnStartIndex, 2)
}

async function requestStop(): Promise<void> {
  if (!sending.value || stopRequested.value || !activeRequestId || sessionId.value === null) return
  stopRequested.value = true
  try {
    const result = await agentService.stopMessageStream(sessionId.value, activeRequestId)
    if (result.outcome === 'rolled_back') {
      removeActiveTurn()
      controller?.abort()
      ElMessage.info('已停止，本轮未修改筛选结果')
    } else if (result.outcome === 'pending') {
      ElMessage.info('正在完成已开始的筛选，之后将停止生成说明')
    }
  } catch {
    stopRequested.value = false
    ElMessage.warning('停止请求未成功，请重试')
  }
}

async function send(
  preset?: string,
  contextPatch?: Record<string, unknown>,
  guidedClearFields: AgentFilterField[] = [],
) {
  const text = (preset ?? inputText.value).trim()
  if (!text || unavailable.value || sessionId.value === null) return

  const compareIds = isComparisonRequest(text) ? comparisonCandidateIds.value : undefined
  if (isComparisonRequest(text) && (!compareIds || compareIds.length < 2)) {
    ElMessage.warning('请先让 AI 推荐或在候选清单中准备至少 2 个具体户型')
    return
  }

  activeTurnStartIndex = messages.value.length
  const userMessage: AgentChatMessage = { role: 'user', content: text }
  messages.value.push(userMessage)
  const assistantMessage = agentChatStore.appendStreamingAssistant()
  if (preset === undefined) inputText.value = ''
  sending.value = true
  stopRequested.value = false
  activeRequestId = globalThis.crypto?.randomUUID?.()
    || `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`
  controller = new AbortController()
  await scrollToBottom()

  const finalMeta: AgentStreamMeta = {}
  const currentRequestFilters = compactAgentFilters({
    ...requestFilters(),
    ...(contextPatch || {}),
  })
  const requestContext = compactAgentFilters(submittedFilterSnapshot.value)
  const turnFilterDelta = deriveTurnFilterDelta(requestContext, currentRequestFilters)
  const clearFields = deriveClearedFilterFields(
    requestContext,
    currentRequestFilters,
  )
  for (const field of guidedClearFields) {
    if (!clearFields.includes(field)) clearFields.push(field)
  }
  for (const field of props.pendingClearedFilters || []) {
    if (!clearFields.includes(field)) clearFields.push(field)
  }
  let previewFilterSignature = ''
  let previewRecommendationSignature = ''

  const applySearchPreview = (meta: AgentStreamMeta): void => {
    const startsNewTask = meta.task_boundary?.relation === 'new'
    const resetsCurrentTask = meta.task_boundary?.relation === 'continue'
      && Boolean(meta.task_boundary.reset_fields.length)
    const synchronizedFilters = meta.state_summary
      ? compactAgentFilters(meta.state_summary.filters as AgentFilters)
      : null
    const filterPatch: Record<string, unknown> = synchronizedFilters
      ? { ...synchronizedFilters }
      : meta.filter_patch || {}
    const clearedFilters = startsNewTask || resetsCurrentTask
      ? [...new Set<AgentFilterField>([
          ...deriveClearedFilterFields(currentRequestFilters, synchronizedFilters || {}),
          ...(meta.task_boundary?.reset_fields || []),
          ...(meta.cleared_filters || []),
        ])]
      : meta.cleared_filters || []
    const recommendations = uniqueRecommendations(
      meta.recommendations?.length ? meta.recommendations : meta.top_picks,
    )
    previewRecommendationSignature = recommendations
      .map((item) => item.property_id)
      .join(',')
    emit(
      'show-recommendations',
      recommendations,
      Math.max(Number(meta.recommendation_total || 0), recommendations.length),
    )

    if (Object.keys(filterPatch).length || clearedFilters.length) {
      previewFilterSignature = JSON.stringify([filterPatch, [...clearedFilters].sort()])
      emit('apply-filter-patch', filterPatch, true, clearedFilters)
    }
  }
  try {
    await agentService.sendMessageStream(
      sessionId.value,
      {
        message: text,
        context_filters: requestContext,
        ...(Object.keys(turnFilterDelta).length ? { filters: turnFilterDelta } : {}),
        ...(clearFields.length ? { clear_fields: clearFields } : {}),
        compare_property_ids: compareIds,
        request_id: activeRequestId,
      },
      {
        onToken(token) {
          if (stopRequested.value) return
          assistantMessage.content += token
          scheduleScroll()
        },
        onMeta(meta) {
          Object.assign(finalMeta, meta)
          applyMeta(assistantMessage, meta)
          if (meta.event === 'search_results') applySearchPreview(meta)
          if (meta.stop_outcome === 'results_kept') {
            assistantMessage.content = '已停止生成说明，筛选结果已保留。'
          }
          scheduleScroll()
        },
        onError(message) {
          if (!assistantMessage.content) assistantMessage.content = `抱歉，${message}`
        },
      },
      controller.signal,
    )

    if (!assistantMessage.content && finalMeta.stop_outcome !== 'rolled_back') {
      assistantMessage.content = '这次没有生成有效回复，请换一种说法再试。'
    }
    const recommendations = uniqueRecommendations(
      finalMeta.recommendations?.length ? finalMeta.recommendations : finalMeta.top_picks,
    )
    const startsNewTask = finalMeta.task_boundary?.relation === 'new'
    const clarifiesTask = finalMeta.task_boundary?.relation === 'clarify'
    const resetsCurrentTask = finalMeta.task_boundary?.relation === 'continue'
      && Boolean(finalMeta.task_boundary.reset_fields.length)
    const replacesTaskState = startsNewTask || resetsCurrentTask
    // 非澄清回复以服务端完整状态为准，确保右侧已识别条件稳定同步到左侧筛选栏。
    const synchronizedFilters = !clarifiesTask && finalMeta.state_summary
      ? compactAgentFilters(finalMeta.state_summary.filters as AgentFilters)
      : null
    const filterPatch: Record<string, unknown> = synchronizedFilters
      ? { ...synchronizedFilters }
      : finalMeta.filter_patch || {}
    let clearedFilters: AgentFilterField[] = []
    if (replacesTaskState) {
      clearedFilters = [...new Set<AgentFilterField>([
        ...deriveClearedFilterFields(currentRequestFilters, synchronizedFilters || {}),
        ...(finalMeta.task_boundary?.reset_fields || []),
        ...(finalMeta.cleared_filters || []),
      ])]
    } else if (!clarifiesTask) {
      clearedFilters = finalMeta.cleared_filters || []
    }
    if (Object.keys(filterPatch).length || clearedFilters.length) {
      const finalFilterSignature = JSON.stringify([filterPatch, [...clearedFilters].sort()])
      if (finalFilterSignature !== previewFilterSignature) {
        emit('apply-filter-patch', filterPatch, true, clearedFilters)
      }
    }
    submittedFilterSnapshot.value = mergeAgentFilterSnapshot(
      currentRequestFilters,
      // 左侧搜索栏会通过 props 回传已应用 patch；这里不提前记入面板
      // 无法表达的字段（如 area_min），避免下一轮把它误判为 UI 清除。
      {},
      clearedFilters,
    )
    if (recommendations.length) {
      const finalRecommendationSignature = recommendations
        .map((item) => item.property_id)
        .join(',')
      if (finalRecommendationSignature !== previewRecommendationSignature) {
        emit(
          'show-recommendations',
          recommendations,
          Math.max(Number(finalMeta.recommendation_total || 0), recommendations.length),
        )
      }
    }
    if (props.pendingClearedFilters?.length) {
      emit('clear-filters-consumed', [...props.pendingClearedFilters])
    }
    if (finalMeta.cart_changed) await cartStore.fetch()
  } catch (error) {
    if (controller.signal.aborted) return
    const reason = error instanceof Error ? error.message : '请求没有成功，请稍后再试'
    assistantMessage.content = assistantMessage.content
      ? `${assistantMessage.content}\n\n（连接中断：${reason}）`
      : `抱歉，${reason}`
  } finally {
    assistantMessage.streaming = false
    sending.value = false
    stopRequested.value = false
    activeRequestId = null
    activeTurnStartIndex = null
    controller = null
    void agentChatStore.fetchSessions()
    await scrollToBottom()
  }
}

function isComparisonRequest(text: string): boolean {
  return /(这几套|这些房|哪套|哪个好|怎么选|对比|比较)/i.test(text)
}

function currentStep(message: AgentChatMessage): ThinkingStep | null {
  const steps = message.thinkingSteps || []
  return steps.find((step) => step.status === 'running') || steps[steps.length - 1] || null
}

const STREAM_STEP_NAMES: Record<string, string> = {
  understanding: '理解需求',
  searching: '检索房源',
  comparing: '对比户型',
  generating: '生成回复',
}

function applyStreamStatus(message: AgentChatMessage, meta: AgentStreamMeta): void {
  if (meta.event === 'status' && meta.status && meta.message) {
    const completed = (message.thinkingSteps || []).map((step) => (
      step.status === 'running' ? { ...step, status: 'success' as const } : step
    ))
    message.thinkingSteps = [
      ...completed,
      {
        agent_id: `stream-${meta.status}`,
        agent_name: STREAM_STEP_NAMES[meta.status] || '处理中',
        status: 'running',
        summary: meta.message,
        duration_ms: 0,
      },
    ]
  } else if (meta.event === 'result' && message.thinkingSteps?.length) {
    message.thinkingSteps = message.thinkingSteps.map((step) => (
      step.status === 'running' ? { ...step, status: 'success' as const } : step
    ))
  }
}

function applyMeta(message: AgentChatMessage, meta: AgentStreamMeta) {
  if (meta.thinking_steps?.length) message.thinkingSteps = meta.thinking_steps
  applyStreamStatus(message, meta)

  const previousTaskBoundary = message.taskBoundary
  if (meta.task_boundary) message.taskBoundary = meta.task_boundary
  const startsNewTask = meta.task_boundary?.relation === 'new'
    && !(
      previousTaskBoundary?.relation === 'new'
      && previousTaskBoundary.task_id === meta.task_boundary.task_id
    )
  const resetsCurrentTask = meta.task_boundary?.relation === 'continue'
    && Boolean(meta.task_boundary.reset_fields.length)
  if (startsNewTask || resetsCurrentTask) {
    selectedCompareIds.value = []
  }

  const allRecommendations = uniqueAgentRecommendations(
    meta.recommendations?.length ? meta.recommendations : meta.top_picks,
  )
  const recommendations = visibleAgentRecommendations(allRecommendations)
  const responseTotal = Number(meta.recommendation_total)
  message.recommendationTotal = Number.isInteger(responseTotal) && responseTotal >= 0
    ? Math.max(responseTotal, allRecommendations.length)
    : allRecommendations.length
  if (recommendations.length) {
    message.recommendations = recommendations
    message.allRecommendations = recommendations
  }
  if (meta.ai_available !== undefined) message.aiAvailable = meta.ai_available
  if (meta.quick_replies) message.quickReplies = meta.quick_replies
  if (meta.links) message.links = meta.links
  if (meta.guided_options) message.guidedOptions = meta.guided_options
  if (meta.state_summary) message.stateSummary = meta.state_summary
  if (meta.turn_summary) message.turnSummary = meta.turn_summary
  if (meta.query_rewrite) message.queryRewrite = meta.query_rewrite
  if (meta.sources) message.sources = meta.sources
  if (meta.filter_patch) message.filterPatch = meta.filter_patch
  if (meta.cleared_filters) message.clearedFilters = meta.cleared_filters
}

function uniqueRecommendations(
  recommendations: AgentRecommendation[] | null | undefined,
): AgentRecommendation[] {
  return visibleAgentRecommendations(recommendations)
}

function recommendationCount(message: AgentChatMessage): number {
  return Math.max(
    Number(message.recommendationTotal || 0),
    uniqueAgentRecommendations(message.allRecommendations || message.recommendations).length,
  )
}

function visibleRequirementChips(summary?: AgentChatMessage['stateSummary']): Array<{ key: string; label: string }> {
  return (summary?.chips || []).slice(0, 10)
}

function applyGuidedOption(option: GuidedOption) {
  const clearFields = option.clear_fields || []
  if (option.filter_patch || clearFields.length) {
    emit('apply-filter-patch', option.filter_patch || {}, false, clearFields)
  }
  // 学校名解析需要异步地理编码；本轮请求直接合并 patch，避免发送时读到旧 props。
  void send(option.message || option.label, option.filter_patch || undefined, clearFields)
}

function toggleCompare(propertyId: number, checked: boolean) {
  if (checked) {
    if (!selectedCompareIds.value.includes(propertyId) && selectedCompareIds.value.length < 5) {
      selectedCompareIds.value = [...selectedCompareIds.value, propertyId]
    } else if (selectedCompareIds.value.length >= 5) {
      ElMessage.warning('一次最多对比 5 个具体户型')
    }
    return
  }
  selectedCompareIds.value = selectedCompareIds.value.filter((id) => id !== propertyId)
}

function openCompare(ids: number[]) {
  const validIds = [...new Set(ids)]
    .map(Number)
    .filter((id) => Number.isInteger(id) && id > 0)
    .slice(0, 5)
  if (validIds.length < 2) {
    ElMessage.warning('请至少选择 2 个具体户型进行对比')
    return
  }
  void router.push({ name: 'compare', query: { ids: validIds.join(',') } })
}

async function handleToggleCart(recommendation: AgentRecommendation) {
  try {
    if (cartStore.has(recommendation.property_id)) {
      await cartStore.remove(recommendation.property_id)
      ElMessage.info('已从候选清单移出')
    } else {
      await cartStore.add(recommendation.property_id, recommendation.match_reason || undefined)
      ElMessage.success('已加入候选清单')
    }
  } catch {
    // 接口错误由统一拦截器提示。
  }
}

function openProperty(propertyId: number, emittedInstituteId?: number) {
  const recommendation = messages.value
    .flatMap((message) => message.recommendations || [])
    .find((item) => item.property_id === propertyId)
  const instituteId = Number(emittedInstituteId || recommendation?.property.institute_id)
  if (Number.isInteger(instituteId) && instituteId > 0) {
    void router.push({
      name: 'building-detail',
      params: { id: instituteId },
      query: { unit_type_id: String(propertyId) },
    })
  } else {
    void router.push({
      name: 'property-detail',
      params: { id: propertyId },
      query: { unit_type_id: String(propertyId) },
    })
  }
}

function openAgentLink(to: string) {
  const match = to.match(/^\/(?:property|room)\/(\d+)(?:[/?#]|$)/)
  if (match) {
    openProperty(Number(match[1]))
    return
  }
  void router.push(to)
}
</script>

<style scoped>
.agent-panel {
  height: 100%; min-height: 0; display: flex; flex-direction: column;
  background: #fff; border: 1px solid #dfe4ea; border-radius: 12px; overflow: hidden;
}
.agent-header {
  min-height: 64px; padding: 10px 10px 10px 14px; display: flex;
  align-items: center; justify-content: space-between; border-bottom: 1px solid #ebeef2;
}
.agent-title { display: flex; align-items: center; gap: 9px; min-width: 0; }
.agent-title > div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.agent-title strong { color: #303133; font-size: 14px; }
.agent-title span { color: #909399; font-size: 11px; }
.agent-header-actions { display: flex; align-items: center; gap: 6px; flex: 0 0 auto; }
.agent-header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.agent-action-button {
  width: 32px; height: 32px; padding: 0; border-color: #dfe5ec; border-radius: 9px;
  color: #667085; background: #f8fafc;
}
.agent-action-button:not(.is-disabled):hover,
.agent-action-button:not(.is-disabled):focus-visible {
  color: #337ecc; border-color: #b8d7f5; background: #ecf5ff;
}
.agent-icon {
  width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center;
  color: #fff; background: linear-gradient(135deg, #409eff, #7a7cff); border-radius: 10px;
}
.memory-row span, .requirement-summary i {
  padding: 2px 7px; color: #35658f; background: #fff; border: 1px solid #d8e6f3;
  border-radius: 999px; font-size: 10px; font-style: normal;
}
.requirement-summary {
  display: flex; flex-direction: column; gap: 5px;
}
.requirement-summary > span {
  color: #7a8594; font-size: 10px; font-weight: 700;
}
.requirement-summary > div {
  display: flex; flex-wrap: wrap; gap: 4px;
}
.requirement-summary.overall {
  padding: 9px 12px; border-bottom: 1px solid #edf0f3; background: #f8fbf7;
}
.requirement-summary.overall i {
  color: #3f6a45; border-color: #d9eadc; background: #fff;
}
.requirement-summary.turn {
  width: fit-content; max-width: 88%; margin-top: 6px; padding: 7px 8px;
  background: #fbfcfe; border: 1px solid #e4ebf2; border-radius: 8px;
}
.requirement-summary.turn i {
  color: #606266; background: #f5f7fa; border-color: #e4e7ed;
}
.entity-note {
  margin: 8px 10px 0; padding: 7px 9px; display: flex; gap: 6px; align-items: flex-start;
  color: #7a5d20; background: #fff9e8; border: 1px solid #fae4a3; border-radius: 7px;
  font-size: 10.5px; line-height: 1.45;
}
.message-list { flex: 1; min-height: 0; overflow-y: auto; padding: 10px; }
.welcome-panel {
  margin-bottom: 12px; padding: 12px; display: flex; flex-direction: column; gap: 6px;
  background: linear-gradient(135deg, #f4f8ff, #faf8ff); border: 1px solid #dfe9fa; border-radius: 10px;
}
.welcome-panel > strong { color: #303133; font-size: 13px; }
.welcome-panel > span { color: #77808c; font-size: 11px; line-height: 1.5; }
.welcome-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 5px; }
.welcome-actions button {
  padding: 9px; display: flex; align-items: center; gap: 7px; text-align: left;
  color: #3c5f85; background: #fff; border: 1px solid #d8e4f2; border-radius: 8px; cursor: pointer;
}
.welcome-actions button:disabled { cursor: not-allowed; opacity: .5; }
.welcome-actions span { display: flex; flex-direction: column; min-width: 0; }
.welcome-actions b { color: #334155; font-size: 11px; }
.welcome-actions small { color: #9099a5; font-size: 9.5px; }
.message-block { margin-bottom: 12px; }
.bubble-row { display: flex; margin-top: 6px; }
.bubble-row.user { justify-content: flex-end; }
.bubble {
  max-width: 88%; padding: 8px 10px; border-radius: 10px; white-space: pre-wrap;
  color: #3b4350; background: #f1f3f6; font-size: 12px; line-height: 1.55;
}
.bubble.user { color: #fff; background: #409eff; border-bottom-right-radius: 3px; }
.bubble.assistant { border-bottom-left-radius: 3px; }
.bubble.typing { display: flex; align-items: center; gap: 6px; color: #7d8794; }
.processing-chip {
  width: fit-content; margin-top: 6px; padding: 3px 8px; display: flex; align-items: center; gap: 5px;
  color: #35658f; background: #edf6ff; border: 1px solid #d5e8f8; border-radius: 999px;
  font-size: 10.5px;
}
.recommendation-group { margin-bottom: 8px; padding: 9px; background: #f8fafc; border: 1px solid #e6ebf1; border-radius: 10px; }
.recommendation-head { margin-bottom: 7px; display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.recommendation-head > div { display: flex; flex-direction: column; gap: 2px; }
.recommendation-head strong { color: #303133; font-size: 12px; }
.recommendation-head span { color: #909399; font-size: 10px; }
.recommendation-row { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 5px; scroll-snap-type: x mandatory; }
.compare-selection { margin-top: 7px; display: flex; align-items: center; gap: 5px; }
.compare-selection > span { margin-right: auto; color: #606266; font-size: 11px; }
.memory-row, .quick-row { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 5px; }
.quick-row button {
  padding: 4px 8px; color: #337ecc; background: #ecf5ff; border: 1px solid #c6e2ff;
  border-radius: 999px; font-size: 10.5px; cursor: pointer;
}
.quick-row button:disabled { cursor: not-allowed; opacity: .5; }
.composer { padding: 9px 10px 10px; border-top: 1px solid #ebeef2; background: #fff; }
.faq-row { margin-bottom: 7px; display: flex; gap: 5px; overflow-x: auto; }
.faq-row button {
  flex: 0 0 auto; padding: 3px 7px; color: #606266; background: #f5f7fa;
  border: 1px solid #e4e7ed; border-radius: 999px; font-size: 10px; cursor: pointer;
}
.composer-row { display: flex; align-items: flex-end; gap: 7px; }
.composer-row :deep(.el-textarea) { flex: 1; }
.composer-row :deep(.el-textarea__inner) { font-size: 12px; }
.send-btn { flex: 0 0 auto; margin-bottom: 2px; }
.stop-square { width: 10px; height: 10px; border-radius: 2px; background: currentColor; }
</style>
