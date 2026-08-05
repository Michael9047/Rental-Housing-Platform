<!-- 搜索页右侧 AI 租房管家面板：承载快捷入口、流式对话与房源推荐。 -->
<template>
  <section class="agent-panel" aria-label="AI 租房管家">
    <header class="agent-header">
      <div class="agent-title">
        <span class="agent-icon"><el-icon :size="17"><ChatDotRound /></el-icon></span>
        <div>
          <strong>AI 租房管家</strong>
          <span>{{ starting ? '正在启动' : startupFailed ? '启动失败，请重新打开' : '结合当前搜索继续问' }}</span>
        </div>
      </div>
      <el-tooltip content="关闭 AI 租房管家" placement="bottom">
        <el-button class="close-btn" text circle aria-label="关闭 AI 租房管家" @click="emit('close')">
          <el-icon><Close /></el-icon>
        </el-button>
      </el-tooltip>
    </header>

    <div v-if="currentFilterChips.length" class="context-bar">
      <span class="context-label">当前筛选</span>
      <div class="context-chips">
        <span v-for="chip in currentFilterChips" :key="chip">{{ chip }}</span>
      </div>
    </div>

    <div v-if="selectedVisibleResultIds.length" class="left-selection-bar" aria-live="polite">
      <span>左侧已选 <strong>{{ selectedVisibleResultIds.length }}</strong> 套房源</span>
      <el-button
        size="small"
        type="primary"
        :disabled="selectedVisibleResultIds.length < 2 || sending"
        @click="compareLeftSelection"
      >
        综合对比
      </el-button>
    </div>

    <div ref="messageListRef" class="message-list" aria-live="polite">
      <section class="welcome-panel" aria-label="AI 租房管家快捷入口">
        <div class="welcome-copy">
          <strong>你好，我是租房推荐管家 👋</strong>
          <span>告诉我地区、预算和户型，我会结合左侧筛选帮你继续找。</span>
        </div>
        <div class="welcome-actions">
          <button :disabled="starting || startupFailed || sending" @click="send('我要找房')">
            <span class="welcome-action-icon"><el-icon><Search /></el-icon></span>
            <span>
              <strong>找房子</strong>
              <small>按需求推荐房源</small>
            </span>
          </button>
          <button
            :disabled="starting || startupFailed || sending || comparisonCandidateIds.length < 2"
            :title="comparisonCandidateIds.length < 2 ? '当前至少需要 2 套房源才能比较' : '比较当前搜索结果'"
            @click="send('请对比当前搜索结果里的房源，告诉我哪套更适合')"
          >
            <span class="welcome-action-icon"><el-icon><DataAnalysis /></el-icon></span>
            <span>
              <strong>对比找房</strong>
              <small>{{ comparisonCandidateIds.length < 2 ? '至少需要 2 套' : `比较当前 ${comparisonCandidateIds.length} 套` }}</small>
            </span>
          </button>
        </div>
      </section>

      <div
        v-for="(message, index) in conversationMessages"
        :key="message.id || `${message.role}-${index}`"
        class="message-block"
      >
        <!-- 房源图片和卡片统一置于回复正文上方，横向展示去重后的全部结果。 -->
        <div
          v-if="message.role === 'assistant' && message.recommendations?.length"
          class="recommendation-group"
        >
          <div class="recommendation-head">
            <strong>{{ uniqueRecommendations(message.recommendations).length }} 套匹配房源</strong>
            <span>勾选 2–5 套可直接对比</span>
          </div>
          <div class="recommendation-row">
            <article
              v-for="rec in uniqueRecommendations(message.recommendations)"
              :key="rec.property_id"
              class="recommendation-card"
              role="button"
              tabindex="0"
              @click="openProperty(rec.property_id)"
              @keydown.enter.prevent="openProperty(rec.property_id)"
            >
              <div class="recommendation-image">
                <img v-if="imageUrl(rec)" :src="imageUrl(rec)!" :alt="rec.property.title" />
                <el-icon v-else :size="22"><PictureFilled /></el-icon>
                <div class="recommendation-check" @click.stop>
                  <el-checkbox
                    :model-value="selectedCompareIds.includes(rec.property_id)"
                    :disabled="!selectedCompareIds.includes(rec.property_id) && selectedCompareIds.length >= 5"
                    @change="(checked: boolean) => toggleCompare(rec.property_id, checked)"
                  >
                    对比
                  </el-checkbox>
                </div>
              </div>
              <div class="recommendation-copy">
                <strong :title="rec.property.title">{{ rec.property.title }}</strong>
                <span>{{ rec.property.district || '区域待确认' }} · {{ formatPrice(rec) }}/月</span>
                <div class="recommendation-specs">
                  <span>{{ rec.property.bedrooms ?? '?' }}室{{ rec.property.bathrooms ?? '?' }}卫</span>
                  <span v-if="rec.property.area_sqm">{{ rec.property.area_sqm }}㎡</span>
                </div>
                <p v-if="rec.match_reason">{{ rec.match_reason }}</p>
              </div>
            </article>
          </div>
          <div v-if="selectedCompareIds.length" class="compare-selection" aria-live="polite">
            <span>已选 {{ selectedCompareIds.length }} 套</span>
            <el-button
              size="small"
              type="primary"
              :disabled="selectedCompareIds.length < 2 || sending"
              @click="compareSelected"
            >
              对比已选房源
            </el-button>
            <el-button size="small" text @click="selectedCompareIds = []">清空</el-button>
          </div>
          <el-button
            v-if="uniqueRecommendations(message.allRecommendations).length"
            class="show-results-btn"
            size="small"
            plain
            type="primary"
            @click="emit('show-recommendations', uniqueRecommendations(message.allRecommendations))"
          >
            在搜索区显示 {{ uniqueRecommendations(message.allRecommendations).length }} 套
          </el-button>
        </div>

        <div class="bubble-row" :class="message.role">
          <div
            v-if="message.role === 'assistant' && message.streaming && !message.content"
            class="bubble assistant typing"
          >
            <el-icon class="is-loading"><Loading /></el-icon>
            正在整理回复
          </div>
          <div v-else class="bubble" :class="message.role">{{ message.content }}</div>
        </div>

        <div v-if="message.role === 'assistant' && message.stateSummary?.chips.length" class="memory-row">
          <span v-for="chip in message.stateSummary.chips.slice(0, 6)" :key="chip.key">{{ chip.label }}</span>
        </div>

        <div v-if="message.role === 'assistant' && message.guidedOptions?.length" class="quick-row">
          <button
            v-for="option in message.guidedOptions.slice(0, 4)"
            :key="option.kind + option.label"
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
      </div>

    </div>

    <footer class="composer" aria-label="向 AI 租房管家提问">
      <div class="faq-row" aria-label="常见问题快捷入口">
        <span class="faq-label">常见问题</span>
        <button
          v-for="faq in faqChips"
          :key="faq.id"
          :disabled="starting || startupFailed || sending"
          @click="send(faq.chip)"
        >
          {{ faq.chip }}
        </button>
      </div>
      <div class="composer-row">
        <el-input
          v-model="inputText"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          :maxlength="20000"
          show-word-limit
          resize="none"
          :disabled="starting || startupFailed || sending"
          placeholder="补充预算、通勤或生活偏好（Shift+Enter 换行）"
          @keydown.enter.exact.prevent="send()"
        />
        <el-tooltip content="发送" placement="top">
          <el-button
            class="send-btn"
            type="primary"
            circle
            :loading="sending"
            :disabled="starting || startupFailed || sending || !inputText.trim()"
            aria-label="发送"
            @click="send()"
          >
            <el-icon v-if="!sending"><Promotion /></el-icon>
          </el-button>
        </el-tooltip>
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
  Loading,
  PictureFilled,
  Promotion,
  Search,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { agentService } from '@/services/agent'
import { useAgentChatStore } from '@/stores/agentChat'
import { getImageUrl } from '@/utils/image'
import { formatPropertyPrice, getCurrencySymbol } from '@/utils/currency'
import { uniqueAgentRecommendations } from '@/utils/agentRecommendations'
import type {
  AgentChatMessage,
  AgentFilters,
  AgentRecommendation,
  AgentStreamMeta,
  FaqChip,
  GuidedOption,
} from '@/types/agent'

const props = defineProps<{
  filters: AgentFilters
  resultCount: number
  resultIds: number[]
  selectedResultIds: number[]
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'apply-filter-patch', patch: Record<string, unknown>, refreshResults?: boolean): void
  (event: 'show-recommendations', recommendations: AgentRecommendation[]): void
}>()

const router = useRouter()
const agentChatStore = useAgentChatStore()
const { sessionId, messages } = storeToRefs(agentChatStore)
const inputText = ref('')
const starting = ref(true)
const startupFailed = ref(false)
const sending = ref(false)
const selectedCompareIds = ref<number[]>([])
const messageListRef = ref<HTMLElement | null>(null)
let scrollFrame: number | null = null

const requiredFaqChips: FaqChip[] = [
  { id: 'find_house', chip: '我要找房' },
  { id: 'booking', chip: '预订流程' },
  { id: 'contract', chip: '合同如何签' },
  { id: 'deposit', chip: '押金怎么退' },
]
const faqChips = ref<FaqChip[]>([...requiredFaqChips])

/** Store 内的欢迎语由面板内可滚动的快捷入口呈现，避免重复展示。 */
const conversationMessages = computed(() => messages.value.filter((message) => !message.isWelcome))

const currentFilterChips = computed(() => {
  const filters = props.filters
  const chips: string[] = []
  if (filters.country) chips.push(filters.country)
  if (filters.district) chips.push(filters.district)
  const priceSymbol = getCurrencySymbol(filters.currency, filters.country)
  if (filters.price_min != null) chips.push(`最低 ${priceSymbol}${Number(filters.price_min).toLocaleString()}`)
  if (filters.price_max != null) chips.push(`最高 ${priceSymbol}${Number(filters.price_max).toLocaleString()}`)
  if (filters.bedrooms != null) chips.push(`${filters.bedrooms} 室`)
  if (filters.property_type) chips.push(filters.property_type)
  if (filters.room_type) chips.push(filters.room_type)
  if (filters.max_lease_months != null && Number(filters.max_lease_months) <= 3) {
    chips.push('短租 1–3 月')
  } else if (
    filters.min_lease_months != null
    && Number(filters.min_lease_months) >= 3
    && filters.max_lease_months != null
    && Number(filters.max_lease_months) <= 6
  ) {
    chips.push('中租 3–6 月')
  } else if (filters.min_lease_months != null && Number(filters.min_lease_months) >= 12) {
    chips.push('长租 12 月起')
  }
  if (filters.amenities?.length) chips.push(...filters.amenities.slice(0, 2))
  if (props.resultCount > 0) chips.push(`${props.resultCount} 套结果`)
  return chips.slice(0, 7)
})

onMounted(async () => {
  try {
    await Promise.all([
      agentChatStore.ensureSession(),
      agentService.getFaqs().then((chips) => {
        if (chips.length) faqChips.value = mergeFaqChips(chips)
      }).catch(() => undefined),
    ])
    await scrollToBottom()
  } catch {
    startupFailed.value = true
    ElMessage.error('AI 租房管家启动失败，请稍后重试')
  } finally {
    starting.value = false
  }
})

onBeforeUnmount(() => {
  if (scrollFrame !== null) window.cancelAnimationFrame(scrollFrame)
})

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

function scheduleScroll() {
  if (scrollFrame !== null) return
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = null
    void scrollToBottom()
  })
}

/** 必选入口始终保留，接口返回的 FAQ 作为补充，避免关键 chips 被远端列表覆盖。 */
function mergeFaqChips(remoteChips: FaqChip[]): FaqChip[] {
  const merged = [...requiredFaqChips]
  for (const chip of remoteChips) {
    if (merged.some((item) => item.id === chip.id || item.chip === chip.chip)) continue
    merged.push(chip)
  }
  return merged.slice(0, 6)
}

function requestFilters(): AgentFilters {
  return Object.fromEntries(
    Object.entries(props.filters).filter(([, value]) => value != null && value !== ''),
  ) as AgentFilters
}

async function send(preset?: string, explicitCompareIds?: number[]) {
  const text = (preset ?? inputText.value).trim()
  if (!text || sending.value || sessionId.value === null) return
  const availableCompareIds = explicitCompareIds?.length
    ? explicitCompareIds
    : comparisonCandidateIds.value
  if (isComparisonRequest(text) && availableCompareIds.length < 2) {
    ElMessage.warning('当前结果不足 2 套，请先放宽筛选条件再进行比较')
    return
  }

  messages.value.push({ role: 'user', content: text })
  // Store 返回响应式消息对象，流中的每个 token 都能立即刷新当前气泡。
  const assistantMessage = agentChatStore.appendStreamingAssistant()
  if (preset === undefined) inputText.value = ''
  sending.value = true
  await scrollToBottom()

  const finalMeta: AgentStreamMeta = {}
  const compareIds = explicitCompareIds?.length ? explicitCompareIds : compareIdsFor(text)

  try {
    await agentService.sendMessageStream(
      sessionId.value,
      {
        message: text,
        context_filters: requestFilters(),
        compare_property_ids: compareIds,
      },
      {
        onToken(token) {
          assistantMessage.content += token
          scheduleScroll()
        },
        onMeta(meta) {
          Object.assign(finalMeta, meta)
          applyMeta(assistantMessage, meta)
          scheduleScroll()
        },
        onError(message) {
          if (!assistantMessage.content) assistantMessage.content = `抱歉，${message}`
        },
      },
    )
    if (!assistantMessage.content) assistantMessage.content = '这次没有生成有效回复，请换一种说法再试。'

    const recommendations = finalMeta.recommendations?.length
      ? uniqueRecommendations(finalMeta.recommendations)
      : finalMeta.top_picks?.length
        ? uniqueRecommendations(finalMeta.top_picks)
        : []
    if (finalMeta.filter_patch && Object.keys(finalMeta.filter_patch).length > 0) {
      emit('apply-filter-patch', finalMeta.filter_patch, recommendations.length === 0)
    }
    if (recommendations.length > 0) emit('show-recommendations', recommendations)
  } catch (error) {
    const reason = error instanceof Error ? error.message : '请求没有成功，请稍后再试'
    assistantMessage.content = assistantMessage.content
      ? `${assistantMessage.content}\n\n（连接中断：${reason}）`
      : `抱歉，${reason}`
  } finally {
    assistantMessage.streaming = false
    sending.value = false
    void agentChatStore.fetchSessions()
    await scrollToBottom()
  }
}

function compareIdsFor(text: string): number[] | undefined {
  if (!isComparisonRequest(text)) return undefined
  return comparisonCandidateIds.value.length >= 2 ? comparisonCandidateIds.value : undefined
}

function isComparisonRequest(text: string): boolean {
  return /(这几套|这些房|哪套|哪个好|怎么选|对比|比较)/i.test(text)
}

const validResultIds = computed(() => [
  ...new Set(props.resultIds.filter((id) => Number.isInteger(id) && id > 0)),
])

const selectedVisibleResultIds = computed(() => [
  ...new Set(props.selectedResultIds.filter((id) => Number.isInteger(id) && id > 0)),
].slice(0, 5))

/** 用户勾选后严格使用勾选项；未勾选时默认取当前可见结果前 5 套。 */
const comparisonCandidateIds = computed(() => (
  selectedVisibleResultIds.value.length
    ? selectedVisibleResultIds.value
    : validResultIds.value.slice(0, 5)
))

function applyMeta(message: AgentChatMessage, meta: AgentStreamMeta) {
  const recommendations = meta.recommendations?.length
    ? uniqueRecommendations(meta.recommendations)
    : meta.top_picks?.length
      ? uniqueRecommendations(meta.top_picks)
      : undefined
  if (recommendations) {
    message.recommendations = recommendations
    message.allRecommendations = uniqueRecommendations(meta.recommendations || recommendations)
  }
  if (meta.ai_available !== undefined) message.aiAvailable = meta.ai_available
  if (meta.quick_replies) message.quickReplies = meta.quick_replies
  if (meta.guided_options) message.guidedOptions = meta.guided_options
  if (meta.state_summary) message.stateSummary = meta.state_summary
  if (meta.query_rewrite) message.queryRewrite = meta.query_rewrite
  if (meta.sources) message.sources = meta.sources
  if (meta.filter_patch) message.filterPatch = meta.filter_patch
}

function applyGuidedOption(option: GuidedOption) {
  if (option.filter_patch) emit('apply-filter-patch', option.filter_patch, false)
  send(option.message || option.label)
}

function uniqueRecommendations(
  recommendations: AgentRecommendation[] | null | undefined,
): AgentRecommendation[] {
  return uniqueAgentRecommendations(recommendations)
}

function toggleCompare(propertyId: number, checked: boolean) {
  if (checked && !selectedCompareIds.value.includes(propertyId) && selectedCompareIds.value.length < 5) {
    selectedCompareIds.value = [...selectedCompareIds.value, propertyId]
  } else if (!checked) {
    selectedCompareIds.value = selectedCompareIds.value.filter((id) => id !== propertyId)
  }
}

function compareSelected() {
  if (selectedCompareIds.value.length < 2) {
    ElMessage.warning('请至少勾选 2 套房源进行对比')
    return
  }
  void send(
    '请结合我前面说的需求，详细比较这些房源并告诉我哪套更适合。',
    [...selectedCompareIds.value],
  )
}

function compareLeftSelection() {
  if (selectedVisibleResultIds.value.length < 2) {
    ElMessage.warning('请在左侧至少勾选 2 套房源进行对比')
    return
  }
  void send(
    '请结合我前面说的需求，详细比较左侧勾选的房源并告诉我哪套更适合。',
    [...selectedVisibleResultIds.value],
  )
}

function imageUrl(rec: AgentRecommendation): string | null {
  const images = rec.property.images
  if (!images?.length) return null
  const primary = images.find((image) => image.is_primary) || images[0]
  return getImageUrl(primary.filename)
}

function formatPrice(rec: AgentRecommendation): string {
  return formatPropertyPrice(
    rec.property.price_monthly,
    rec.property.currency,
    rec.property.country,
  )
}

function openProperty(propertyId: number) {
  router.push(`/property/${propertyId}`)
}
</script>

<style scoped>
.agent-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #dfe4ea;
  border-radius: 12px;
  overflow: hidden;
}

.agent-header {
  min-height: 68px;
  padding: 12px 12px 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef2;
}

.agent-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 11px;
}

.agent-icon {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  display: grid;
  place-items: center;
  color: #fff;
  background: #2768a8;
  border-radius: 9px;
}

.agent-title div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.agent-title strong { font-size: 16px; color: #263445; }
.agent-title span { font-size: 12px; color: #778596; }
.close-btn { width: 34px; height: 34px; flex: 0 0 34px; }

.context-bar {
  padding: 10px 14px;
  background: #f7f9fb;
  border-bottom: 1px solid #ebeef2;
}

.left-selection-bar {
  padding: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #41627f;
  background: #eef6fd;
  border-bottom: 1px solid #d6e7f5;
  font-size: 12px;
}

.left-selection-bar strong { color: #205f96; }

.context-label {
  display: block;
  margin-bottom: 6px;
  color: #6c7785;
  font-size: 12px;
  font-weight: 600;
}

.context-chips,
.memory-row,
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.context-chips span,
.memory-row span {
  max-width: 100%;
  padding: 4px 8px;
  color: #456078;
  background: #eaf1f7;
  border-radius: 5px;
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.welcome-panel {
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid #e3eaf1;
  border-radius: 10px;
  background: linear-gradient(180deg, #fbfdff 0%, #f7faff 100%);
}

.welcome-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.welcome-copy strong { color: #2f4155; font-size: 14px; }
.welcome-copy span { color: #6f7e8e; font-size: 12px; line-height: 1.55; }

.welcome-actions {
  margin-top: 11px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
}

.welcome-actions button {
  min-width: 0;
  min-height: 62px;
  padding: 9px 10px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: #385a78;
  text-align: left;
  background: #fff;
  border: 1px solid #d7e3ee;
  border-radius: 9px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.welcome-actions button:hover:not(:disabled) {
  border-color: #78a6d0;
  box-shadow: 0 3px 10px rgba(42, 75, 108, 0.08);
  transform: translateY(-1px);
}

.welcome-actions button:disabled { opacity: 0.55; cursor: not-allowed; }
.welcome-actions button > span:last-child { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.welcome-actions strong { font-size: 13px; }
.welcome-actions small { color: #7c8998; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.welcome-action-icon {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  display: grid;
  place-items: center;
  color: #2768a8;
  background: #eaf3fb;
  border-radius: 6px;
}

.faq-row button {
  padding: 5px 9px;
  border: 1px solid #cbd9e6;
  border-radius: 999px;
  color: #35658f;
  background: #fff;
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
}

.faq-row button:hover { border-color: #7ba8d4; background: #f0f6fb; }
.faq-row button:disabled { opacity: 0.55; cursor: not-allowed; }

.message-list {
  flex: 1 1 260px;
  min-height: 120px;
  padding: 14px 14px 18px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.message-block + .message-block { margin-top: 13px; }
.bubble-row { display: flex; }
.bubble-row.user { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }

.bubble {
  max-width: 88%;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13.5px;
  line-height: 1.62;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.bubble.user { color: #fff; background: #2768a8; border-bottom-right-radius: 3px; }
.bubble.assistant { color: #344254; background: #f2f4f7; border-bottom-left-radius: 3px; }
.typing { display: flex; align-items: center; gap: 7px; color: #718096; }
.memory-row { margin: 7px 0 0; }

.recommendation-group {
  margin-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.recommendation-head { display: flex; align-items: baseline; gap: 7px; }
.recommendation-head { justify-content: space-between; gap: 12px; }
.recommendation-head strong { color: #2f4052; font-size: 13px; }
.recommendation-head span { color: #7d8997; font-size: 11px; }
.recommendation-row { display: flex; gap: 10px; padding-bottom: 7px; overflow-x: auto; scroll-snap-type: x proximity; }

.recommendation-card {
  width: 406px;
  flex: 0 0 406px;
  min-height: 150px;
  padding: 0;
  display: grid;
  grid-template-columns: 154px minmax(0, 1fr);
  text-align: left;
  background: #fff;
  border: 1px solid #e2e7ed;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  scroll-snap-align: start;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.recommendation-card:hover { border-color: #7ba8d4; box-shadow: 0 3px 10px rgba(42, 75, 108, 0.09); }
.recommendation-image { position: relative; min-height: 150px; display: grid; place-items: center; color: #b2bbc5; background: #eef1f4; }
.recommendation-image img { width: 100%; height: 100%; object-fit: cover; }
.recommendation-check { position: absolute; top: 8px; left: 8px; padding: 2px 7px; border-radius: 6px; background: rgba(255, 255, 255, 0.94); box-shadow: 0 1px 5px rgba(38, 52, 69, 0.12); }
.recommendation-check :deep(.el-checkbox__label) { padding-left: 5px; font-size: 11px; }
.recommendation-copy { min-width: 0; padding: 13px 14px; display: flex; flex-direction: column; gap: 7px; }
.recommendation-copy strong { color: #2d3948; font-size: 14.5px; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.recommendation-copy > span { color: #c64f46; font-size: 13px; font-weight: 700; }
.recommendation-specs { display: flex; flex-wrap: wrap; gap: 5px; }
.recommendation-specs span { padding: 3px 6px; border-radius: 5px; color: #53677b; background: #eef3f7; font-size: 10.5px; }
.recommendation-copy p { margin: 0; color: #6f7b89; font-size: 11.5px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.compare-selection { padding: 8px 10px; display: flex; align-items: center; gap: 6px; border-radius: 8px; color: #47627c; background: #edf6ff; font-size: 12px; }
.compare-selection > span { margin-right: auto; font-weight: 600; }
.show-results-btn { width: 100%; }

.quick-row { margin-top: 7px; }
.quick-row button {
  padding: 5px 9px;
  color: #35658f;
  background: #fff;
  border: 1px solid #cbd9e6;
  border-radius: 5px;
  font-size: 11.5px;
  cursor: pointer;
}
.quick-row button:hover { background: #f0f6fb; border-color: #7ba8d4; }
.quick-row button:disabled { opacity: 0.55; cursor: not-allowed; }

.composer {
  flex: 0 0 auto;
  margin-top: auto;
  padding: 12px;
  position: relative;
  z-index: 2;
  background: #fff;
  border-top: 1px solid #ebeef2;
  box-shadow: 0 -4px 12px rgba(40, 61, 82, 0.035);
}

.faq-row { margin-bottom: 7px; display: flex; align-items: center; gap: 5px; overflow-x: auto; }
.faq-label { flex: 0 0 auto; color: #7b8794; font-size: 11px; white-space: nowrap; }
.composer-row { display: grid; grid-template-columns: minmax(0, 1fr) 38px; align-items: end; gap: 9px; }
.composer :deep(.el-textarea__inner) { min-height: 62px !important; padding-right: 58px; font-size: 13px; }
.send-btn { width: 38px; height: 38px; }

@media (max-height: 700px) {
  .welcome-panel { padding-top: 8px; padding-bottom: 8px; }
  .welcome-copy span { display: none; }
  .welcome-actions { margin-top: 6px; }
  .welcome-actions button { min-height: 43px; padding-top: 5px; padding-bottom: 5px; }
  .message-list { min-height: 72px; padding-top: 8px; padding-bottom: 9px; }
  .composer { padding-top: 8px; padding-bottom: 8px; }
  .composer :deep(.el-textarea__inner) { min-height: 46px !important; }
}

@media (max-width: 1240px) {
  .agent-panel { border: 0; border-radius: 0; }
}

@media (max-width: 480px) {
  .recommendation-card {
    width: calc(100vw - 44px);
    flex-basis: calc(100vw - 44px);
    grid-template-columns: 132px minmax(0, 1fr);
  }
  .recommendation-head { align-items: flex-start; flex-direction: column; gap: 2px; }
  .welcome-actions { grid-template-columns: 1fr; }
}
</style>
