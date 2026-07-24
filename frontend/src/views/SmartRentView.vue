<template>
  <div class="chat-page">
    <!-- ═══ 页面标题栏 ═══ -->
    <div class="chat-content-header">
      <div class="chat-content-title">
        <el-icon :size="18" color="#409eff"><ChatDotRound /></el-icon>
        <span>智能租房</span>
        <el-tag v-if="!aiAvailable" size="small" type="warning">AI 暂不可用</el-tag>
      </div>
      <div class="chat-content-actions">
        <el-radio-group
          v-model="agentMode"
          size="small"
          class="mode-switcher"
        >
          <el-radio-button value="auto">🤖 智能</el-radio-button>
          <el-radio-button value="default">⚡ 快速</el-radio-button>
          <el-radio-button value="handoff">🧠 深度</el-radio-button>
        </el-radio-group>
      </div>
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
          <div class="chat-bubble" :class="msg.role">{{ msg.content }}</div>
        </div>

        <!-- 专家模式：思考步骤 -->
        <div
          v-if="msg.role === 'assistant' && msg.thinkingSteps && msg.thinkingSteps.length"
          class="thinking-panel"
        >
          <el-collapse>
            <el-collapse-item>
              <template #title>
                <div class="thinking-title">
                  <el-icon :size="14" color="#409eff"><Loading /></el-icon>
                  <span>分析过程（{{ msg.thinkingSteps.filter(s => s.status === 'success').length }}/{{ msg.thinkingSteps.length }} 步完成）</span>
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
            <span>为你找到 {{ msg.recommendations.length }} 套推荐</span>
            <el-tag v-if="msg.aiAvailable === false" size="small" type="warning">
              AI 分析暂不可用
            </el-tag>
            <span class="rec-carousel-hint">← 左右滑动查看 →</span>
          </div>
          <div class="rec-carousel">
            <div
              v-for="rec in msg.recommendations"
              :key="rec.property_id"
              class="rec-card"
              :class="{ selected: isSelected(rec.property_id) }"
              @click="goDetail(rec.property_id)"
            >
              <div class="rec-card-img">
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
                  <el-tag size="small" type="info">{{ typeLabels[rec.property.property_type] }}</el-tag>
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
                  <span class="rec-card-price">¥{{ rec.property.price_monthly }}<i>/月</i></span>
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
      </div>

      <div v-if="sending" class="chat-bubble-row assistant">
        <div class="chat-bubble assistant typing">
          {{ agentMode === 'handoff' ? '多 Agent 深度分析中，请稍候…' : agentMode === 'auto' ? '智能分析中，请稍候…' : '正在思考…' }}
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
                <div class="cart-item-meta">{{ item.property.district }} · ¥{{ item.property.price_monthly }}/月</div>
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
          <span class="compare-priority-hint">得分由真实数据按权重计算，AI 只负责解读</span>
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
              <span v-if="row.property">¥{{ row.property.price_monthly }}</span>
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
          <el-table-column label="综合得分" width="120" sortable prop="score">
            <template #default="{ row }">
              <el-tooltip placement="left" :content="breakdownText(row)">
                <el-progress :percentage="row.score" :stroke-width="10" :color="scoreColor(row.score)" />
              </el-tooltip>
            </template>
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
  AgentChatMessage,
  AgentRecommendation,
  CompareItem,
  ComparePriority,
  CompareResponse,
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

// ── 模式：auto=智能自动, default=快速(linear), handoff=深度(多Agent交接) ──
const agentMode = ref<string>('auto')

// ── 状态 ────────────────────────────────────────────────────────
const inputText = ref('')
const sending = ref(false)
const comparing = ref(false)
const compareVisible = ref(false)
const compareResult = ref<CompareResponse | null>(null)
const comparePriority = ref<ComparePriority>('balanced')
const lastCompareIds = ref<number[] | undefined>(undefined)
const chatListRef = ref<HTMLElement | null>(null)

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

/** 从房源属性推断设施特点标签 */
function getCardAmenities(property: PropertySearchResult): string[] {
  const tags: string[] = []
  const p = property
  if (p.property_type === '1-bed' || p.property_type === '2-bed') { tags.push('电梯'); tags.push('WiFi') }
  else if (p.property_type === 'studio') { tags.push('独立卫浴'); tags.push('WiFi') }
  else if (p.property_type === 'house') { tags.push('车位'); tags.push('全屋家电') }
  else if (p.property_type === 'shared') { tags.push('包水电'); tags.push('WiFi') }
  if ((p.area_sqm ?? 0) > 60) tags.push('阳台')
  if (p.bedrooms >= 2) tags.push('近地铁')
  if (p.price_monthly < 3000) tags.push('高性价比')
  else if (p.price_monthly > 8000) tags.push('精装修')
  if (p.description) {
    if (/短租/.test(p.description)) tags.push('可短租')
    if (/宠物|猫|狗/.test(p.description)) tags.push('可养宠物')
    if (/暖气/.test(p.description)) tags.push('暖气')
  }
  return [...new Set(tags)]
}

function inCart(propertyId: number): boolean {
  return cartItems.value.some((item) => item.property_id === propertyId)
}

function goDetail(propertyId: number) {
  router.push(`/property/${propertyId}`)
}

function scoreColor(score: number): string {
  if (score >= 85) return '#67c23a'
  if (score >= 70) return '#409eff'
  return '#e6a23c'
}

async function scrollChatToBottom() {
  await nextTick()
  if (chatListRef.value) {
    chatListRef.value.scrollTop = chatListRef.value.scrollHeight
  }
}

// ── 发送消息 ────────────────────────────────────────────────────
async function handleSend(preset?: string) {
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
  if (!preset) inputText.value = ''
  sending.value = true
  await scrollChatToBottom()

  const mode = agentMode.value === 'auto' ? null : agentMode.value

  try {
    const resp = await agentService.sendMessage(sessionId.value!, {
      message: text,
      mode,
    })
    messages.value.push({
      role: 'assistant',
      content: resp.reply,
      recommendations: resp.intent === 'recommend' ? resp.recommendations : undefined,
      aiAvailable: resp.ai_available,
      quickReplies: resp.quick_replies,
      links: resp.links,
      thinkingSteps: (resp as any).thinking_steps || [],
    } as AgentChatMessage)
    aiAvailable.value = resp.ai_available
    if (resp.cart_changed) {
      await cartStore.fetch()
    }
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，请求失败了，请稍后再试。' })
  } finally {
    sending.value = false
    await scrollChatToBottom()
  }
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

const dimensionLabels: Record<string, string> = {
  price: '价格',
  commute: '通勤',
  space: '空间',
  rating: '评价',
}

function breakdownText(row: CompareItem): string {
  if (!row.score_breakdown) return `综合 ${row.score} 分`
  const parts = Object.entries(row.score_breakdown).map(
    ([k, v]) => `${dimensionLabels[k] ?? k} ${v}`,
  )
  return `综合 ${row.score} 分 ｜ ` + parts.join(' · ')
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
