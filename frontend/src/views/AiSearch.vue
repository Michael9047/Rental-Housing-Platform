<!-- AI 找房主页面：多会话、长期偏好、流式状态与 UnitType 推荐卡。 -->
<template>
  <div class="ai-search-page">
    <button
      v-if="mobileSidebarOpen"
      class="mobile-sidebar-backdrop"
      type="button"
      aria-label="关闭对话记录"
      @click="mobileSidebarOpen = false"
    />

    <aside class="session-sidebar" :class="{ 'mobile-open': mobileSidebarOpen }">
      <div class="session-head">
        <strong>对话记录</strong>
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          :loading="creatingSession"
          @click="startNewSession"
        >
          新对话
        </el-button>
      </div>

      <div v-loading="loadingHistory" class="session-list">
        <button
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: session.session_id === sessionId }"
          type="button"
          @click="openSession(session.session_id)"
        >
          <span class="session-title">{{ sessionTitle(session) }}</span>
          <span class="session-time">{{ relativeTime(session.updated_at) }}</span>
        </button>
        <el-empty v-if="!sessions.length" :image-size="48" description="暂无历史对话" />
      </div>

      <section class="memory-card">
        <div class="memory-card-head">
          <span><el-icon><CollectionTag /></el-icon> 长期偏好</span>
          <el-button
            v-if="memoryChips.length"
            text
            type="danger"
            size="small"
            :loading="savingMemory"
            @click="clearSavedMemory"
          >
            清空
          </el-button>
        </div>
        <p v-if="!memoryChips.length">保存后，新对话也会沿用你的地区、预算和户型偏好。</p>
        <div v-else class="memory-chip-list">
          <span v-for="chip in memoryChips" :key="chip">{{ chip }}</span>
        </div>
      </section>
    </aside>

    <main class="chat-main">
      <header class="chat-header">
        <div class="chat-heading">
          <el-button
            class="mobile-history-button"
            circle
            :icon="ChatLineSquare"
            aria-label="打开对话记录与长期偏好"
            @click="mobileSidebarOpen = true"
          />
          <div>
            <h1><el-icon><MagicStick /></el-icon> AI 智能找房</h1>
            <p>基于 main 的公寓与户型数据，结合当前对话和已保存偏好继续回答</p>
          </div>
        </div>
        <div class="chat-header-actions">
          <el-button
            :icon="Search"
            :disabled="sessionId === null || sending"
            @click="openSearchResults"
          >
            查看搜索结果
          </el-button>
          <el-button
            :icon="CollectionTag"
            :loading="savingMemory"
            :disabled="!savableMemory"
            @click="saveCurrentMemory"
          >
            保存本次偏好
          </el-button>
        </div>
      </header>

      <div ref="chatAreaRef" class="chat-area" aria-live="polite">
        <div v-if="loadingHistory" class="history-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          正在载入对话记录
        </div>

        <template v-else>
          <article
            v-for="(message, index) in messages"
            :key="message.id || `${message.role}-${index}`"
            class="message-block"
            :class="message.role"
          >
            <section
              v-if="message.role === 'assistant' && message.recommendations?.length"
              class="recommendation-shell"
            >
              <div class="recommendation-head">
                <strong>
                  共有 {{ recommendationCount(message) }} 个可选户型
                </strong>
                <span>
                  当前展示前 {{ message.recommendations.length }} 个 · 左右滑动查看
                </span>
              </div>
              <div v-horizontal-wheel-scroll v-sync-match-reason-heights class="recommendation-row">
                <RecPropertyCard
                  v-for="recommendation in message.recommendations"
                  :key="recommendation.property_id"
                  :rec="recommendation"
                  :selected="selectedIds.includes(recommendation.property_id)"
                  :in-cart="cartStore.has(recommendation.property_id)"
                  @toggle-compare="toggleCompare"
                  @toggle-cart="toggleCart"
                  @detail="goDetail"
                />
              </div>
            </section>

            <div class="bubble-row">
              <div class="message-bubble" :class="message.role">
                <span v-if="message.role === 'assistant'" class="assistant-label">AI 管家</span>
                <span class="message-text">
                  {{ message.content || (message.streaming ? '正在理解你的需求…' : '') }}
                </span>
              </div>
            </div>

            <div
              v-if="message.role === 'assistant' && message.streaming && currentStep(message)"
              class="processing-note"
            >
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ currentStep(message)?.agent_name }}：{{ currentStep(message)?.summary || '正在处理' }}
            </div>

            <div
              v-if="message.role === 'assistant' && message.aiAvailable === false"
              class="degraded-note"
            >
              当前 AI 分析服务不可用，本轮结果由结构化检索提供。
            </div>

            <div
              v-if="message.role === 'assistant' && message.isWelcome"
              class="welcome-actions"
              aria-label="开始使用 AI 租房管家"
            >
              <button
                v-for="action in welcomeActions"
                :key="action.title"
                type="button"
                :disabled="sending"
                @click="send(action.prompt)"
              >
                <span class="welcome-action-icon" aria-hidden="true">{{ action.icon }}</span>
                <span class="welcome-action-copy">
                  <strong>{{ action.title }}</strong>
                  <small>{{ action.description }}</small>
                </span>
                <span class="welcome-action-arrow" aria-hidden="true">→</span>
              </button>
            </div>

            <div
              v-if="message.role === 'assistant'
                && message.queryRewrite
                && message.queryRewrite.rewritten !== message.queryRewrite.original"
              class="understanding-note"
            >
              我理解为：{{ message.queryRewrite.rewritten }}
            </div>

            <div
              v-if="message.role === 'assistant' && message.stateSummary?.chips.length"
              class="state-row"
            >
              <span class="row-label">本轮记住</span>
              <span v-for="chip in message.stateSummary.chips" :key="chip.key">{{ chip.label }}</span>
            </div>

            <div
              v-if="message.role === 'assistant' && message.sources?.length"
              class="source-row"
            >
              <span class="row-label">数据依据</span>
              <span
                v-for="source in message.sources"
                :key="`${source.label}-${source.status}`"
                :class="{ missing: source.status === 'missing' }"
              >
                {{ source.label }}{{ source.status === 'missing' ? '待补充' : '已核验' }}
              </span>
            </div>

            <div
              v-if="message.role === 'assistant' && message.guidedOptions?.length"
              class="quick-row"
            >
              <span class="row-label">继续调整</span>
              <button
                v-for="option in message.guidedOptions"
                :key="`${option.kind}-${option.label}`"
                type="button"
                :disabled="sending"
                @click="applyGuidedOption(option)"
              >
                {{ option.icon }} {{ option.label }}
              </button>
            </div>

            <div
              v-if="message.role === 'assistant' && message.quickReplies?.length"
              class="quick-row"
            >
              <button
                v-for="reply in message.quickReplies"
                :key="reply"
                type="button"
                :disabled="sending"
                @click="send(reply)"
              >
                {{ reply }}
              </button>
            </div>

            <div
              v-if="message.role === 'assistant' && message.links?.length"
              class="quick-row link-row"
            >
              <el-button
                v-for="link in message.links"
                :key="`${link.to}-${link.label}`"
                size="small"
                type="primary"
                plain
                @click="openAgentLink(link.to)"
              >
                {{ link.label }} →
              </el-button>
            </div>
          </article>
        </template>
      </div>

      <div v-if="selectedIds.length" class="compare-bar">
        <span>已选 {{ selectedIds.length }} 个户型（最多 5 个）</span>
        <el-button
          class="open-compare-workspace"
          size="small"
          type="primary"
          :disabled="selectedIds.length < 2"
          aria-label="打开综合对比工作台"
          @click="openCompareWorkspace"
        >
          打开综合对比
        </el-button>
        <el-button
          size="small"
          :disabled="selectedIds.length < 2"
          @click="askToCompare"
        >
          在对话中比较
        </el-button>
        <el-button size="small" text @click="selectedIds = []">清空</el-button>
      </div>

      <footer class="composer">
        <div class="faq-row" aria-label="常见问题快捷入口">
          <span>常见问题</span>
          <button
            v-for="faq in faqChips"
            :key="faq.id"
            type="button"
            :disabled="sending"
            @click="send(faqPrompt(faq))"
          >
            {{ faqLabel(faq) }}
          </button>
        </div>
        <div class="composer-row">
          <el-input
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 6 }"
            :maxlength="20000"
            show-word-limit
            resize="none"
            :disabled="sending || loadingHistory"
            placeholder="描述需求，或继续问「刚才第二个户型离学校多远？」（Shift+Enter 换行）"
            @keydown="handleComposerKeydown"
          />
          <el-button
            class="send-button"
            type="primary"
            :icon="Promotion"
            :loading="sending"
            :disabled="!inputText.trim() || loadingHistory"
            @click="send()"
          >
            发送
          </el-button>
        </div>
      </footer>
    </main>

    <el-dialog
      v-model="compareWorkspaceOpen"
      class="compare-workspace-dialog"
      modal-class="compare-workspace-modal"
      aria-label="综合对比工作台"
      width="94vw"
      :z-index="3200"
      :show-close="false"
      :close-on-click-modal="false"
      :destroy-on-close="false"
      append-to-body
    >
      <CompareWorkspace
        mode="overlay"
        :initial-ids="workspaceIds"
        @close="closeCompareWorkspace"
        @open-new-page="openCompareInNewPage"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  ChatLineSquare,
  CollectionTag,
  Loading,
  MagicStick,
  Plus,
  Promotion,
  Search,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import RecPropertyCard from '@/components/RecPropertyCard.vue'
import { vHorizontalWheelScroll } from '@/directives/horizontalWheelScroll'
import { vSyncMatchReasonHeights } from '@/directives/syncMatchReasonHeights'
import CompareWorkspace from '@/components/compare/CompareWorkspace.vue'
import { agentService } from '@/services/agent'
import {
  uniqueAgentRecommendations,
  visibleAgentRecommendations,
} from '@/utils/agentRecommendations'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'
import type {
  AgentChatMessage,
  AgentFilterField,
  AgentFilters,
  AgentRecommendation,
  AgentSessionSummary,
  AgentSearchWorkspace,
  AgentStreamMeta,
  FaqChip,
  GuidedOption,
  ThinkingStep,
} from '@/types/agent'

const route = useRoute()
const router = useRouter()
const agentChat = useAgentChatStore()
const cartStore = useCartStore()
const {
  sessionId,
  messages,
  sessions,
  loadingHistory,
  rememberedPreferences,
  aiAvailable,
} = storeToRefs(agentChat)

const inputText = ref('')
const sending = ref(false)
const creatingSession = ref(false)
const savingMemory = ref(false)
const mobileSidebarOpen = ref(false)
const chatAreaRef = ref<HTMLElement | null>(null)
const selectedIds = ref<number[]>([])
const workspaceIds = ref<number[]>([])
const compareWorkspaceOpen = ref(false)
const localFilters = reactive<AgentFilters>({})

const currentSessionSummary = computed(() => (
  sessions.value.find((session) => session.session_id === sessionId.value) || null
))

let scrollFrame: number | null = null
let activeStream: AbortController | null = null

const FILTER_KEYS = new Set<keyof AgentFilters>([
  'country',
  'currency',
  'city',
  'district',
  'institute_id',
  'institution',
  'price_min',
  'price_max',
  'bedrooms',
  'bathrooms',
  'property_type',
  'room_type',
  'amenities',
  'area_min',
  'area_max',
  'min_lease_months',
  'max_lease_months',
  'available_from',
  'female_only',
  'commute_mode',
  'commute_minutes',
  'poi_requirements',
])

const welcomeActions = [
  {
    title: '开始找房',
    description: '按学校、地区、预算和户型逐步收窄',
    icon: '⌂',
    prompt: '我想找房，请先引导我补充学校或地区、预算和户型。',
  },
  {
    title: '对比户型',
    description: '比较租金、通勤、面积和公寓设施',
    icon: '⇄',
    prompt: '请先推荐几个适合我的户型，再帮我比较租金、通勤、面积和公寓设施。',
  },
]

const faqChips = ref<FaqChip[]>([
  { id: 'find_house', chip: '如何找房' },
  { id: 'contract', chip: '合同怎么签' },
  { id: 'booking', chip: '预订流程' },
  { id: 'deposit', chip: '押金怎么退' },
  { id: 'fees', chip: '有哪些费用' },
])

function faqLabel(faq: FaqChip): string {
  if (faq.id === 'find_house') return '我要找房'
  if (faq.id === 'contract') return '合同如何签'
  return faq.chip
}

function faqPrompt(faq: FaqChip): string {
  if (faq.id === 'find_house') return '我要找房'
  if (faq.id === 'contract') return '合同如何签'
  return faq.chip
}

const latestStateFilters = computed<AgentFilters>(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const summary = messages.value[index].stateSummary
    if (summary) return (summary.filters || {}) as AgentFilters
  }
  return {}
})

function hasFilterValue(value: unknown): boolean {
  return value !== null
    && value !== undefined
    && value !== ''
    && (!Array.isArray(value) || value.length > 0)
}

function cleanFilters(filters: AgentFilters): AgentFilters {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => hasFilterValue(value)),
  ) as AgentFilters
}

const preferenceSnapshot = computed<AgentFilters>(() => cleanFilters({
  ...localFilters,
  ...latestStateFilters.value,
}))

const savableMemory = computed(() => Object.keys(preferenceSnapshot.value).length > 0)
const memoryChips = computed(() => filterChips(rememberedPreferences.value))

function filterChips(filters: AgentFilters): string[] {
  const chips: string[] = []
  if (filters.country) chips.push(`国家/地区：${filters.country}`)
  if (filters.city) chips.push(`城市：${filters.city}`)
  if (filters.district) chips.push(`区域：${filters.district}`)
  if (filters.institution) chips.push(`学校/机构：${filters.institution}`)
  if (filters.price_min != null || filters.price_max != null) {
    const min = filters.price_min != null ? Number(filters.price_min).toLocaleString() : '不限'
    const max = filters.price_max != null ? Number(filters.price_max).toLocaleString() : '不限'
    const currency = filters.currency ? ` ${filters.currency}` : ''
    chips.push(`预算：${min}–${max}${currency}`)
  }
  if (filters.property_type) chips.push(`户型：${filters.property_type}`)
  else if (filters.room_type) chips.push(`户型：${filters.room_type}`)
  if (filters.bedrooms != null) chips.push(`${filters.bedrooms}室`)
  if (filters.amenities?.length) chips.push(...filters.amenities.slice(0, 4))
  if (filters.commute_minutes != null) chips.push(`通勤≤${filters.commute_minutes}分钟`)
  return [...new Set(chips)].slice(0, 10)
}

function sessionTitle(session: AgentSessionSummary): string {
  const candidate = session.last_message || session.title || '新对话'
  return candidate.replace(/\s+/g, ' ').slice(0, 24)
}

function relativeTime(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return ''
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}小时前`
  return new Date(timestamp).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
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

function recommendationCount(message: AgentChatMessage): number {
  return Math.max(
    Number(message.recommendationTotal || 0),
    message.allRecommendations?.length || 0,
    message.recommendations?.length || 0,
  )
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (chatAreaRef.value) chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
}

function scheduleScroll(): void {
  if (scrollFrame !== null) return
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = null
    void scrollToBottom()
  })
}

async function openSession(id: number): Promise<void> {
  if (sending.value) return
  try {
    await agentChat.switchSession(id)
    replaceLocalFilters(latestStateFilters.value as Record<string, unknown>)
    selectedIds.value = []
    mobileSidebarOpen.value = false
    await router.replace({
      name: 'ai-search',
      query: { ...route.query, session: String(id) },
    })
    await scrollToBottom()
  } catch {
    ElMessage.error('对话记录加载失败，请稍后重试')
  }
}

async function startNewSession(): Promise<void> {
  if (sending.value || creatingSession.value) return
  creatingSession.value = true
  try {
    await agentChat.newSession()
    replaceLocalFilters(rememberedPreferences.value as Record<string, unknown>)
    selectedIds.value = []
    inputText.value = ''
    mobileSidebarOpen.value = false
    if (sessionId.value !== null) {
      await router.replace({
        name: 'ai-search',
        query: { ...route.query, session: String(sessionId.value) },
      })
    }
    await scrollToBottom()
  } catch {
    ElMessage.error('新对话创建失败，请稍后重试')
  } finally {
    creatingSession.value = false
  }
}

async function openSearchResults(): Promise<void> {
  if (sessionId.value === null || sending.value) return
  try {
    let workspace = currentSessionSummary.value?.search_workspace || null
    if (!workspace) {
      const searchId = `ai-${Date.now()}-${sessionId.value}`
      workspace = {
        search_id: searchId,
        route_query: { search_id: searchId },
        manual_filters: {},
        ui_state: { search_mode: 'city', sort_by: 'created_at', view_mode: 'grid' },
      } satisfies AgentSearchWorkspace
      await agentChat.saveSearchWorkspace(workspace, sessionId.value)
    }
    await router.push({
      name: 'search',
      query: { ...workspace.route_query, search_id: workspace.search_id },
    })
  } catch {
    ElMessage.error('搜索状态准备失败，请稍后重试')
  }
}

function mergeFilterPatch(
  patch?: Record<string, unknown> | null,
  appendArrays = false,
): void {
  if (!patch) return
  const target = localFilters as Record<string, unknown>

  for (const [key, value] of Object.entries(patch)) {
    if (!FILTER_KEYS.has(key as keyof AgentFilters) || value === undefined) continue
    if (appendArrays && (key === 'amenities' || key === 'poi_requirements') && Array.isArray(value)) {
      const current = Array.isArray(target[key]) ? target[key] as unknown[] : []
      target[key] = [
        ...current,
        ...value.filter((item) => !current.some(
          (existing) => JSON.stringify(existing) === JSON.stringify(item),
        )),
      ]
      continue
    }
    target[key] = Array.isArray(value) ? [...value] : value
  }
}

/** 服务端确认清除后立即删除本地副本，避免下一轮 activeFilters 重新上报旧值。 */
function clearLocalFilters(fields: readonly AgentFilterField[]): void {
  const target = localFilters as Record<string, unknown>
  for (const field of fields) delete target[field]
}

/** 切换会话时完整替换筛选上下文，不能把上一会话条件继续带入。 */
function replaceLocalFilters(filters?: Record<string, unknown> | null): void {
  const target = localFilters as Record<string, unknown>
  for (const key of Object.keys(target)) delete target[key]
  mergeFilterPatch(filters)
}

function activeFilters(): AgentFilters | undefined {
  const filters = cleanFilters(localFilters)
  return Object.keys(filters).length ? filters : undefined
}

function applyMeta(message: AgentChatMessage, meta: AgentStreamMeta): void {
  if (meta.thinking_steps?.length) message.thinkingSteps = meta.thinking_steps
  applyStreamStatus(message, meta)
  if (meta.query_rewrite) message.queryRewrite = meta.query_rewrite
  if (meta.sources) message.sources = meta.sources

  const previousTaskBoundary = message.taskBoundary
  const incomingTaskBoundary = meta.task_boundary
  if (incomingTaskBoundary) message.taskBoundary = incomingTaskBoundary
  const taskBoundary = incomingTaskBoundary || message.taskBoundary
  const startsNewTask = taskBoundary?.relation === 'new'
  const resetsTaskCandidates = incomingTaskBoundary?.relation === 'continue'
    && Boolean(incomingTaskBoundary.reset_fields.length)
  const firstNewTaskBoundary = incomingTaskBoundary?.relation === 'new'
    && !(
      previousTaskBoundary?.relation === 'new'
      && previousTaskBoundary.task_id === incomingTaskBoundary.task_id
    )

  if (firstNewTaskBoundary || resetsTaskCandidates) {
    selectedIds.value = []
    workspaceIds.value = []
    compareWorkspaceOpen.value = false
    // 状态摘要稍后可能随 result 事件到达；届时会完整替换当前筛选。
    if (!meta.state_summary && incomingTaskBoundary) {
      clearLocalFilters(incomingTaskBoundary.reset_fields)
    }
  }

  if (meta.state_summary) {
    message.stateSummary = meta.state_summary
    // 澄清轮只询问必要信息，不应把尚未确认的摘要当作筛选重置。
    if (taskBoundary?.relation !== 'clarify') {
      replaceLocalFilters(meta.state_summary.filters)
    }
  }
  if (meta.guided_options) message.guidedOptions = meta.guided_options
  if (meta.quick_replies) message.quickReplies = meta.quick_replies
  if (meta.links) message.links = meta.links
  if (meta.filter_patch) {
    message.filterPatch = meta.filter_patch
    // 新任务的完整状态摘要优先，避免旧任务条件被增量 patch 重新带回。
    if (!(startsNewTask && message.stateSummary)) mergeFilterPatch(meta.filter_patch)
  }
  if (meta.cleared_filters) {
    message.clearedFilters = meta.cleared_filters
    if (
      taskBoundary?.relation !== 'clarify'
      && !(startsNewTask && message.stateSummary)
    ) {
      clearLocalFilters(meta.cleared_filters)
    }
  }
  if (meta.ai_available !== undefined) {
    message.aiAvailable = meta.ai_available
    aiAvailable.value = meta.ai_available
  }

  const allRecommendations = uniqueAgentRecommendations(meta.recommendations)
  const visibleRecommendations = visibleAgentRecommendations(allRecommendations)
  const topPicks = visibleAgentRecommendations(meta.top_picks)
  const responseTotal = Number(meta.recommendation_total)
  message.recommendationTotal = Number.isInteger(responseTotal) && responseTotal >= 0
    ? Math.max(responseTotal, allRecommendations.length)
    : allRecommendations.length || topPicks.length
  if (allRecommendations.length) {
    message.recommendations = visibleRecommendations
    message.allRecommendations = visibleRecommendations
    message.topPicks = topPicks.length ? topPicks : undefined
  } else if (topPicks.length) {
    message.recommendations = topPicks
    message.allRecommendations = topPicks
    message.topPicks = topPicks
  }
}

async function send(
  preset?: string,
  compareIds?: number[],
  guidedClearFields: AgentFilterField[] = [],
): Promise<void> {
  const text = (preset ?? inputText.value).trim()
  if (!text || sending.value || loadingHistory.value) return

  if (sessionId.value === null) {
    try {
      await agentChat.ensureSession()
    } catch {
      ElMessage.error('会话创建失败，请刷新后重试')
      return
    }
  }

  messages.value.push({ role: 'user', content: text })
  const assistantMessage = agentChat.appendStreamingAssistant()
  if (preset === undefined) inputText.value = ''
  sending.value = true
  await scrollToBottom()

  const controller = new AbortController()
  activeStream = controller

  try {
    await agentService.sendMessageStream(
      sessionId.value!,
      {
        message: text,
        context_filters: activeFilters(),
        clear_fields: guidedClearFields.length ? guidedClearFields : undefined,
        compare_property_ids: compareIds,
        mode: 'auto',
      },
      {
        onToken(token) {
          assistantMessage.content += token
          scheduleScroll()
        },
        onMeta(meta) {
          applyMeta(assistantMessage, meta)
          scheduleScroll()
        },
        onError(message) {
          if (!assistantMessage.content) assistantMessage.content = `抱歉，${message}`
        },
      },
      controller.signal,
    )
    if (!assistantMessage.content) {
      assistantMessage.content = '这次没有生成有效回复，请换一种说法再试。'
    }
  } catch (error) {
    if (!(error instanceof DOMException && error.name === 'AbortError')) {
      const reason = error instanceof Error ? error.message : '请求失败，请稍后再试'
      assistantMessage.content = assistantMessage.content
        ? `${assistantMessage.content}\n\n（连接中断：${reason}）`
        : `抱歉，${reason}`
    }
  } finally {
    assistantMessage.streaming = false
    if (activeStream === controller) activeStream = null
    sending.value = false
    void agentChat.fetchSessions()
    await scrollToBottom()
  }
}

function handleComposerKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  void send()
}

function applyGuidedOption(option: GuidedOption): void {
  const clearFields = option.clear_fields || []
  if (clearFields.length) clearLocalFilters(clearFields)
  mergeFilterPatch(option.filter_patch, true)
  void send(option.message || option.label, undefined, clearFields)
}

function toggleCompare(unitTypeId: number, checked: boolean): void {
  if (checked && selectedIds.value.includes(unitTypeId)) return
  if (checked && selectedIds.value.length >= 5) {
    ElMessage.warning('一次最多对比 5 个户型')
    return
  }
  if (checked) selectedIds.value.push(unitTypeId)
  else selectedIds.value = selectedIds.value.filter((id) => id !== unitTypeId)
}

function askToCompare(): void {
  if (selectedIds.value.length < 2) return
  void send(
    '请结合我前面说的需求，详细比较这些户型，并说明各自所属公寓和最适合的人群。',
    [...selectedIds.value],
  )
}

/** 在主 Agent 上层打开工作台，不打断当前对话。 */
function openCompareWorkspace(): void {
  if (selectedIds.value.length < 2) return
  workspaceIds.value = [...selectedIds.value]
  compareWorkspaceOpen.value = true
}

function closeCompareWorkspace(): void {
  compareWorkspaceOpen.value = false
}

/** 独立页用于分享、刷新和更宽松的浏览；主 Agent 保持在当前标签页。 */
function openCompareInNewPage(ids: number[]): void {
  const validIds = [...new Set(ids)].filter((id) => Number.isInteger(id) && id > 0).slice(0, 5)
  if (validIds.length < 2) return
  const href = router.resolve({
    name: 'compare',
    query: { ids: validIds.join(',') },
  }).href
  window.open(href, '_blank', 'noopener')
}

function recommendationTitle(recommendation: AgentRecommendation): string {
  const property = recommendation.property
  return property.name || property.unit_type_name || property.title || `户型 ${recommendation.property_id}`
}

async function toggleCart(recommendation: AgentRecommendation): Promise<void> {
  const title = recommendationTitle(recommendation)
  try {
    if (cartStore.has(recommendation.property_id)) {
      await cartStore.remove(recommendation.property_id)
      ElMessage.info(`已从候选清单移出「${title}」`)
    } else {
      await cartStore.add(recommendation.property_id, recommendation.match_reason || undefined)
      ElMessage.success(`已将「${title}」加入候选清单`)
    }
  } catch {
    // API 拦截器负责展示后端的具体错误。
  }
}

/** 详情使用 Institute ID；UnitType ID 仅作为 query 定位具体户型。 */
function goDetail(unitTypeId: number, instituteId?: number): void {
  if (instituteId) {
    void router.push({
      name: 'building-detail',
      params: { id: String(instituteId) },
      query: { unit_type_id: String(unitTypeId) },
    })
    return
  }

  // 极少数旧响应没有 institute_id，交给 main 的 UnitType → Building 适配路由解析。
  void router.push({
    name: 'property-detail',
    params: { id: String(unitTypeId) },
    query: { unit_type_id: String(unitTypeId) },
  })
}

/** 旧 Agent 可能返回 /property/:unitTypeId，不能让 router 将其误当 Building ID。 */
function openAgentLink(to: string): void {
  const match = to.match(/^\/(?:property|room)\/(\d+)(?:[/?#]|$)/)
  if (!match) {
    void router.push(to)
    return
  }

  const unitTypeId = Number(match[1])
  const recommendation = messages.value
    .flatMap((message) => message.recommendations || [])
    .find((item) => item.property_id === unitTypeId)
  const instituteId = Number(recommendation?.property.institute_id)
  goDetail(
    unitTypeId,
    Number.isInteger(instituteId) && instituteId > 0 ? instituteId : undefined,
  )
}

async function saveCurrentMemory(): Promise<void> {
  savingMemory.value = true
  try {
    await agentChat.saveMemory(preferenceSnapshot.value)
    ElMessage.success('已保存偏好，新对话也会继续参考')
  } catch {
    ElMessage.error('偏好保存失败，请稍后重试')
  } finally {
    savingMemory.value = false
  }
}

async function clearSavedMemory(): Promise<void> {
  savingMemory.value = true
  try {
    await agentChat.clearMemory()
    ElMessage.success('长期偏好已清空，当前对话条件仍然保留')
  } catch {
    ElMessage.error('长期偏好清空失败，请稍后重试')
  } finally {
    savingMemory.value = false
  }
}

onMounted(async () => {
  document.documentElement.classList.add('ai-search-page-active')

  // 游客首次进入时先创建 guest 会话并保存 token，再请求其余历史和偏好接口。
  if (!localStorage.getItem('access_token') && !localStorage.getItem('guest_token')) {
    try {
      await agentChat.ensureSession()
    } catch {
      ElMessage.error('AI 找房会话启动失败，请刷新后重试')
      return
    }
  }

  await Promise.allSettled([
    agentChat.fetchSessions(),
    agentChat.fetchMemory(),
    cartStore.fetch(),
    agentService.getFaqs().then((chips) => {
      if (chips.length) faqChips.value = chips
    }),
  ])

  try {
    const routeSessionId = typeof route.query.session === 'string'
      ? Number(route.query.session)
      : null
    const routeSessionExists = routeSessionId !== null
      && Number.isInteger(routeSessionId)
      && sessions.value.some((session) => session.session_id === routeSessionId)
    if (routeSessionExists) {
      await agentChat.switchSession(routeSessionId)
    } else if (sessionId.value === null && sessions.value.length) {
      await agentChat.switchSession(sessions.value[0].session_id)
    } else {
      await agentChat.ensureSession()
    }
    if (sessionId.value !== null && String(route.query.session || '') !== String(sessionId.value)) {
      await router.replace({
        name: 'ai-search',
        query: { ...route.query, session: String(sessionId.value) },
      })
    }
    const hasConversationState = messages.value.some((message) => !!message.stateSummary)
    replaceLocalFilters(
      (hasConversationState ? latestStateFilters.value : rememberedPreferences.value) as Record<string, unknown>,
    )
  } catch {
    ElMessage.error('AI 找房会话启动失败，请刷新后重试')
  }

  const routeQuery = typeof route.query.q === 'string' ? route.query.q.trim() : ''
  const pendingQuery = agentChat.consumeQuery()?.trim() || ''
  const initialQuery = routeQuery || pendingQuery
  if (initialQuery) await send(initialQuery)
  await scrollToBottom()
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('ai-search-page-active')
  activeStream?.abort()
  activeStream = null
  if (scrollFrame !== null) window.cancelAnimationFrame(scrollFrame)
})
</script>

<style scoped>
.ai-search-page {
  position: relative;
  width: 100%;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 224px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  overflow: hidden;
  border: 1px solid #e2e8ef;
  border-radius: 14px;
  background: #fff;
}

.session-sidebar { min-width: 0; min-height: 0; display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid #e5eaf0; background: #f7f9fc; }
.session-head { min-height: 56px; padding: 9px; display: flex; align-items: center; justify-content: space-between; gap: 8px; border-bottom: 1px solid #e5eaf0; }
.session-head strong { color: #2f3b4b; font-size: 14px; }
.session-list { flex: 1; min-height: 0; padding: 8px; overflow-y: auto; }
.session-item { width: 100%; margin-bottom: 4px; padding: 8px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 8px; text-align: left; border: 1px solid transparent; border-radius: 9px; background: transparent; cursor: pointer; }
.session-item:hover { background: #eef3f9; }
.session-item.active { border-color: #b9d2ea; background: #e8f2fc; }
.session-title { overflow: hidden; color: #334254; font-size: 11.5px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.session-time { color: #9ca6b2; font-size: 10px; white-space: nowrap; }

.memory-card { margin: 6px 8px 8px; padding: 9px; border: 1px solid #dce6f0; border-radius: 10px; background: #fff; }
.memory-card-head { display: flex; align-items: center; justify-content: space-between; color: #47617c; font-size: 12px; font-weight: 600; }
.memory-card-head > span { display: flex; align-items: center; gap: 5px; }
.memory-card p { margin: 7px 0 0; color: #8995a3; font-size: 11px; line-height: 1.5; }
.memory-chip-list { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 5px; }
.memory-chip-list span { padding: 3px 7px; border-radius: 999px; color: #35638c; background: #edf5fc; font-size: 10px; }

.chat-main { min-width: 0; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.chat-header { min-height: 62px; padding: 9px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid #ebeff3; }
.chat-header-actions { display: flex; align-items: center; gap: 8px; }
.chat-header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.chat-heading { min-width: 0; display: flex; align-items: center; gap: 8px; }
.chat-header h1 { margin: 0; display: flex; align-items: center; gap: 8px; color: #273547; font-size: 17px; }
.chat-header p { margin: 4px 0 0; color: #8793a2; font-size: 11px; }
.mobile-history-button, .mobile-sidebar-backdrop { display: none; }

.chat-area { flex: 1; min-height: 0; padding: 15px 16px; overflow-y: auto; overscroll-behavior: contain; background: #fbfcfe; }
.history-loading { height: 100%; display: grid; place-content: center; grid-auto-flow: column; gap: 8px; color: #8793a2; font-size: 13px; }
.message-block + .message-block { margin-top: 17px; }
.bubble-row { display: flex; }
.message-block.user .bubble-row { justify-content: flex-end; }
.message-bubble { max-width: min(760px, 82%); padding: 10px 14px; border-radius: 12px; overflow-wrap: anywhere; font-size: 13px; line-height: 1.65; }
.message-bubble.user { color: #fff; background: #3278ba; border-bottom-right-radius: 3px; }
.message-bubble.assistant { color: #354253; background: #fff; border: 1px solid #e4e9ef; border-bottom-left-radius: 3px; box-shadow: 0 2px 8px rgb(39 61 86 / 5%); }
.assistant-label { display: block; margin-bottom: 3px; color: #3a79b3; font-size: 10.5px; font-weight: 700; }
.message-text { white-space: pre-wrap; }
.processing-note, .degraded-note, .understanding-note { width: fit-content; max-width: 82%; margin: 7px 0 0 6px; color: #718196; font-size: 11px; }
.processing-note { display: flex; align-items: center; gap: 5px; }
.degraded-note { padding: 5px 9px; border-radius: 7px; color: #946b2c; background: #fff7e6; }
.understanding-note { padding: 5px 9px; border-left: 2px solid #9fc2e5; }

.welcome-actions { width: min(590px, 90%); margin-top: 9px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.welcome-actions button { min-width: 0; padding: 10px; display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; align-items: center; gap: 8px; text-align: left; border: 1px solid #d7e4f0; border-radius: 10px; color: #344c63; background: #fff; cursor: pointer; transition: border-color 150ms, background 150ms, transform 150ms; }
.welcome-actions button:hover { border-color: #75a7d4; background: #f4f9fe; transform: translateY(-1px); }
.welcome-action-icon { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 8px; color: #fff; background: #3278ba; font-size: 17px; }
.welcome-action-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.welcome-action-copy strong { font-size: 12px; }
.welcome-action-copy small { overflow: hidden; color: #8190a0; font-size: 10.5px; text-overflow: ellipsis; white-space: nowrap; }
.welcome-action-arrow { color: #78a0c4; font-size: 15px; }

.recommendation-shell { margin-bottom: 10px; padding: 10px; border: 1px solid #dde7f1; border-radius: 12px; background: linear-gradient(180deg, #f4f9fd, #fff 52px); }
.recommendation-head { margin-bottom: 8px; display: flex; align-items: baseline; gap: 9px; }
.recommendation-head strong { color: #33465a; font-size: 12px; }
.recommendation-head span { color: #8794a2; font-size: 10.5px; }
.recommendation-row { display: flex; gap: 10px; padding-bottom: 6px; overflow-x: auto; scroll-snap-type: x proximity; }

.state-row, .source-row, .quick-row { margin: 7px 0 0 4px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.state-row > span:not(.row-label), .source-row > span:not(.row-label) { padding: 4px 8px; border-radius: 999px; color: #3d668c; background: #eaf3fc; font-size: 10.5px; }
.source-row > span.missing { color: #936822; background: #fff5df; }
.row-label { color: #8794a2; font-size: 10.5px; }
.quick-row button, .faq-row button { padding: 5px 10px; border: 1px solid #c5daec; border-radius: 999px; color: #35658f; background: #fff; font-size: 11px; white-space: nowrap; cursor: pointer; }
.quick-row button:hover, .faq-row button:hover { border-color: #6fa4d1; background: #edf6fe; }
button:disabled { opacity: 0.55; cursor: not-allowed; }

.compare-bar { padding: 7px 16px; display: flex; align-items: center; gap: 8px; border-top: 1px solid #dfebf6; color: #52677d; background: #eef7ff; font-size: 12px; }
.compare-bar span { margin-right: auto; }
.compare-bar :deep(.el-button + .el-button) { margin-left: 0; }
.composer { flex: 0 0 auto; padding: 9px 14px 12px; border-top: 1px solid #e5eaf0; background: #fff; box-shadow: 0 -4px 14px rgb(45 68 92 / 4%); }
.faq-row { margin-bottom: 8px; display: flex; align-items: center; gap: 6px; overflow-x: auto; }
.faq-row > span { color: #8793a2; font-size: 10.5px; white-space: nowrap; }
.composer-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 9px; }
.composer :deep(.el-textarea__inner) { min-height: 58px !important; padding-right: 68px; border-radius: 10px; font-size: 13px; }
.send-button { height: 38px; }

@media (max-width: 980px) {
  .ai-search-page { grid-template-columns: 184px minmax(0, 1fr); }
  .chat-header p { max-width: 430px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}

@media (max-width: 720px) {
  .ai-search-page { display: flex; }
  .session-sidebar { position: absolute; inset: 0 auto 0 0; z-index: 21; width: min(86vw, 310px); transform: translateX(-102%); transition: transform 180ms ease; box-shadow: 12px 0 30px rgb(31 48 68 / 18%); }
  .session-sidebar.mobile-open { transform: translateX(0); }
  .mobile-sidebar-backdrop { position: absolute; inset: 0; z-index: 20; display: block; border: 0; background: rgb(28 42 58 / 34%); }
  .mobile-history-button { display: inline-flex; flex: 0 0 auto; }
  .chat-header { min-height: 56px; padding: 8px 10px; }
  .chat-header h1 { font-size: 15px; }
  .chat-header p { display: none; }
  .chat-header > .el-button { padding: 7px 9px; font-size: 11px; }
  .chat-area { padding: 12px 9px; }
  .message-bubble { max-width: 92%; }
  .welcome-actions { width: 100%; grid-template-columns: 1fr; }
  .recommendation-head { align-items: flex-start; flex-direction: column; gap: 2px; }
  .compare-bar { padding: 6px 8px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 6px; }
  .compare-bar span { grid-column: 1 / -1; margin-right: 0; }
  .compare-bar :deep(.el-button) { min-width: 0; margin: 0; padding: 5px 8px; }
  .composer { padding: 8px; }
  .composer-row { grid-template-columns: minmax(0, 1fr) 40px; }
  .send-button { width: 40px; padding: 0; font-size: 0; }
}
</style>

<style>
/* AI 页使用视口内独立滚动，避免长对话把输入区推离屏幕。 */
html.ai-search-page-active,
html.ai-search-page-active body,
html.ai-search-page-active #app {
  height: 100%;
  overflow: hidden;
}

html.ai-search-page-active .layout-container {
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
}

html.ai-search-page-active .layout-body,
html.ai-search-page-active .layout-main {
  min-height: 0;
  overflow: hidden;
}

/* router 尚未声明 hideFooter 时的页面级兜底。 */
html.ai-search-page-active .global-footer {
  display: none;
}

/* 对比工作台由 Dialog 传送到 body，尺寸样式必须放在非 scoped 区域。 */
.compare-workspace-modal .el-overlay-dialog {
  overflow: hidden;
}

.el-dialog.compare-workspace-dialog {
  width: 94vw;
  height: 90vh;
  height: 90dvh;
  margin: 5dvh auto 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 14px;
}

.el-dialog.compare-workspace-dialog .el-dialog__header {
  display: none;
  margin: 0;
  padding: 0;
}

.el-dialog.compare-workspace-dialog .el-dialog__body {
  flex: 1;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

@media (max-width: 720px) {
  .el-dialog.compare-workspace-dialog {
    width: 100vw !important;
    max-width: none;
    height: 100vh;
    height: 100dvh;
    margin: 0;
    border-radius: 0;
  }
}
</style>
