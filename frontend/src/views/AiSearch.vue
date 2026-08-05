<!-- AI 找房主页面：多会话、长期记忆、FAQ 快捷入口与横向房源推荐。 -->
<template>
  <div class="ai-search-page">
    <button
      v-if="mobileSidebarOpen"
      class="mobile-sidebar-backdrop"
      aria-label="关闭对话记录"
      @click="mobileSidebarOpen = false"
    />
    <aside class="session-sidebar" :class="{ 'mobile-open': mobileSidebarOpen }">
      <div class="session-head">
        <strong>对话记录</strong>
        <el-button type="primary" size="small" :icon="Plus" :loading="creatingSession" @click="startNewSession">
          新对话
        </el-button>
      </div>

      <div v-loading="loadingHistory" class="session-list">
        <button
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: session.session_id === sessionId }"
          @click="openSession(session.session_id)"
        >
          <span class="session-title">{{ sessionTitle(session) }}</span>
          <span class="session-time">{{ relativeTime(session.updated_at) }}</span>
        </button>
        <el-empty v-if="!sessions.length" :image-size="48" description="暂无历史对话" />
      </div>

      <div class="memory-card">
        <div class="memory-card-head">
          <span><el-icon><CollectionTag /></el-icon> 长期记忆</span>
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
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-header">
        <div class="chat-heading">
          <el-button
            class="mobile-history-button"
            circle
            :icon="ChatLineSquare"
            aria-label="打开对话记录与长期记忆"
            @click="mobileSidebarOpen = true"
          />
          <el-button
            class="back-to-search-btn"
            size="small"
            @click="router.push('/search')"
          >
            <el-icon><ArrowLeft /></el-icon>
            返回搜索
          </el-button>
          <div>
            <h1><el-icon><MagicStick /></el-icon> AI 智能找房</h1>
            <p>我会结合当前对话、刚推荐的房源和已保存偏好继续回答</p>
          </div>
        </div>
        <el-button
          :icon="CollectionTag"
          :loading="savingMemory"
          :disabled="!savableMemory"
          @click="saveCurrentMemory"
        >
          保存本次偏好
        </el-button>
      </header>

      <div ref="chatAreaRef" class="chat-area">
        <div v-if="loadingHistory" class="history-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          正在载入对话记录
        </div>

        <article
          v-for="(message, index) in messages"
          v-else
          :key="message.id || `${message.role}-${index}`"
          class="message-block"
          :class="message.role"
        >
          <!-- 推荐卡片优先展示在回复正文上方，全部放进同一条横向轨道。 -->
          <div
            v-if="message.role === 'assistant' && message.recommendations?.length"
            class="recommendation-shell"
          >
            <div class="recommendation-head">
              <strong>为你找到 {{ message.allRecommendations?.length || message.recommendations.length }} 套房源</strong>
              <span>左右滑动查看全部 · 勾选后可对比</span>
            </div>
            <div class="recommendation-row">
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
          </div>

          <div class="bubble-row">
            <div class="message-bubble" :class="message.role">
              <span v-if="message.role === 'assistant'" class="assistant-label">AI 管家</span>
              <span class="message-text">{{ message.content || (message.streaming ? '正在理解你的需求…' : '') }}</span>
            </div>
          </div>

          <div
            v-if="message.role === 'assistant' && message.isWelcome"
            class="welcome-actions"
            aria-label="开始使用 AI 租房管家"
          >
            <button
              v-for="action in welcomeActions"
              :key="action.title"
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
            v-if="message.role === 'assistant' && message.queryRewrite && message.queryRewrite.rewritten !== message.queryRewrite.original"
            class="understanding-note"
          >
            我理解为：{{ message.queryRewrite.rewritten }}
          </div>

          <div v-if="message.role === 'assistant' && message.stateSummary?.chips.length" class="state-row">
            <span class="row-label">本轮记住</span>
            <span v-for="chip in message.stateSummary.chips" :key="chip.key">{{ chip.label }}</span>
          </div>

          <div v-if="message.role === 'assistant' && message.guidedOptions?.length" class="quick-row">
            <span class="row-label">继续调整</span>
            <button
              v-for="option in message.guidedOptions"
              :key="`${option.kind}-${option.label}`"
              :disabled="sending"
              @click="applyGuidedOption(option)"
            >
              {{ option.icon }} {{ option.label }}
            </button>
          </div>

          <div v-if="message.role === 'assistant' && message.quickReplies?.length" class="quick-row">
            <button
              v-for="reply in message.quickReplies"
              :key="reply"
              :disabled="sending"
              @click="send(reply)"
            >
              {{ reply }}
            </button>
          </div>

          <div v-if="message.role === 'assistant' && message.links?.length" class="quick-row link-row">
            <el-button
              v-for="link in message.links"
              :key="`${link.to}-${link.label}`"
              size="small"
              type="primary"
              plain
              @click="router.push(link.to)"
            >
              {{ link.label }} →
            </el-button>
          </div>
        </article>
      </div>

      <div v-if="selectedIds.length" class="compare-bar">
        <span>已选 {{ selectedIds.length }} 套房源</span>
        <el-button size="small" type="primary" :disabled="selectedIds.length < 2" @click="askToCompare">
          在对话中比较
        </el-button>
        <el-button size="small" text @click="selectedIds = []">清空</el-button>
      </div>

      <footer class="composer">
        <div class="faq-row" aria-label="常见问题快捷入口">
          <span>常见问题</span>
          <button v-for="faq in faqChips" :key="faq.id" :disabled="sending" @click="send(faqPrompt(faq))">
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
            placeholder="描述需求，或继续问「你推荐的这套有健身房吗？」（Shift+Enter 换行）"
            @keydown.enter.exact.prevent="send()"
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
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ArrowLeft, ChatLineSquare, CollectionTag, Loading, MagicStick, Plus, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import RecPropertyCard from '@/components/RecPropertyCard.vue'
import { agentService } from '@/services/agent'
import { uniqueAgentRecommendations } from '@/utils/agentRecommendations'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'
import type {
  AgentChatMessage,
  AgentFilters,
  AgentRecommendation,
  AgentSessionSummary,
  AgentStreamMeta,
  FaqChip,
  GuidedOption,
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
let scrollFrame: number | null = null

const localFilters = reactive<AgentFilters>({
  poi_requirements: [],
})

const welcomeActions = [
  {
    title: '找房子',
    description: '按地区、预算和户型开始',
    icon: '⌂',
    prompt: '我想找房，请先引导我补充地区、预算和户型。',
  },
  {
    title: '对比找房',
    description: '比较租金、通勤和设施',
    icon: '⇄',
    prompt: '请先帮我推荐几套适合对比的房源，再比较租金、通勤和设施。',
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
    const filters = messages.value[index].stateSummary?.filters
    if (filters && Object.keys(filters).length) return filters as AgentFilters
  }
  return {}
})

const savableMemory = computed(() => {
  return Object.keys({ ...localFilters, ...latestStateFilters.value })
    .some((key) => {
      const value = ({ ...localFilters, ...latestStateFilters.value } as Record<string, unknown>)[key]
      return value != null && value !== '' && (!Array.isArray(value) || value.length > 0)
    })
})

const memoryChips = computed(() => filterChips(rememberedPreferences.value))

function filterChips(filters: AgentFilters): string[] {
  const chips: string[] = []
  if (filters.country) chips.push(`国家/地区：${filters.country}`)
  if (filters.district) chips.push(`区域：${filters.district}`)
  if (filters.institution) chips.push(`学校：${filters.institution}`)
  if (filters.price_min != null || filters.price_max != null) {
    const min = filters.price_min != null ? Number(filters.price_min).toLocaleString() : '不限'
    const max = filters.price_max != null ? Number(filters.price_max).toLocaleString() : '不限'
    chips.push(`预算：${min}–${max}`)
  }
  if (filters.property_type) chips.push(`类型：${filters.property_type}`)
  if (filters.room_type) chips.push(`房型：${filters.room_type}`)
  if (filters.bedrooms != null) chips.push(`${filters.bedrooms} 室`)
  if (filters.amenities?.length) chips.push(...filters.amenities.slice(0, 4))
  return chips.slice(0, 9)
}

function sessionTitle(session: AgentSessionSummary): string {
  if (session.last_message) return session.last_message.slice(0, 24)
  return session.title || '新对话'
}

function relativeTime(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return ''
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`
  return new Date(timestamp).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

async function scrollToBottom() {
  await nextTick()
  if (chatAreaRef.value) chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
}

function scheduleScroll() {
  if (scrollFrame !== null) return
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = null
    void scrollToBottom()
  })
}

async function openSession(id: number) {
  if (sending.value) return
  try {
    await agentChat.switchSession(id)
    selectedIds.value = []
    mobileSidebarOpen.value = false
    await scrollToBottom()
  } catch {
    ElMessage.error('对话记录加载失败，请稍后重试')
  }
}

async function startNewSession() {
  if (sending.value || creatingSession.value) return
  creatingSession.value = true
  try {
    await agentChat.newSession()
    selectedIds.value = []
    inputText.value = ''
    mobileSidebarOpen.value = false
    await scrollToBottom()
  } catch {
    ElMessage.error('新对话创建失败，请稍后重试')
  } finally {
    creatingSession.value = false
  }
}

function mergePatch(patch?: Record<string, unknown> | null) {
  if (!patch) return
  for (const [key, value] of Object.entries(patch)) {
    if ((key === 'amenities' || key === 'poi_requirements') && Array.isArray(value)) {
      const current = Array.isArray((localFilters as Record<string, unknown>)[key])
        ? (localFilters as Record<string, unknown>)[key] as unknown[]
        : []
      ;(localFilters as Record<string, unknown>)[key] = [
        ...current,
        ...value.filter((item) => !current.some((existing) => JSON.stringify(existing) === JSON.stringify(item))),
      ]
    } else {
      ;(localFilters as Record<string, unknown>)[key] = value
    }
  }
}

function activeFilters(): AgentFilters | undefined {
  const filters = Object.fromEntries(
    Object.entries(localFilters).filter(([, value]) =>
      value != null && value !== '' && (!Array.isArray(value) || value.length > 0),
    ),
  ) as AgentFilters
  return Object.keys(filters).length ? filters : undefined
}

function applyMeta(message: AgentChatMessage, meta: AgentStreamMeta) {
  if (meta.thinking_steps) message.thinkingSteps = meta.thinking_steps
  if (meta.query_rewrite) message.queryRewrite = meta.query_rewrite
  if (meta.sources) message.sources = meta.sources
  if (meta.state_summary) message.stateSummary = meta.state_summary
  if (meta.guided_options) message.guidedOptions = meta.guided_options
  if (meta.quick_replies) message.quickReplies = meta.quick_replies
  if (meta.links) message.links = meta.links
  if (meta.ai_available !== undefined) {
    message.aiAvailable = meta.ai_available
    aiAvailable.value = meta.ai_available
  }
  if (meta.recommendations?.length) {
    message.recommendations = uniqueAgentRecommendations(meta.recommendations)
    message.allRecommendations = uniqueAgentRecommendations(meta.recommendations)
  } else if (meta.top_picks?.length) {
    message.recommendations = uniqueAgentRecommendations(meta.top_picks)
    message.allRecommendations = uniqueAgentRecommendations(meta.top_picks)
  }
}

async function send(preset?: string, compareIds?: number[]) {
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

  try {
    await agentService.sendMessageStream(
      sessionId.value!,
      {
        message: text,
        filters: activeFilters(),
        compare_property_ids: compareIds,
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
    )
    if (!assistantMessage.content) assistantMessage.content = '这次没有生成有效回复，请换一种说法再试。'
  } catch (error) {
    const reason = error instanceof Error ? error.message : '请求失败，请稍后再试'
    assistantMessage.content = assistantMessage.content
      ? `${assistantMessage.content}\n\n（连接中断：${reason}）`
      : `抱歉，${reason}`
  } finally {
    assistantMessage.streaming = false
    sending.value = false
    void agentChat.fetchSessions()
    await scrollToBottom()
  }
}

function applyGuidedOption(option: GuidedOption) {
  mergePatch(option.filter_patch)
  void send(option.message || option.label)
}

function toggleCompare(propertyId: number, checked: boolean) {
  if (checked && !selectedIds.value.includes(propertyId)) selectedIds.value.push(propertyId)
  if (!checked) selectedIds.value = selectedIds.value.filter((id) => id !== propertyId)
}

function askToCompare() {
  if (selectedIds.value.length < 2) return
  void send('请结合我前面说的需求，详细比较这些房源并告诉我哪套更适合。', [...selectedIds.value])
}

async function toggleCart(recommendation: AgentRecommendation) {
  try {
    if (cartStore.has(recommendation.property_id)) {
      await cartStore.remove(recommendation.property_id)
      ElMessage.info(`已从候选清单移出「${recommendation.property.title}」`)
    } else {
      await cartStore.add(recommendation.property_id, recommendation.match_reason || undefined)
      ElMessage.success(`已将「${recommendation.property.title}」加入候选清单`)
    }
  } catch {
    // API 拦截器会展示具体错误。
  }
}

function goDetail(propertyId: number) {
  router.push(`/property/${propertyId}`)
}

async function saveCurrentMemory() {
  const preferences = { ...localFilters, ...latestStateFilters.value }
  savingMemory.value = true
  try {
    await agentChat.saveMemory(preferences)
    ElMessage.success('已保存偏好，新对话也会继续参考')
  } catch {
    ElMessage.error('偏好保存失败，请稍后重试')
  } finally {
    savingMemory.value = false
  }
}

async function clearSavedMemory() {
  savingMemory.value = true
  try {
    await agentChat.clearMemory()
    ElMessage.success('长期记忆已清空')
  } catch {
    ElMessage.error('记忆清空失败，请稍后重试')
  } finally {
    savingMemory.value = false
  }
}

onMounted(async () => {
  document.documentElement.classList.add('ai-search-page-active')

  await Promise.allSettled([
    agentChat.fetchSessions(),
    agentChat.fetchMemory(),
    cartStore.fetch(),
    agentService.getFaqs().then((chips) => {
      if (chips.length) faqChips.value = chips
    }),
  ])

  try {
    if (sessionId.value === null && sessions.value.length) {
      await agentChat.switchSession(sessions.value[0].session_id)
    } else {
      await agentChat.ensureSession()
    }
  } catch {
    ElMessage.error('AI 找房会话启动失败，请刷新后重试')
  }

  const query = typeof route.query.q === 'string' ? route.query.q.trim() : ''
  if (query) await send(query)
  await scrollToBottom()
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('ai-search-page-active')
  if (scrollFrame !== null) window.cancelAnimationFrame(scrollFrame)
})
</script>

<style scoped>
.ai-search-page {
  position: relative;
  width: 100%;
  flex: 1;
  display: grid;
  grid-template-columns: 212px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  height: auto;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  background: #fff;
}

.session-sidebar {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #e7ebf0;
  background: #f7f9fc;
}

.session-head {
  min-height: 54px;
  padding: 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px solid #e7ebf0;
}

.session-head strong { color: #2f3b4b; font-size: 14px; }
.session-list { flex: 1; min-height: 0; padding: 8px; overflow-y: auto; }
.session-item {
  width: 100%;
  margin-bottom: 4px;
  padding: 7px 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 8px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  cursor: pointer;
}
.session-item:hover { background: #eef3f9; }
.session-item.active { border-color: #bdd5ee; background: #eaf3fc; }
.session-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-title { color: #334254; font-size: 11.5px; font-weight: 600; }
.session-time { color: #a0a8b4; font-size: 10px; white-space: nowrap; }

.memory-card { margin: 6px 8px 8px; padding: 8px; border: 1px solid #dfe8f2; border-radius: 9px; background: #fff; }
.memory-card-head { display: flex; align-items: center; justify-content: space-between; color: #47617c; font-size: 12px; font-weight: 600; }
.memory-card-head > span { display: flex; align-items: center; gap: 5px; }
.memory-card p { margin: 7px 0 0; color: #8b96a5; font-size: 11px; line-height: 1.5; }
.memory-chip-list { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 5px; }
.memory-chip-list span { padding: 3px 6px; border-radius: 999px; color: #35638c; background: #edf5fc; font-size: 10px; }

.chat-main { min-width: 0; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.chat-header { min-height: 60px; padding: 9px 16px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid #edf0f3; }
.chat-header h1 { margin: 0; display: flex; align-items: center; gap: 8px; color: #273547; font-size: 17px; }
.chat-header p { margin: 4px 0 0; color: #8a95a3; font-size: 11px; }
.chat-heading { min-width: 0; display: flex; align-items: center; gap: 8px; }
.mobile-history-button,
.mobile-sidebar-backdrop { display: none; }

.quick-row button,
.faq-row button { padding: 5px 10px; border: 1px solid #c8dced; border-radius: 999px; color: #35658f; background: #fff; font-size: 11px; white-space: nowrap; cursor: pointer; }
.quick-row button:hover,
.faq-row button:hover { border-color: #6fa4d1; background: #edf6fe; }
button:disabled { opacity: 0.55; cursor: not-allowed; }

.chat-area { flex: 1; min-height: 0; padding: 14px 16px; overflow-y: auto; overscroll-behavior: contain; background: #fbfcfe; }
.history-loading { height: 100%; display: grid; place-content: center; grid-auto-flow: column; gap: 8px; color: #8b96a5; font-size: 13px; }
.message-block + .message-block { margin-top: 16px; }
.bubble-row { display: flex; }
.message-block.user .bubble-row { justify-content: flex-end; }
.message-bubble { max-width: min(760px, 82%); padding: 9px 13px; border-radius: 11px; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.message-bubble.user { color: #fff; background: #3278ba; border-bottom-right-radius: 3px; }
.message-bubble.assistant { color: #354253; background: #fff; border: 1px solid #e7ebf0; border-bottom-left-radius: 3px; box-shadow: 0 2px 8px rgb(39 61 86 / 5%); }
.assistant-label { display: block; margin-bottom: 3px; color: #3a79b3; font-size: 10.5px; font-weight: 700; }
.message-text { white-space: pre-wrap; }
.understanding-note { width: fit-content; max-width: 82%; margin: 7px 0 0 6px; padding: 5px 9px; border-left: 2px solid #9fc2e5; color: #718196; font-size: 11px; }

.welcome-actions {
  width: min(560px, 88%);
  margin-top: 9px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.welcome-actions button {
  min-width: 0;
  padding: 10px;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  text-align: left;
  border: 1px solid #d9e6f2;
  border-radius: 10px;
  color: #344c63;
  background: #fff;
  cursor: pointer;
  transition: border-color 150ms, background 150ms, transform 150ms;
}
.welcome-actions button:hover { border-color: #75a7d4; background: #f4f9fe; transform: translateY(-1px); }
.welcome-action-icon { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 8px; color: #fff; background: #3278ba; font-size: 17px; }
.welcome-action-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.welcome-action-copy strong { font-size: 12px; }
.welcome-action-copy small { overflow: hidden; color: #8290a0; font-size: 10.5px; text-overflow: ellipsis; white-space: nowrap; }
.welcome-action-arrow { color: #78a0c4; font-size: 15px; }

.recommendation-shell { margin-bottom: 10px; padding: 10px; border: 1px solid #e0e9f3; border-radius: 11px; background: linear-gradient(180deg, #f5f9fd, #fff 50px); }
.recommendation-head { margin-bottom: 8px; display: flex; align-items: baseline; gap: 9px; }
.recommendation-head strong { color: #33465a; font-size: 12px; }
.recommendation-head span { color: #8995a3; font-size: 10.5px; }
.recommendation-row { display: flex; gap: 10px; padding-bottom: 6px; overflow-x: auto; scroll-snap-type: x proximity; }
.recommendation-row > * { scroll-snap-align: start; }

.state-row,
.quick-row { margin: 7px 0 0 4px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.state-row > span:not(.row-label) { padding: 4px 8px; border-radius: 999px; color: #3d668c; background: #eaf3fc; font-size: 10.5px; }
.row-label { color: #8a96a4; font-size: 10.5px; }

.compare-bar { padding: 7px 16px; display: flex; align-items: center; gap: 8px; border-top: 1px solid #e4edf6; background: #f0f7ff; color: #52677d; font-size: 12px; }
.compare-bar span { margin-right: auto; }
.composer { flex: 0 0 auto; padding: 9px 14px 12px; border-top: 1px solid #e7ebf0; background: #fff; box-shadow: 0 -4px 14px rgb(45 68 92 / 4%); }
.faq-row { margin-bottom: 8px; display: flex; align-items: center; gap: 6px; overflow-x: auto; }
.faq-row > span { color: #8a95a3; font-size: 10.5px; white-space: nowrap; }
.composer-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 9px; }
.composer :deep(.el-textarea__inner) { min-height: 58px !important; padding-right: 66px; border-radius: 10px; font-size: 13px; }
.send-button { height: 38px; }

@media (max-width: 980px) {
  .ai-search-page { grid-template-columns: 176px minmax(0, 1fr); }
}

@media (max-width: 720px) {
  .ai-search-page { display: flex; height: auto; min-height: 0; }
  .session-sidebar {
    position: absolute;
    inset: 0 auto 0 0;
    z-index: 21;
    width: min(86vw, 300px);
    display: flex;
    transform: translateX(-102%);
    transition: transform 180ms ease;
    box-shadow: 12px 0 30px rgb(31 48 68 / 18%);
  }
  .session-sidebar.mobile-open { transform: translateX(0); }
  .mobile-sidebar-backdrop {
    position: absolute;
    inset: 0;
    z-index: 20;
    display: block;
    border: 0;
    background: rgb(28 42 58 / 34%);
  }
  .mobile-history-button { display: inline-flex; flex: 0 0 auto; }
  .chat-header p { display: none; }
  .chat-header { min-height: 56px; padding: 8px 11px; }
  .chat-header h1 { font-size: 15px; }
  .chat-area { padding: 12px 9px; }
  .message-bubble { max-width: 92%; }
  .welcome-actions { width: 100%; grid-template-columns: 1fr; }
  .composer { padding: 8px; }
  .composer-row { grid-template-columns: minmax(0, 1fr) 40px; }
  .send-button { width: 40px; padding: 0; font-size: 0; }
}
</style>

<style>
/* AI 找房页锁定在当前视口，消息区独立滚动，确保输入框始终留在面板底部。 */
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
</style>
