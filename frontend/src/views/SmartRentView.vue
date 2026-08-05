<template>
  <div class="chat-page">
    <!-- ═══ 页面标题栏 ═══ -->
    <div class="chat-content-header">
      <div class="chat-content-title">
        <el-icon :size="18" color="#409eff"><ChatDotRound /></el-icon>
        <span>智能租房</span>
        <el-tag v-if="!aiAvailable" size="small" type="warning">AI 暂不可用</el-tag>
      </div>
    </div>

    <!-- 当前会话 Memory：让用户知道系统记住了什么，也便于发现理解偏差 -->
    <div v-if="latestStateSummary?.chips.length" class="memory-bar">
      <span class="memory-label">已记住</span>
      <span v-for="chip in latestStateSummary.chips" :key="chip.key" class="memory-chip">
        {{ chip.label }}
      </span>
    </div>

    <!-- ═══ 消息列表 ═══ -->
    <div ref="chatListRef" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-empty">
        <el-icon :size="40" color="#c0c4cc"><ChatDotRound /></el-icon>
        <p>用自然语言描述你的租房需求</p>
        <p class="chat-hint">例如：「苏州工业园区，预算3000以内，近地铁的单间」</p>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="msg-block">
        <!-- 消息气泡 -->
        <div class="chat-bubble-row" :class="msg.role">
          <div class="chat-bubble" :class="msg.role">
            {{ msg.content || (msg.streaming ? '正在理解你的需求…' : '') }}
          </div>
        </div>

        <!-- Query Rewrite：只展示“系统如何理解”，不展示模型思维链 -->
        <div
          v-if="msg.role === 'assistant' && msg.queryRewrite && msg.queryRewrite.rewritten !== msg.queryRewrite.original"
          class="query-rewrite"
        >
          <span>理解为：</span>{{ msg.queryRewrite.rewritten }}
        </div>

        <!-- 可验证处理步骤：只展示动作摘要，不展示模型思维链 -->
        <div
          v-if="msg.role === 'assistant' && msg.thinkingSteps && msg.thinkingSteps.length"
          class="thinking-panel"
        >
          <el-collapse>
            <el-collapse-item>
              <template #title>
                <div class="thinking-title">
                  <el-icon :size="14" color="#409eff"><Loading /></el-icon>
                  <span>处理过程（{{ msg.thinkingSteps.filter(s => s.status === 'success').length }}/{{ msg.thinkingSteps.length }} 步完成）</span>
                </div>
              </template>
              <div class="thinking-steps">
                <div
                  v-for="step in msg.thinkingSteps"
                  :key="step.agent_id"
                  class="thinking-step"
                  :class="step.status"
                >
                  <el-icon :size="14" class="step-icon">
                    <CircleCheck v-if="step.status === 'success'" color="#67c23a" />
                    <Loading v-else-if="step.status === 'running'" color="#409eff" />
                    <CircleClose v-else color="#f56c6c" />
                  </el-icon>
                  <span class="step-name">{{ step.agent_name }}</span>
                  <span v-if="step.summary" class="step-summary">{{ step.summary }}</span>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- Grounded Answer 来源 -->
        <div v-if="msg.role === 'assistant' && msg.sources?.length" class="source-row">
          <span class="source-label">数据依据</span>
          <span v-for="source in msg.sources" :key="source.label" class="source-chip">
            <span class="source-dot" />{{ source.label }}
          </span>
        </div>

        <!-- 深链按钮 + 快捷追问 chips -->
        <div
          v-if="msg.role === 'assistant' && ((msg.links && msg.links.length) || (msg.quickReplies && msg.quickReplies.length))"
          class="msg-extras"
        >
          <el-button
            v-for="l in msg.links || []"
            :key="'l' + l.to + l.label"
            size="small"
            type="primary"
            @click="router.push(l.to)"
          >
            {{ l.label }} →
          </el-button>
          <button
            v-for="qr in msg.quickReplies || []"
            :key="'q' + qr"
            class="intent-chip"
            @click="handleSend(qr)"
          >
            {{ qr }}
          </button>
        </div>

        <!-- 推荐房源横条 -->
        <div
          v-if="msg.role === 'assistant' && msg.recommendations && msg.recommendations.length"
          class="rec-carousel-wrap"
        >
          <div class="rec-carousel-head">
            <span>为你找到 {{ msg.allRecommendations?.length || msg.recommendations.length }} 套，先看前 {{ msg.recommendations.length }} 套</span>
            <el-tag v-if="msg.aiAvailable === false" size="small" type="warning">
              AI 分析暂不可用
            </el-tag>
            <span class="rec-carousel-hint">← 左右滑动查看 →</span>
          </div>
          <div class="rec-carousel">
            <div
              v-for="(rec, recIndex) in msg.recommendations"
              :key="rec.property_id"
              class="rec-card"
              :class="{ selected: isSelected(rec.property_id) }"
              @click="goDetail(rec.property_id)"
            >
              <div class="rec-card-img">
                <span class="rec-rank">{{ rec.rank || recIndex + 1 }}</span>
                <img
                  v-if="imageUrl(rec.property)"
                  :src="imageUrl(rec.property)!"
                  :alt="rec.property.title"
                />
                <div v-else class="rec-img-placeholder">
                  <el-icon :size="24" color="#c0c4cc"><PictureFilled /></el-icon>
                </div>
              </div>
              <div class="rec-card-body">
                <div class="rec-card-title" :title="rec.property.title">
                  {{ rec.property.title }}
                </div>
                <div class="rec-card-tags">
                  <el-tag size="small" type="info">{{ propertyTypeLabel(rec.property.property_type) }}</el-tag>
                  <el-tag size="small">{{ rec.property.bedrooms }}室{{ rec.property.bathrooms }}卫</el-tag>
                  <el-tag v-if="rec.property.area_sqm" size="small" type="info">
                    {{ rec.property.area_sqm }}㎡
                  </el-tag>
                </div>
                <div class="rec-card-addr">
                  <el-icon :size="12"><LocationFilled /></el-icon>
                  {{ rec.property.district }}
                </div>
                <!-- AI 推荐理由 -->
                <div v-if="rec.match_reason" class="rec-card-reason" :title="rec.match_reason">
                  <el-icon :size="12" color="#67c23a"><Star /></el-icon>
                  {{ rec.match_reason }}
                </div>
                <!-- 房源亮点（pros） -->
                <div v-if="rec.pros && rec.pros.length" class="rec-card-pros">
                  <span v-for="p in rec.pros.slice(0, 3)" :key="p" class="pro-tag">✓ {{ p }}</span>
                </div>
                <!-- 设施特点 -->
                <div v-if="getCardAmenities(rec.property).length" class="rec-card-amenities">
                  <span v-for="a in getCardAmenities(rec.property).slice(0, 4)" :key="a" class="amenity-dot">{{ a }}</span>
                </div>
                <div class="rec-card-foot">
                  <span class="rec-card-price">
                    {{ formatRent(rec.property) }}<i v-if="rec.property.price_monthly != null">/月</i>
                  </span>
                </div>
                <div class="rec-card-acts">
                  <el-button
                    size="small"
                    :type="inCart(rec.property_id) ? 'success' : 'primary'"
                    @click.stop="handleToggleCart(rec)"
                  >
                    {{ inCart(rec.property_id) ? '已加入 ✕' : '加入候选清单' }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 渐进搜索与约束消融建议 -->
        <div
          v-if="msg.role === 'assistant' && msg.guidedOptions?.length"
          class="guided-row"
        >
          <span class="guided-label">继续调整</span>
          <button
            v-for="option in msg.guidedOptions"
            :key="option.kind + option.label"
            class="guided-chip"
            :disabled="sending"
            @click="handleGuidedOption(option)"
          >
            <span v-if="option.icon">{{ option.icon }}</span>{{ option.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ 输入区 ═══ -->
    <div class="chat-input-area">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="描述你的租房需求，或问「押金怎么退」「合同怎么签」"
        @keydown.enter.exact.prevent="handleSend()"
      />
      <el-button
        type="primary"
        :loading="sending"
        :disabled="!inputText.trim()"
        class="send-btn"
        @click="handleSend()"
      >
        发送
      </el-button>
    </div>

    <!-- ═══ 浮动购物车角标 ═══ -->
    <button v-show="!cartOpen" class="cart-fab" :style="{ left: `${sidebarWidth + 24}px` }" @click="cartOpen = true">
      <el-icon :size="20"><ShoppingCart /></el-icon>
      <span>候选清单</span>
      <span v-if="cartItems.length" class="cart-fab-badge">{{ cartItems.length }}</span>
    </button>

    <!-- ═══ 候选清单抽屉 ═══ -->
    <el-drawer
      v-model="cartOpen"
      :size="drawerSize"
      title="候选清单"
      direction="rtl"
    >
      <template #header>
        <div class="drawer-header">
          <span>候选清单</span>
          <span class="drawer-count">{{ cartItems.length }} 套</span>
        </div>
      </template>

      <div class="cart-drawer-body">
        <div v-if="cartItems.length === 0" class="cart-empty">
          <el-icon :size="36" color="#dcdfe6"><ShoppingCart /></el-icon>
          <p>还没有候选房源</p>
          <p class="chat-hint">在推荐横条上点「加入候选清单」</p>
        </div>

        <template v-else>
          <div class="cart-toolbar">
            <el-checkbox v-model="cartAllSelected">全选候选</el-checkbox>
            <span class="cart-toolbar-hint">已勾选 {{ selectedIds.length }} 套用于对比</span>
          </div>
          <div class="cart-list">
            <div v-for="item in cartItems" :key="item.id" class="cart-item">
              <el-checkbox
                class="cart-item-check"
                :model-value="isSelected(item.property_id)"
                @change="(v: boolean) => toggleSelect(item.property_id, v)"
              />
              <div class="cart-item-image">
                <img
                  v-if="imageUrl(item.property)"
                  :src="imageUrl(item.property)!"
                  :alt="item.property.title"
                />
                <div v-else class="rec-img-placeholder">
                  <el-icon :size="18" color="#c0c4cc"><PictureFilled /></el-icon>
                </div>
              </div>
              <div class="cart-item-info">
                <div class="cart-item-title" :title="item.property.title">{{ item.property.title }}</div>
                <div class="cart-item-meta">
                  {{ item.property.district }} · {{ formatRent(item.property) }}<template v-if="item.property.price_monthly != null">/月</template>
                </div>
                <div v-if="item.reason" class="cart-item-reason" :title="item.reason">{{ item.reason }}</div>
              </div>
              <el-button
                size="small"
                text
                type="danger"
                :icon="Delete"
                class="cart-item-remove"
                @click="handleRemoveFromCart(item.property_id)"
              />
            </div>
          </div>
        </template>
      </div>

      <template #footer>
        <div class="cart-drawer-footer">
          <el-button
            type="primary"
            :disabled="!canCompare"
            :loading="comparing"
            style="width: 100%"
            @click="handleCompare"
          >
            {{ compareLabel }}
          </el-button>
          <p class="cart-drawer-tip">勾选任意推荐/候选房源（≥2 套）即可对比，跨区域也行</p>
        </div>
      </template>
    </el-drawer>

    <!-- ═══ 对比结果弹窗 ═══ -->
    <el-dialog v-model="compareVisible" title="房源对比分析" width="980px" top="5vh">
      <template v-if="compareResult">
        <div class="compare-priority-row">
          <span class="compare-priority-label">我更看重</span>
          <el-radio-group
            v-model="comparePriority"
            size="small"
            :disabled="comparing"
            @change="rerunCompare"
          >
            <el-radio-button value="balanced">均衡</el-radio-button>
            <el-radio-button value="budget">预算优先</el-radio-button>
            <el-radio-button value="commute">通勤优先</el-radio-button>
            <el-radio-button value="space">空间优先</el-radio-button>
          </el-radio-group>
          <span class="compare-priority-hint">基于真实价格、通勤、空间和评价给出建议</span>
        </div>

        <el-alert
          :title="compareResult.summary"
          :type="compareResult.ai_available ? 'success' : 'warning'"
          :closable="false"
          class="compare-summary"
        />
        <el-table v-loading="comparing" :data="compareResult.items" stripe class="compare-table">
          <el-table-column label="房源" min-width="150">
            <template #default="{ row }">
              <el-link type="primary" @click="goDetail(row.property_id)">{{ row.title }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="月租" width="95">
            <template #default="{ row }">
              <span v-if="row.property">{{ formatRent(row.property) }}</span>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column label="区域/面积" width="125">
            <template #default="{ row }">
              <span v-if="row.property">
                {{ row.property.district }}<template v-if="row.property.area_sqm"> · {{ row.property.area_sqm }}㎡</template>
              </span>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column label="通勤" min-width="120">
            <template #default="{ row }">{{ row.commute || '暂无数据' }}</template>
          </el-table-column>
          <el-table-column label="评分" width="95">
            <template #default="{ row }">
              <span v-if="row.rating != null">★ {{ row.rating }}（{{ row.review_count }}条）</span>
              <span v-else>暂无</span>
            </template>
          </el-table-column>
          <el-table-column label="优势" min-width="140">
            <template #default="{ row }">
              <el-tag v-for="p in row.pros" :key="p" size="small" type="success" effect="plain" class="compare-tag">{{ p }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="劣势" min-width="120">
            <template #default="{ row }">
              <el-tag v-for="c in row.cons" :key="c" size="small" type="warning" effect="plain" class="compare-tag">{{ c }}</el-tag>
              <span v-if="!row.cons.length">—</span>
            </template>
          </el-table-column>
          <el-table-column label="适合人群" min-width="100">
            <template #default="{ row }">{{ row.best_for || '—' }}</template>
          </el-table-column>
        </el-table>
        <div class="compare-recommendation">
          <el-icon color="#409eff"><Star /></el-icon>
          {{ compareResult.recommendation }}
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Delete,
  Loading,
  LocationFilled,
  PictureFilled,
  ShoppingCart,
  Star,
} from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'
import { getImageUrl } from '@/utils/image'
import { agentService } from '@/services/agent'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'
import type {
  AgentRecommendation,
  AgentStreamMeta,
  ComparePriority,
  CompareResponse,
  GuidedOption,
  ThinkingStep,
} from '@/types/agent'
import type { PropertySearchResult, PropertyType } from '@/types/property'

const router = useRouter()
const route = useRoute()
const cartStore = useCartStore()
const { items: cartItems } = storeToRefs(cartStore)
const agentChat = useAgentChatStore()
const { sessionId, messages, aiAvailable } = storeToRefs(agentChat)

const typeLabels: Record<PropertyType, string> = {
  studio: '单间',
  '1-bed': '一室',
  '2-bed': '两室+',
  shared: '合租',
  house: '别墅',
}

// ── 状态 ────────────────────────────────────────────────────────
const inputText = ref('')
const sending = ref(false)
const comparing = ref(false)
const compareVisible = ref(false)
const compareResult = ref<CompareResponse | null>(null)
const comparePriority = ref<ComparePriority>('balanced')
const lastCompareIds = ref<number[] | undefined>(undefined)
const chatListRef = ref<HTMLElement | null>(null)
let scrollFrame: number | null = null

const latestStateSummary = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const summary = messages.value[index].stateSummary
    if (summary) return summary
  }
  return null
})

// 对比选择
const selectedIds = ref<number[]>([])

// 购物车抽屉
const windowWidth = ref(window.innerWidth)
const cartOpen = ref(false)
const drawerSize = computed(() => (windowWidth.value >= 900 ? 360 : '85%'))

// 侧边栏宽度追踪 —— cart-fab 动态偏移
const sidebarWidth = ref(64)
let sidebarObserver: ResizeObserver | null = null

function updateSidebarWidth() {
  const sidebar = document.querySelector('.layout-sidebar')
  if (sidebar) sidebarWidth.value = sidebar.clientWidth
}

function onResize() {
  windowWidth.value = window.innerWidth
  updateSidebarWidth()
}

// ── 选择 ────────────────────────────────────────────────────────
function isSelected(propertyId: number): boolean {
  return selectedIds.value.includes(propertyId)
}

function toggleSelect(propertyId: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(propertyId)) selectedIds.value.push(propertyId)
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== propertyId)
  }
}

const cartAllSelected = computed<boolean>({
  get: () =>
    cartItems.value.length > 0 &&
    cartItems.value.every((it) => selectedIds.value.includes(it.property_id)),
  set: (val) => {
    const cartIds = cartItems.value.map((it) => it.property_id)
    if (val) {
      for (const id of cartIds) {
        if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
      }
    } else {
      selectedIds.value = selectedIds.value.filter((id) => !cartIds.includes(id))
    }
  },
})

const canCompare = computed(
  () => selectedIds.value.length >= 2 || (selectedIds.value.length === 0 && cartItems.value.length >= 2),
)
const compareLabel = computed(() => {
  if (selectedIds.value.length >= 2) return `对比所选（${selectedIds.value.length}）`
  if (selectedIds.value.length === 0 && cartItems.value.length >= 2) return `对比候选清单（${cartItems.value.length}）`
  return '对比所选'
})

// ── 工具 ────────────────────────────────────────────────────────
function imageUrl(property: PropertySearchResult): string | null {
  const images = property.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  return getImageUrl(primary.filename)
}

/** 只展示后端返回的真实设施字段，不按价格或户型猜测。 */
function getCardAmenities(property: PropertySearchResult): string[] {
  return [...new Set((property.amenities || []).filter(Boolean))]
}

function propertyTypeLabel(propertyType: string | null | undefined): string {
  if (!propertyType) return '户型待确认'
  return typeLabels[propertyType as PropertyType] || propertyType
}

function formatRent(property: PropertySearchResult): string {
  if (property.price_monthly == null) return '价格待确认'
  const symbols: Record<string, string> = {
    CNY: '¥',
    GBP: '£',
    SGD: 'S$',
    USD: '$',
    HKD: 'HK$',
  }
  const currency = (property.currency || 'CNY').toUpperCase()
  const amount = Number(property.price_monthly).toLocaleString('zh-CN', {
    maximumFractionDigits: 0,
  })
  return `${symbols[currency] || `${currency} `}${amount}`
}

function inCart(propertyId: number): boolean {
  return cartItems.value.some((item) => item.property_id === propertyId)
}

function goDetail(propertyId: number) {
  router.push(`/property/${propertyId}`)
}

async function scrollChatToBottom() {
  await nextTick()
  if (chatListRef.value) {
    chatListRef.value.scrollTop = chatListRef.value.scrollHeight
  }
}

function scheduleScrollToBottom() {
  if (scrollFrame !== null) return
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = null
    void scrollChatToBottom()
  })
}

// ── 发送消息 ────────────────────────────────────────────────────
async function handleSend(preset?: string, filterPatch?: Record<string, unknown> | null) {
  const text = (preset ?? inputText.value).trim()
  if (!text || sending.value) return

  // 未登录时创建临时会话（游客模式）
  if (sessionId.value === null) {
    try {
      await agentChat.ensureSession()
    } catch {
      ElMessage.error('会话创建失败，请刷新重试')
      return
    }
  }

  messages.value.push({ role: 'user', content: text })
  const assistantMessage = agentChat.appendStreamingAssistant({
    thinkingSteps: [],
  })
  if (!preset) inputText.value = ''
  sending.value = true
  await scrollChatToBottom()
  let cartChanged = false

  try {
    await agentService.sendMessageStream(
      sessionId.value!,
      {
        message: text,
        filters: (filterPatch || undefined) as any,
        mode: 'auto',
      },
      {
        onToken(token) {
          assistantMessage.content += token
          scheduleScrollToBottom()
        },
        onMeta(meta: AgentStreamMeta) {
          if (meta.thinking_steps) assistantMessage.thinkingSteps = meta.thinking_steps
          if (meta.query_rewrite) assistantMessage.queryRewrite = meta.query_rewrite
          if (meta.sources) assistantMessage.sources = meta.sources
          if (meta.state_summary) assistantMessage.stateSummary = meta.state_summary
          if (meta.guided_options) assistantMessage.guidedOptions = meta.guided_options
          if (meta.quick_replies) assistantMessage.quickReplies = meta.quick_replies
          if (meta.links) assistantMessage.links = meta.links
          if (meta.ai_available !== undefined) {
            assistantMessage.aiAvailable = meta.ai_available
            aiAvailable.value = meta.ai_available
          }
          if (meta.recommendations) {
            assistantMessage.allRecommendations = meta.recommendations
          }
          if (meta.top_picks?.length) {
            assistantMessage.topPicks = meta.top_picks
            assistantMessage.recommendations = meta.top_picks
          } else if (meta.recommendations?.length) {
            assistantMessage.recommendations = meta.recommendations.slice(0, 3)
          }
          if (meta.cart_changed) cartChanged = true
          scheduleScrollToBottom()
        },
        onError(message) {
          if (!assistantMessage.content) assistantMessage.content = `抱歉，${message}`
        },
      },
    )
    if (!assistantMessage.content) {
      assistantMessage.content = '这次没有生成有效回复，请换一种说法再试。'
    }
    if (cartChanged) {
      await cartStore.fetch()
    }
  } catch (error) {
    const errorText = error instanceof Error ? error.message : '请求失败了，请稍后再试。'
    assistantMessage.content = assistantMessage.content
      ? `${assistantMessage.content}\n\n（连接中断：${errorText}）`
      : `抱歉，${errorText}`
  } finally {
    assistantMessage.streaming = false
    sending.value = false
    await scrollChatToBottom()
  }
}

function handleGuidedOption(option: GuidedOption) {
  void handleSend(option.message || option.label, option.filter_patch)
}

async function handleToggleCart(rec: AgentRecommendation) {
  try {
    if (inCart(rec.property_id)) {
      await cartStore.remove(rec.property_id)
      toggleSelect(rec.property_id, false)
      ElMessage.info(`已从候选清单移出「${rec.property.title}」`)
    } else {
      await cartStore.add(rec.property_id, rec.match_reason || undefined)
      ElMessage.success(`已将「${rec.property.title}」加入候选清单`)
    }
  } catch {
    // ignore
  }
}

async function handleRemoveFromCart(propertyId: number) {
  try {
    await cartStore.remove(propertyId)
    toggleSelect(propertyId, false)
  } catch {
    // ignore
  }
}

async function handleCompare() {
  if (!canCompare.value) return
  lastCompareIds.value = selectedIds.value.length >= 2 ? [...selectedIds.value] : undefined
  await runCompare()
  if (compareResult.value) compareVisible.value = true
}

async function rerunCompare() {
  await runCompare()
}

async function runCompare() {
  comparing.value = true
  try {
    compareResult.value = await agentService.compareCart(lastCompareIds.value, comparePriority.value)
  } catch {
    // ignore
  } finally {
    comparing.value = false
  }
}

// ── 初始化 ──────────────────────────────────────────────────────
onMounted(async () => {
  window.addEventListener('resize', onResize)

  // 监听侧边栏宽度变化，动态偏移 cart-fab
  updateSidebarWidth()
  const sidebar = document.querySelector('.layout-sidebar')
  if (sidebar) {
    sidebarObserver = new ResizeObserver(() => updateSidebarWidth())
    sidebarObserver.observe(sidebar)
  }

  // 读取 URL 查询参数，自动发送首条消息
  const qParam = route.query.q
  if (qParam && typeof qParam === 'string' && qParam.trim()) {
    try {
      await agentChat.ensureSession()
    } catch {
      // 游客模式：会话创建失败则跳过
    }
    inputText.value = qParam.trim()
    await handleSend()
  } else {
    try {
      await agentChat.ensureSession()
    } catch {
      // 游客模式静默失败
    }
  }

  try {
    await cartStore.fetch()
  } catch {
    // 未登录无购物车
  }
  await scrollChatToBottom()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  sidebarObserver?.disconnect()
  if (scrollFrame !== null) window.cancelAnimationFrame(scrollFrame)
})
</script>

<style scoped>
/* ── 整体布局 ─────────────────────── */
.chat-page {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  background: #fafbfc;
}

/* ── 内容标题栏 ───────────────────── */
.chat-content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 12px 0;
  flex-shrink: 0;
}

.chat-content-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.chat-content-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.memory-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin: -2px 0 10px;
  padding: 9px 12px;
  border: 1px solid #e7edf5;
  border-radius: 10px;
  background: #f7faff;
}

.memory-label {
  color: #7a8798;
  font-size: 12px;
}

.memory-chip {
  padding: 3px 8px;
  border-radius: 999px;
  color: #315b86;
  background: #eaf3ff;
  font-size: 12px;
}

.mode-label {
  font-size: 12px;
  color: #909399;
}

/* ── 消息区 ───────────────────────── */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #fafbfc;
}

.chat-empty {
  margin: auto;
  text-align: center;
  color: #909399;
  font-size: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.chat-hint {
  color: #c0c4cc;
  font-size: 12px;
}

.msg-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-bubble-row {
  display: flex;
}

.chat-bubble-row.user {
  justify-content: flex-end;
}

.chat-bubble {
  max-width: 80%;
  padding: 9px 13px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-bubble.user {
  background: var(--el-color-primary, #409eff);
  color: #fff;
  border-bottom-right-radius: 2px;
}

.chat-bubble.assistant {
  background: #fff;
  color: #303133;
  border-bottom-left-radius: 2px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.query-rewrite {
  width: fit-content;
  max-width: min(720px, 88%);
  margin: 6px 0 0 42px;
  padding: 6px 10px;
  border-left: 2px solid #a8c8ee;
  color: #738195;
  font-size: 12px;
  line-height: 1.55;
}

.query-rewrite span {
  color: #4d6683;
  font-weight: 600;
}

.source-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin: 8px 0 0 42px;
}

.source-label,
.guided-label {
  color: #9099a8;
  font-size: 12px;
}

.source-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border: 1px solid #dfe8df;
  border-radius: 999px;
  color: #58725b;
  background: #f5faf5;
  font-size: 11px;
}

.source-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #67c23a;
}

.chat-bubble.typing {
  color: #909399;
  background: #f4f4f5;
}

/* ── 思考步骤面板 ────────────────── */
.thinking-panel {
  margin: 0 0 4px 0;
  font-size: 12px;
}

.thinking-panel :deep(.el-collapse-item__header) {
  height: 32px;
  line-height: 32px;
  padding: 0 10px;
  background: #f0f7ff;
  border-radius: 6px;
  border: 1px solid #d6e8ff;
  font-size: 12px;
}

.thinking-panel :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.thinking-panel :deep(.el-collapse-item__content) {
  padding: 8px 10px 4px;
}

.thinking-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #409eff;
}

.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.thinking-step {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.thinking-step.success {
  color: #303133;
}

.thinking-step.error {
  color: #f56c6c;
}

.step-icon {
  flex-shrink: 0;
}

.step-name {
  font-weight: 500;
  white-space: nowrap;
}

.step-summary {
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 深链按钮 + 追问 chips ────────── */
.intent-chip {
  border: 1px solid var(--el-color-primary, #409eff);
  background: #fff;
  color: var(--el-color-primary, #409eff);
  font-size: 12px;
  line-height: 1.4;
  padding: 4px 12px;
  border-radius: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.intent-chip:hover {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.msg-extras {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
  padding-left: 4px;
}

/* ── 输入区 ───────────────────────── */
.chat-input-area {
  border-top: 1px solid #e4e7ed;
  padding: 10px 16px;
  display: flex;
  gap: 8px;
  align-items: flex-end;
  background: #fff;
  flex-shrink: 0;
}

.send-btn {
  flex-shrink: 0;
}

/* ── 推荐横条 ─────────────────────── */
.rec-carousel-wrap {
  /* 推荐卡片在所有 Agent 回复中都先于文字展示。 */
  order: -1;
  background: #fafbfc;
  border: 1px solid #eef0f3;
  border-radius: 10px;
  padding: 10px 12px 12px;
}

.rec-carousel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 10px;
}

.rec-carousel-hint {
  margin-left: auto;
  font-weight: 400;
  color: #c0c4cc;
  font-size: 11px;
}

.rec-carousel {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 6px;
  scroll-snap-type: x proximity;
}

.rec-carousel::-webkit-scrollbar {
  height: 6px;
}
.rec-carousel::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.rec-card {
  flex: 0 0 260px;
  width: 260px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  scroll-snap-align: start;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.rec-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
}

.rec-card.selected {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff);
}

.rec-card-img {
  position: relative;
  height: 116px;
  background: #f5f7fa;
}

.rec-rank {
  position: absolute;
  z-index: 2;
  top: 7px;
  left: 7px;
  display: grid;
  width: 23px;
  height: 23px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: rgb(32 45 64 / 82%);
  font-size: 12px;
  font-weight: 700;
}

.rec-card-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.rec-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rec-card-check {
  position: absolute;
  top: 6px;
  left: 6px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 5px;
  padding: 1px 7px;
  line-height: 1;
}

.rec-card-check :deep(.el-checkbox__label) {
  font-size: 12px;
  padding-left: 5px;
}

.rec-card-body {
  padding: 9px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: 1;
}

.rec-card-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.guided-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0 0 42px;
}

.guided-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: 1px solid #d7e4f5;
  border-radius: 999px;
  color: #356691;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: 0.18s ease;
}

.guided-chip:hover:not(:disabled) {
  border-color: #8fb8e7;
  background: #f3f8ff;
  transform: translateY(-1px);
}

.guided-chip:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.rec-card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.rec-card-addr {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-card-reason {
  font-size: 11px;
  color: #67c23a;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── AI 亮点标签 ──────────────────── */
.rec-card-pros {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.pro-tag {
  font-size: 10px;
  color: #67c23a;
  background: #f0f9eb;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
  line-height: 1.6;
}

/* ── 设施特点 ─────────────────────── */
.rec-card-amenities {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.amenity-dot {
  font-size: 10px;
  color: #909399;
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
  line-height: 1.5;
}

.rec-card-foot {
  margin-top: auto;
}

.rec-card-price {
  font-size: 17px;
  font-weight: 700;
  color: var(--danger, #f56c6c);
}

.rec-card-price i {
  font-size: 11px;
  font-weight: 400;
  font-style: normal;
  color: #909399;
}

.rec-card-acts {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 4px;
}

/* ── 购物车 FAB ───────────────────── */
.cart-fab {
  position: fixed;
  left: 24px;
  bottom: 28px;
  z-index: 2000;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 18px;
  border: none;
  border-radius: 26px;
  background: var(--el-color-primary, #409eff);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(64, 158, 255, 0.4);
  transition: transform 0.15s, box-shadow 0.15s;
}

.cart-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 22px rgba(64, 158, 255, 0.5);
}

.cart-fab-badge {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #fff;
  color: var(--el-color-primary, #409eff);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── 购物车抽屉 ───────────────────── */
.drawer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
}

.drawer-count {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

.cart-drawer-body {
  height: 100%;
}

.cart-empty {
  padding: 60px 0;
  text-align: center;
  color: #909399;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.cart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px 10px;
  border-bottom: 1px solid #f0f2f5;
  margin-bottom: 6px;
}

.cart-toolbar-hint {
  font-size: 12px;
  color: #909399;
}

.cart-list {
  display: flex;
  flex-direction: column;
}

.cart-item {
  display: flex;
  gap: 8px;
  padding: 10px 2px;
  border-bottom: 1px solid #f0f2f5;
  align-items: center;
}

.cart-item-check {
  flex-shrink: 0;
}

.cart-item-image {
  flex-shrink: 0;
  width: 58px;
  height: 46px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}

.cart-item-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cart-item-info {
  flex: 1;
  min-width: 0;
}

.cart-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cart-item-meta {
  font-size: 12px;
  color: #909399;
}

.cart-item-reason {
  font-size: 11px;
  color: #b88230;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cart-item-remove {
  flex-shrink: 0;
}

.cart-drawer-footer {
  width: 100%;
}

.cart-drawer-tip {
  margin-top: 8px;
  font-size: 11px;
  color: #c0c4cc;
  text-align: center;
}

/* ── 对比弹窗 ─────────────────────── */
.compare-priority-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.compare-priority-label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.compare-priority-hint {
  font-size: 12px;
  color: #c0c4cc;
}

.compare-summary {
  margin-bottom: 14px;
}

.compare-table {
  width: 100%;
}

.compare-tag {
  margin: 2px 4px 2px 0;
}

.compare-recommendation {
  margin-top: 14px;
  padding: 10px 14px;
  background: #ecf5ff;
  border-radius: 6px;
  font-size: 13px;
  color: #303133;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  line-height: 1.6;
}

/* ── 响应式 ───────────────────────── */
@media (max-width: 768px) {
  .chat-content-header {
    padding: 0 0 8px 0;
  }

  .chat-messages {
    padding: 10px 12px;
  }

  .chat-bubble {
    max-width: 90%;
  }

  .rec-card {
    flex: 0 0 240px;
    width: 240px;
  }
}
</style>
