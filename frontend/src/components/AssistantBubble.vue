<template>
  <!-- 浮动 AI 管家：全站唯一的找房/对比入口，登录用户任意页面可见。
       用 v-show 而非 v-if：切换路由时组件不卸载，会话与消息保留。 -->
  <teleport to="body">
    <div v-show="visible" class="ab-root" :style="rootStyle">
      <!-- 气泡按钮（可拖动） -->
      <button v-show="!open" class="ab-fab" @pointerdown="onDragStart" @click="onFabClick">
        <el-icon :size="20"><ChatDotRound /></el-icon>
        <span>AI 管家</span>
      </button>

      <!-- 对话面板（标题栏可拖动） -->
      <transition name="ab-pop">
        <div v-show="open" class="ab-panel" :class="{ 'is-max': maximized }">
          <div class="ab-header" @pointerdown="onDragStart">
            <div class="ab-title">
              <el-icon :size="16" color="#409eff"><ChatDotRound /></el-icon>
              <span>{{ view === 'cart' ? '候选清单' : 'AI 租房管家' }}</span>
            </div>
            <div class="ab-header-acts">
              <el-tooltip content="对话列表" placement="bottom">
                <el-button
                  size="small"
                  text
                  :type="view === 'sessions' ? 'primary' : ''"
                  @click="openSessions"
                >
                  <el-icon :size="15"><ChatLineSquare /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="新对话" placement="bottom">
                <el-button size="small" text @click="handleNewSession">
                  <el-icon :size="15"><Plus /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="候选清单" placement="bottom">
                <el-badge :value="cartStore.count" :hidden="cartStore.count === 0" :max="99">
                  <el-button
                    size="small"
                    text
                    :type="view === 'cart' ? 'primary' : ''"
                    @click="view = view === 'cart' ? 'chat' : 'cart'"
                  >
                    <el-icon :size="15"><ShoppingCart /></el-icon>
                  </el-button>
                </el-badge>
              </el-tooltip>
              <el-tooltip :content="maximized ? '还原窗口' : '放大窗口'" placement="bottom">
                <el-button size="small" text type="primary" @click="maximized = !maximized">
                  <el-icon :size="15"><ScaleToOriginal v-if="maximized" /><FullScreen v-else /></el-icon>
                </el-button>
              </el-tooltip>
              <el-button size="small" text @click="open = false">
                <el-icon :size="15"><Close /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- ═══ 对话列表视图（紧凑态用；放大态见左侧常驻侧栏） ═══ -->
          <template v-if="view === 'sessions'">
            <div class="ab-sessions-body">
              <el-button
                class="ab-new-session"
                size="small"
                type="primary"
                :icon="Plus"
                @click="handleNewSession"
              >
                新对话
              </el-button>
              <div v-if="agentChat.sessions.length === 0" class="ab-cart-empty">
                <p>还没有历史对话</p>
              </div>
              <div
                v-for="s in agentChat.sessions"
                :key="s.id"
                class="ab-session-item"
                :class="{ active: s.id === sessionId }"
                @click="handleSwitchSession(s.id)"
              >
                <el-icon :size="13" class="ab-session-icon"><ChatLineSquare /></el-icon>
                <div class="ab-session-info">
                  <div class="ab-session-title">{{ s.title || '新对话' }}</div>
                  <div class="ab-session-time">{{ formatTime(s.updated_at) }}</div>
                </div>
                <el-button
                  size="small"
                  text
                  type="danger"
                  :icon="Delete"
                  class="ab-session-del"
                  @click.stop="handleDeleteSession(s.id)"
                />
              </div>
            </div>
          </template>

          <!-- ═══ 聊天视图（放大态左侧常驻对话列表） ═══ -->
          <template v-else-if="view === 'chat'">
           <div class="ab-chat-wrap">
            <!-- 左侧对话列表（仅放大态，像 Claude 那样） -->
            <aside v-if="maximized" class="ab-side">
              <el-button
                class="ab-new-session"
                size="small"
                type="primary"
                :icon="Plus"
                @click="handleNewSession"
              >
                新对话
              </el-button>
              <div class="ab-side-list">
                <div
                  v-for="s in agentChat.sessions"
                  :key="s.id"
                  class="ab-session-item"
                  :class="{ active: s.id === sessionId }"
                  @click="handleSwitchSession(s.id)"
                >
                  <div class="ab-session-info">
                    <div class="ab-session-title">{{ s.title || '新对话' }}</div>
                    <div class="ab-session-time">{{ formatTime(s.updated_at) }}</div>
                  </div>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    :icon="Delete"
                    class="ab-session-del"
                    @click.stop="handleDeleteSession(s.id)"
                  />
                </div>
              </div>
            </aside>

            <div class="ab-chat-main">
            <!-- 放大态：紧凑筛选行（随消息一起发给管家） -->
            <div v-if="maximized" class="ab-filters">
              <el-select
                v-model="filters.district"
                placeholder="城市/区域"
                clearable
                filterable
                allow-create
                default-first-option
                size="small"
                style="width: 118px"
              >
                <el-option v-for="d in districtOptions" :key="d" :label="d" :value="d" />
              </el-select>
              <el-input-number
                v-model="filters.price_min"
                :min="0"
                placeholder="最低价"
                :controls="false"
                size="small"
                style="width: 78px"
              />
              <span class="ab-filter-sep">-</span>
              <el-input-number
                v-model="filters.price_max"
                :min="0"
                placeholder="最高价"
                :controls="false"
                size="small"
                style="width: 78px"
              />
              <el-select v-model="filters.bedrooms" placeholder="户型" clearable size="small" style="width: 84px">
                <el-option label="1室" :value="1" />
                <el-option label="2室" :value="2" />
                <el-option label="3室" :value="3" />
                <el-option label="4室+" :value="4" />
              </el-select>
              <el-select v-model="filters.property_type" placeholder="类型" clearable size="small" style="width: 88px">
                <el-option label="公寓" value="apartment" />
                <el-option label="别墅" value="house" />
                <el-option label="单间" value="studio" />
                <el-option label="合租" value="shared" />
              </el-select>
            </div>

            <div ref="listRef" class="ab-messages" @click="onMessagesClick">
              <div v-for="(msg, i) in messages" :key="i" class="ab-msg-block">
                <div class="ab-bubble-row" :class="msg.role">
                  <div
                    v-if="msg.role === 'assistant'"
                    class="ab-bubble assistant"
                    :class="{ 'is-faq': msg.intent === 'faq' }"
                    v-html="renderRichText(msg.content)"
                  />
                  <div v-else class="ab-bubble user">{{ msg.content }}</div>
                </div>

                <!-- 欢迎语下方的功能入口卡片：找房源 / 对比房源 / 帮你找房，一键直达对应位置 -->
                <div v-if="msg.isWelcome" class="ab-welcome-cards">
                  <div class="ab-welcome-card">
                    <el-icon :size="18" color="#409eff"><Search /></el-icon>
                    <div class="ab-welcome-title">找房源</div>
                    <div class="ab-welcome-desc">按区域、价格、户型精确搜索</div>
                    <el-button size="small" type="primary" @click="goSearch">一键查看</el-button>
                  </div>
                  <div class="ab-welcome-card">
                    <el-icon :size="18" color="#409eff"><Histogram /></el-icon>
                    <div class="ab-welcome-title">对比房源</div>
                    <div class="ab-welcome-desc">多套横向对比，一眼看差异</div>
                    <el-button size="small" type="primary" @click="goCompareEntry">一键查看</el-button>
                  </div>
                  <div class="ab-welcome-card">
                    <el-icon :size="18" color="#409eff"><MagicStick /></el-icon>
                    <div class="ab-welcome-title">帮你找房</div>
                    <div class="ab-welcome-desc">说说需求，AI 帮你推荐</div>
                    <el-button size="small" type="primary" @click="triggerFindHouse">一键查看</el-button>
                  </div>
                </div>

                <!-- 复制 / 点赞 / 点踩（只有落库的 AI 回复才有 id，欢迎语等本地消息没有） -->
                <div v-if="msg.role === 'assistant' && msg.id" class="ab-msg-acts">
                  <button class="ab-msg-act" title="复制" @click="copyMessage(msg.content)">
                    <el-icon :size="13"><CopyDocument /></el-icon>
                  </button>
                  <button
                    class="ab-msg-act ab-msg-act-emoji"
                    :class="{ on: msg.feedback === 'up' }"
                    title="有帮助"
                    @click="giveFeedback(msg, 'up')"
                  >
                    👍
                  </button>
                  <button
                    class="ab-msg-act ab-msg-act-emoji"
                    :class="{ on: msg.feedback === 'down' }"
                    title="没帮助"
                    @click="giveFeedback(msg, 'down')"
                  >
                    👎
                  </button>
                </div>

                <!-- 深链 + 后续 chips -->
                <div
                  v-if="msg.role === 'assistant' && ((msg.links && msg.links.length) || (msg.quickReplies && msg.quickReplies.length))"
                  class="ab-extras"
                >
                  <el-button
                    v-for="l in msg.links || []"
                    :key="'l' + l.to"
                    size="small"
                    type="primary"
                    @click="goLink(l.to)"
                  >
                    {{ l.label }} →
                  </el-button>
                  <button
                    v-for="qr in msg.quickReplies || []"
                    :key="'q' + qr"
                    class="ab-chip"
                    @click="send(qr)"
                  >
                    {{ qr }}
                  </button>
                </div>

                <!-- 推荐卡：横向可滑动一行，带对比勾选 + 加购切换 -->
                <div v-if="msg.recommendations && msg.recommendations.length" class="ab-recs">
                  <div
                    v-for="rec in msg.recommendations"
                    :key="rec.property_id"
                    class="ab-rec"
                    :class="{ selected: isSelected(rec.property_id) }"
                  >
                    <div class="ab-rec-img">
                      <img v-if="imageUrl(rec.property)" :src="imageUrl(rec.property)!" :alt="rec.property.title" />
                      <div v-else class="ab-rec-placeholder">
                        <el-icon :size="18" color="#c0c4cc"><PictureFilled /></el-icon>
                      </div>
                      <label class="ab-rec-check" @click.stop>
                        <el-checkbox
                          :model-value="isSelected(rec.property_id)"
                          size="small"
                          @change="(v: boolean) => toggleSelect(rec.property_id, v)"
                        >
                          对比
                        </el-checkbox>
                      </label>
                    </div>
                    <div class="ab-rec-info">
                      <div class="ab-rec-title" :title="rec.property.title">{{ rec.property.title }}</div>
                      <div class="ab-rec-meta">
                        {{ rec.property.district }} · ¥{{ rec.property.price_monthly }}/月
                        <template v-if="rec.property.bedrooms"> · {{ rec.property.bedrooms }}室</template>
                      </div>
                      <div v-if="rec.match_reason" class="ab-rec-reason" :title="rec.match_reason">
                        {{ rec.match_reason }}
                      </div>
                      <div class="ab-rec-acts">
                        <el-button size="small" text type="primary" @click="goLink(`/property/${rec.property_id}`)">
                          详情
                        </el-button>
                        <el-tooltip
                          :content="cartStore.has(rec.property_id) ? '点击移出候选清单' : '加入候选清单'"
                          placement="top"
                        >
                          <button
                            class="ab-add"
                            :class="{ added: cartStore.has(rec.property_id) }"
                            @click="toggleCart(rec)"
                          >
                            <el-icon :size="13"><Check v-if="cartStore.has(rec.property_id)" /><Plus v-else /></el-icon>
                          </button>
                        </el-tooltip>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="sending" class="ab-bubble-row assistant">
                <div class="ab-bubble assistant typing">正在思考…</div>
              </div>
            </div>

            <!-- 已勾选对比提示条 -->
            <div v-if="selectedIds.length" class="ab-cmpbar">
              <span>已选 {{ selectedIds.length }} 套用于对比</span>
              <el-button size="small" type="primary" :disabled="selectedIds.length < 2" @click="goCompare(selectedIds)">
                对比所选
              </el-button>
              <el-button size="small" text @click="selectedIds = []">清空</el-button>
            </div>

            <!-- 引导追问面板：把所有缺失维度一次性摆出来（每维一行 chips，可跨维度切换），
                 点「发送」一次性提交；每维默认选中「不限」，不改也能直接发送跳过全部 -->
            <div v-if="activeElicit" class="ab-elicit-panel">
              <div v-for="group in activeElicit.groups" :key="group.field" class="ab-elicit-row">
                <div class="ab-elicit-label">{{ group.label }}</div>
                <div class="ab-elicit-chips">
                  <button
                    v-for="o in group.options"
                    :key="o.value"
                    class="ab-chip"
                    :class="{
                      'is-any': o.value === '__any__',
                      selected: elicitSelections[group.field] === o.value,
                    }"
                    @click="pickElicit(group.field, o.value)"
                  >
                    {{ o.label }}
                  </button>
                </div>
              </div>
              <div class="ab-elicit-foot">
                <span v-if="activeElicit.allow_custom" class="ab-elicit-hint">也可以在下方直接输入</span>
                <el-button type="primary" size="small" @click="submitElicitPanel">发送</el-button>
              </div>
            </div>

            <!-- 快捷 chips：常驻显示，追问面板打开时也不隐藏，方便随时换话题。
                 「帮你找房」单独高亮成主色按钮：直接进真实找房流程，不是问一句 FAQ -->
            <div v-if="faqChips.length" class="ab-chips-row">
              <button class="ab-chip ab-chip-primary" @click="triggerFindHouse">
                <el-icon :size="12"><MagicStick /></el-icon>
                帮你找房
              </button>
              <button v-for="c in faqChips" :key="c.id" class="ab-chip" @click="send(c.chip)">
                {{ c.chip }}
              </button>
            </div>

            <div class="ab-input-row">
              <el-input
                v-model="inputText"
                size="default"
                placeholder="描述需求或问「押金怎么退」…"
                @keydown.enter.exact.prevent="send()"
              />
              <el-button type="primary" :loading="sending" :disabled="!inputText.trim()" @click="send()">
                发送
              </el-button>
            </div>
            </div><!-- /.ab-chat-main -->
           </div><!-- /.ab-chat-wrap -->
          </template>

          <!-- ═══ 候选清单视图 ═══ -->
          <template v-else>
            <div class="ab-cart-body">
              <div v-if="cartStore.count === 0" class="ab-cart-empty">
                <el-icon :size="34" color="#dcdfe6"><ShoppingCart /></el-icon>
                <p>还没有候选房源</p>
                <p class="ab-empty-sub">在推荐卡上点绿色「+」即可加入</p>
              </div>
              <template v-else>
                <div class="ab-cart-toolbar">
                  <el-checkbox v-model="cartAllSelected" size="small">全选</el-checkbox>
                  <span class="ab-cart-hint">勾选后可只对比所选</span>
                </div>
                <div class="ab-cart-list">
                  <div v-for="item in cartStore.items" :key="item.id" class="ab-cart-item">
                    <el-checkbox
                      :model-value="isSelected(item.property_id)"
                      size="small"
                      @change="(v: boolean) => toggleSelect(item.property_id, v)"
                    />
                    <div class="ab-rec-img sm">
                      <img v-if="imageUrl(item.property)" :src="imageUrl(item.property)!" :alt="item.property.title" />
                      <div v-else class="ab-rec-placeholder">
                        <el-icon :size="14" color="#c0c4cc"><PictureFilled /></el-icon>
                      </div>
                    </div>
                    <div class="ab-cart-info" @click="goLink(`/property/${item.property_id}`)">
                      <div class="ab-rec-title" :title="item.property.title">{{ item.property.title }}</div>
                      <div class="ab-rec-meta">{{ item.property.district }} · ¥{{ item.property.price_monthly }}/月</div>
                    </div>
                    <el-button size="small" text type="danger" :icon="Delete" @click="removeFromCart(item.property_id)" />
                  </div>
                </div>
              </template>
            </div>
            <div class="ab-cart-footer">
              <el-button
                type="primary"
                size="small"
                style="flex: 1"
                :disabled="!canCompare"
                @click="goCompareCart"
              >
                {{ compareLabel }}
              </el-button>
            </div>
          </template>
        </div>
      </transition>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChatDotRound,
  ChatLineSquare,
  Check,
  Close,
  CopyDocument,
  Delete,
  FullScreen,
  Histogram,
  MagicStick,
  PictureFilled,
  Plus,
  ScaleToOriginal,
  Search,
  ShoppingCart,
  Star,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { storeToRefs } from 'pinia'
import { agentService } from '@/services/agent'
import { useAgentChatStore } from '@/stores/agentChat'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import type {
  AgentChatMessage,
  AgentElicit,
  AgentFilters,
  AgentRecommendation,
  FaqChip,
  MessageFeedback,
} from '@/types/agent'
import type { PropertySearchResult } from '@/types/property'

const router = useRouter()
const authStore = useAuthStore()
const cartStore = useCartStore()
const agentChat = useAgentChatStore()
const { sessionId, messages } = storeToRefs(agentChat)

const open = ref(false)
const maximized = ref(false)
const view = ref<'chat' | 'cart' | 'sessions'>('chat')
const inputText = ref('')
const sending = ref(false)
const faqChips = ref<FaqChip[]>([])
const listRef = ref<HTMLElement | null>(null)

// 筛选条件（放大态可编辑；发消息时始终随请求发送）
const filters = reactive<AgentFilters>({
  country: null,
  district: null,
  price_min: null,
  price_max: null,
  bedrooms: null,
  property_type: null,
})
const districtOptions = ['北京', '上海', '广州', '深圳', '苏州', '杭州', '南京', '成都', '武汉']

const visible = computed(() => authStore.isLoggedIn)

// 最后一条 AI 消息如果在追问条件，就把它的追问面板渲染到输入框上方
const activeElicit = computed<AgentElicit | null>(() => {
  const last = messages.value[messages.value.length - 1]
  if (!last || last.role !== 'assistant') return null
  return last.elicit ?? null
})

// 追问面板里每个维度当前选中的 value（field -> option.value）。
// 面板一出现就默认全部选「不限」，用户可以直接点「发送」一次跳过全部，
// 也可以先改掉想要的几项再发送——不用像以前那样一个条件一个条件地串行答。
const elicitSelections = reactive<Record<string, string>>({})

watch(
  activeElicit,
  (elicit) => {
    for (const key of Object.keys(elicitSelections)) delete elicitSelections[key]
    if (!elicit) return
    for (const group of elicit.groups) {
      const anyOption = group.options.find((o) => o.value === '__any__')
      elicitSelections[group.field] = anyOption?.value ?? group.options[0]?.value ?? ''
    }
  },
  { immediate: true },
)

function pickElicit(field: string, value: string) {
  elicitSelections[field] = value
}

/** 追问面板底部「发送」：把每组当前选中的 value 打进 slot_answers 一次性提交 */
function submitElicitPanel() {
  const elicit = activeElicit.value
  if (!elicit) return
  const slotAnswers: Record<string, string> = {}
  const displayParts: string[] = []
  for (const group of elicit.groups) {
    const value = elicitSelections[group.field]
    if (!value) continue
    slotAnswers[group.field] = value
    const label = group.options.find((o) => o.value === value)?.label ?? value
    displayParts.push(label)
  }
  send(undefined, displayParts.join('、') || '不限', slotAnswers)
}

// ── 多会话 ────────────────────────────────────────────────────
function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay
    ? d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

async function openSessions() {
  if (view.value === 'sessions') {
    view.value = 'chat'
    return
  }
  await agentChat.fetchSessions()
  view.value = 'sessions'
}

async function handleNewSession() {
  try {
    await agentChat.newSession()
    view.value = 'chat'
    selectedIds.value = []
    await scrollToBottom()
  } catch {
    // 拦截器统一提示
  }
}

async function handleSwitchSession(id: number) {
  if (id === sessionId.value) {
    view.value = 'chat'
    return
  }
  try {
    await agentChat.switchSession(id)
    view.value = 'chat'
    selectedIds.value = []
    await scrollToBottom()
  } catch {
    // 拦截器统一提示
  }
}

async function handleDeleteSession(id: number) {
  try {
    await ElMessageBox.confirm('删除这个对话？聊天记录将无法恢复。', '删除对话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  try {
    await agentChat.deleteSession(id)
  } catch {
    // 拦截器统一提示
  }
}

// ── 对比选择：勾选后跳转到独立对比页 /compare ────────────────────
const selectedIds = ref<number[]>([])

function isSelected(pid: number): boolean {
  return selectedIds.value.includes(pid)
}

function toggleSelect(pid: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(pid)) selectedIds.value.push(pid)
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== pid)
  }
}

const cartAllSelected = computed<boolean>({
  get: () =>
    cartStore.count > 0 && cartStore.items.every((it) => selectedIds.value.includes(it.property_id)),
  set: (val) => {
    const ids = cartStore.items.map((it) => it.property_id)
    if (val) {
      for (const id of ids) if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
    } else {
      selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id))
    }
  },
})

const canCompare = computed(
  () => selectedIds.value.length >= 2 || (selectedIds.value.length === 0 && cartStore.count >= 2),
)
const compareLabel = computed(() => {
  if (selectedIds.value.length >= 2) return `对比所选（${selectedIds.value.length}）`
  if (selectedIds.value.length === 0 && cartStore.count >= 2) return `对比全部（${cartStore.count}）`
  return '对比所选'
})

/** 跳到独立对比页；关掉气泡避免遮挡 */
function goCompare(ids: number[]) {
  if (ids.length < 2) return
  open.value = false
  router.push({ name: 'compare', query: { ids: ids.join(',') } })
}

/** 候选清单底部「对比」：有勾选就对比所选，否则对比全部 */
function goCompareCart() {
  const ids =
    selectedIds.value.length >= 2
      ? selectedIds.value
      : cartStore.items.map((it) => it.property_id)
  goCompare(ids)
}

// ── 拖拽定位（位置存 localStorage，区分点击与拖动）─────────────
const POS_KEY = 'assistant_bubble_pos'
const posRight = ref(22)
const posBottom = ref(26)
const rootStyle = computed(() => ({ right: `${posRight.value}px`, bottom: `${posBottom.value}px` }))

const drag = { active: false, moved: false, startX: 0, startY: 0, startRight: 0, startBottom: 0 }

function onDragStart(e: PointerEvent) {
  // 别拦截标题栏里的按钮点击
  if ((e.target as HTMLElement).closest('.ab-header-acts')) return
  drag.active = true
  drag.moved = false
  drag.startX = e.clientX
  drag.startY = e.clientY
  drag.startRight = posRight.value
  drag.startBottom = posBottom.value
  window.addEventListener('pointermove', onDragMove)
  window.addEventListener('pointerup', onDragEnd)
}

function onDragMove(e: PointerEvent) {
  if (!drag.active) return
  const dx = e.clientX - drag.startX
  const dy = e.clientY - drag.startY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) drag.moved = true
  posRight.value = Math.min(window.innerWidth - 70, Math.max(6, drag.startRight - dx))
  posBottom.value = Math.min(window.innerHeight - 60, Math.max(6, drag.startBottom - dy))
}

function onDragEnd() {
  if (!drag.active) return
  drag.active = false
  window.removeEventListener('pointermove', onDragMove)
  window.removeEventListener('pointerup', onDragEnd)
  try {
    localStorage.setItem(POS_KEY, JSON.stringify({ r: posRight.value, b: posBottom.value }))
  } catch {
    // 存不了就算了
  }
}

function onFabClick() {
  // 拖动结束后的 click 不当作"打开"
  if (drag.moved) {
    drag.moved = false
    return
  }
  handleOpen()
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(POS_KEY)
    if (saved) {
      const { r, b } = JSON.parse(saved)
      if (typeof r === 'number') posRight.value = Math.min(window.innerWidth - 70, Math.max(6, r))
      if (typeof b === 'number') posBottom.value = Math.min(window.innerHeight - 60, Math.max(6, b))
    }
  } catch {
    // 忽略损坏的存储
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onDragMove)
  window.removeEventListener('pointerup', onDragEnd)
})

// 新消息自动滚底
watch(
  () => messages.value.length,
  () => {
    if (open.value && view.value === 'chat') scrollToBottom()
  },
)

function imageUrl(property: PropertySearchResult): string | null {
  const images = property.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  return `/api/v1/uploads/${primary.filename}`
}

async function scrollToBottom() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

async function handleOpen() {
  open.value = true
  view.value = 'chat'
  if (faqChips.value.length === 0) {
    agentService.getFaqs().then((chips) => (faqChips.value = chips)).catch(() => undefined)
  }
  try {
    await agentChat.ensureSession() // 共享会话：已有则续聊，首次创建附欢迎语
  } catch {
    ElMessage.error('助手启动失败，请稍后重试')
    open.value = false
    return
  }
  cartStore.fetch()
  await scrollToBottom()
}

/**
 * 发送消息。
 * - preset：点 chip 时直接发送的内容（发给后端的 message，如 FAQ 问题原文）
 * - display：气泡里展示给用户看的人话，不传就用 preset/输入框原文
 * - slotAnswers：追问面板一次性提交的「维度 -> option.value」；传了这个时
 *   message 字段就用 display（人话文案），后端靠 slotAnswers 精确解析，不需要再猜
 */
async function send(preset?: string, display?: string, slotAnswers?: Record<string, string>) {
  const text = (preset ?? (slotAnswers && display ? display : inputText.value)).trim()
  if (!text || sending.value || sessionId.value === null) return

  messages.value.push({ role: 'user', content: display ?? text })
  if (!preset && !slotAnswers) inputText.value = ''
  sending.value = true
  await scrollToBottom()

  try {
    const resp = await agentService.sendMessage(sessionId.value, {
      message: text,
      filters: { ...filters },
      slot_answers: slotAnswers,
    })
    messages.value.push({
      id: resp.message_id,
      role: 'assistant',
      content: resp.reply,
      recommendations: resp.intent === 'recommend' ? resp.recommendations : undefined,
      aiAvailable: resp.ai_available,
      quickReplies: resp.quick_replies,
      links: resp.links,
      elicit: resp.elicit,
      feedback: null,
      intent: resp.intent,
    })
    if (resp.cart_changed) await cartStore.fetch()
    // 首条消息后后端会自动命名会话，刷新列表让标题跟上
    agentChat.fetchSessions()
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，请求失败了，请稍后再试。' })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

/** 「帮你找房」入口（欢迎语卡片 + 常驻按钮共用）：直接进真实找房流程，不走 FAQ 问答 */
function triggerFindHouse() {
  send('我想租房，帮我推荐一下')
}

/** 欢迎语下方的功能入口卡片：点了直接跳网站里对应的功能位置 */
function goSearch() {
  open.value = false
  router.push('/search')
}

function goCompareEntry() {
  open.value = false
  router.push('/compare')
}

async function toggleCart(rec: AgentRecommendation) {
  try {
    if (cartStore.has(rec.property_id)) {
      await cartStore.remove(rec.property_id)
      ElMessage.info(`已从候选清单移出「${rec.property.title}」`)
    } else {
      await cartStore.add(rec.property_id, rec.match_reason || undefined)
      ElMessage.success(`已将「${rec.property.title}」加入候选清单`)
    }
  } catch {
    // 拦截器统一提示
  }
}

async function removeFromCart(pid: number) {
  try {
    await cartStore.remove(pid)
    toggleSelect(pid, false)
  } catch {
    // 拦截器统一提示
  }
}

function goLink(to: string) {
  open.value = false
  router.push(to)
}

// ── 富文本渲染：**加粗** + 房源内联链接 [标题](property:id) ──────────
// 先转义再插入受控标签，不会被回复文本里的任意字符注入 XSS。
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderRichText(text: string): string {
  let html = escapeHtml(text)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(
    /\[([^[\]]+)]\(property:(\d+)\)/g,
    '<a href="/property/$2" class="ab-inline-link" data-pid="$2">$1</a>',
  )
  return html.replace(/\n/g, '<br>')
}

/** 消息列表容器上的事件委托：拦截富文本里的房源内联链接，走路由跳转而不是整页刷新 */
function onMessagesClick(e: MouseEvent) {
  const el = (e.target as HTMLElement).closest('.ab-inline-link') as HTMLElement | null
  if (!el) return
  e.preventDefault()
  const pid = el.dataset.pid
  if (pid) goLink(`/property/${pid}`)
}

// ── 消息反馈：复制 / 点赞 / 点踩 ──────────────────────────────────
async function copyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动选中文本')
  }
}

async function giveFeedback(msg: AgentChatMessage, value: MessageFeedback) {
  if (!msg.id) return
  const next = msg.feedback === value ? null : value
  const prev = msg.feedback
  msg.feedback = next
  try {
    await agentService.setMessageFeedback(msg.id, next)
  } catch {
    msg.feedback = prev
    ElMessage.error('反馈提交失败，请稍后再试')
  }
}
</script>

<style scoped>
.ab-root {
  position: fixed;
  /* Element Plus 弹层（MessageBox/Dialog 等）默认从 z-index 2000 起；
     气泡必须比它低，否则 ElMessageBox.confirm 这类确认框会被气泡盖住，
     只剩它的黑色遮罩露出来，表现为"点了背景变黑但没弹窗、删不掉"。 */
  z-index: 1500;
  /* right/bottom 由拖拽定位的内联样式控制 */
}

/* ── 气泡按钮 ── */

.ab-fab {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 12px 18px;
  border: none;
  border-radius: 26px;
  background: linear-gradient(135deg, #409eff, #6a5cff);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.45);
  transition: transform 0.15s, box-shadow 0.15s;
  touch-action: none; /* 允许触屏拖动 */
}

.ab-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.55);
}

/* ── 面板 ── */

.ab-panel {
  width: 384px;
  height: 540px;
  max-height: calc(100vh - 100px);
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.16);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease;
}

/* 放大态：完整管家体验（筛选 + 两列推荐卡） */
.ab-panel.is-max {
  width: min(880px, calc(100vw - 40px));
  height: min(860px, calc(100vh - 70px));
}

.ab-pop-enter-active,
.ab-pop-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.ab-pop-enter-from,
.ab-pop-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.97);
}

.ab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #f0f2f5;
  cursor: move;
  user-select: none;
  touch-action: none;
}

.ab-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
}

.ab-header-acts {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* ── 会话列表（放大态左侧常驻 / 紧凑态整屏） ── */

.ab-chat-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
}

.ab-chat-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ab-side {
  width: 190px;
  flex-shrink: 0;
  border-right: 1px solid #f0f2f5;
  background: #fafbfc;
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 6px;
}

.ab-side-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ab-sessions-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ab-new-session {
  width: 100%;
}

.ab-session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.ab-session-item:hover {
  background: #f0f2f5;
}

.ab-session-item.active {
  background: var(--el-color-primary-light-9, #ecf5ff);
}

.ab-session-icon {
  flex-shrink: 0;
  color: #909399;
}

.ab-session-info {
  flex: 1;
  min-width: 0;
}

.ab-session-title {
  font-size: 12.5px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ab-session-time {
  font-size: 11px;
  color: #c0c4cc;
}

.ab-session-del {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.ab-session-item:hover .ab-session-del {
  opacity: 1;
}

/* ── 引导追问选项 ── */

.ab-elicit-panel {
  padding: 8px 10px 6px;
  border-top: 1px solid #f0f2f5;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ab-elicit-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ab-elicit-label {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  flex-shrink: 0;
  width: 44px;
}

.ab-elicit-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ab-elicit-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 2px;
}

.ab-elicit-hint {
  font-size: 11px;
  color: #c0c4cc;
}

.ab-chip.is-any {
  border-color: #dcdfe6;
  color: #909399;
}

.ab-chip.is-any:hover {
  background: #909399;
  border-color: #909399;
  color: #fff;
}

.ab-chip.selected {
  background: var(--el-color-primary, #409eff);
  border-color: var(--el-color-primary, #409eff);
  color: #fff;
}

.ab-chip.selected.is-any {
  background: #909399;
  border-color: #909399;
}

/* ── 筛选行（放大态） ── */

.ab-filters {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f2f5;
  background: #fafbfc;
}

.ab-filter-sep {
  color: #909399;
  font-size: 12px;
}

/* ── 消息区 ── */

.ab-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ab-empty-sub {
  color: #c0c4cc;
  font-size: 12px;
  margin-top: 4px;
}

.ab-msg-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ab-bubble-row {
  display: flex;
}

.ab-bubble-row.user {
  justify-content: flex-end;
}

.ab-bubble {
  max-width: 85%;
  padding: 8px 11px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.ab-bubble.user {
  background: var(--el-color-primary, #409eff);
  color: #fff;
  border-bottom-right-radius: 2px;
}

.ab-bubble.assistant {
  background: #f4f4f5;
  color: #303133;
  border-bottom-left-radius: 2px;
}

.ab-bubble.typing {
  color: #909399;
}

/* FAQ 卡片化：跟普通对话气泡区分开，左侧一道主色细边 + 淡色底，看起来更像一张"知识卡片" */
.ab-bubble.assistant.is-faq {
  background: linear-gradient(180deg, #f5f9ff 0%, #f4f4f5 100%);
  border-left: 3px solid var(--el-color-primary, #409eff);
  border-radius: 4px 10px 10px 2px;
  padding-left: 12px;
}

.ab-welcome-cards {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.ab-welcome-card {
  flex: 0 0 132px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  background: linear-gradient(180deg, #f5f9ff 0%, #ffffff 100%);
  border: 1px solid #e8f0fe;
  border-radius: 10px;
  padding: 12px 10px;
}

.ab-welcome-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.ab-welcome-desc {
  font-size: 11px;
  color: #909399;
  line-height: 1.4;
  min-height: 30px;
}

.ab-welcome-card .el-button {
  width: 100%;
  margin-top: 2px;
}

.ab-bubble :deep(strong) {
  font-weight: 700;
}

.ab-bubble :deep(.ab-inline-link) {
  color: var(--el-color-primary, #409eff);
  text-decoration: none;
  font-weight: 600;
}

.ab-bubble :deep(.ab-inline-link:hover) {
  text-decoration: underline;
}

.ab-msg-acts {
  display: flex;
  gap: 4px;
  margin-left: 2px;
}

.ab-msg-act {
  border: none;
  background: none;
  cursor: pointer;
  color: #c0c4cc;
  padding: 2px 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}

.ab-msg-act:hover {
  color: #909399;
  background: #f4f4f5;
}

.ab-msg-act.on {
  color: var(--el-color-primary, #409eff);
}

/* 点赞/点踩用 emoji：emoji 自带颜色，CSS color 不生效，
   改用灰度+透明度区分未选中/选中状态 */
.ab-msg-act-emoji {
  font-size: 13px;
  line-height: 1;
  opacity: 0.4;
  filter: grayscale(70%);
  transition: opacity 0.15s, filter 0.15s;
}

.ab-msg-act-emoji:hover {
  opacity: 0.85;
  filter: grayscale(15%);
}

.ab-msg-act-emoji.on {
  opacity: 1;
  filter: none;
  background: #eef5ff;
}

.ab-extras {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* ── 推荐卡：横向可滑动一行 ── */

.ab-recs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  scroll-snap-type: x proximity;
}

.ab-recs::-webkit-scrollbar {
  height: 5px;
}
.ab-recs::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.ab-rec {
  flex: 0 0 158px;
  width: 158px;
  display: flex;
  flex-direction: column;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  scroll-snap-align: start;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.ab-rec.selected {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff);
}

.ab-rec-img {
  position: relative;
  width: 100%;
  height: 92px;
  background: #f5f7fa;
}

/* 候选清单视图里的小缩略图沿用同一类名，恢复成行内小图 */
.ab-rec-img.sm {
  flex-shrink: 0;
  width: 48px;
  height: 38px;
  border-radius: 5px;
  overflow: hidden;
}

.ab-rec-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ab-rec-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ab-rec-check {
  position: absolute;
  top: 5px;
  left: 5px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 5px;
  padding: 1px 6px;
  line-height: 1;
}

.ab-rec-check :deep(.el-checkbox__label) {
  font-size: 11px;
  padding-left: 4px;
}

.ab-rec-info {
  flex: 1;
  min-width: 0;
  padding: 6px 7px 7px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ab-rec-title {
  font-size: 12.5px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ab-rec-meta {
  font-size: 11.5px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ab-rec-reason {
  font-size: 11.5px;
  color: #67c23a;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ab-rec-acts {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 2px;
}

.ab-add {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: #67c23a;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 5px rgba(103, 194, 58, 0.4);
  flex-shrink: 0;
}

.ab-add.added {
  background: #b3e19d;
  box-shadow: none;
}

/* ── 对比提示条 / chips / 输入 ── */

.ab-cmpbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-top: 1px solid #f0f2f5;
  background: var(--el-color-primary-light-9, #ecf5ff);
  font-size: 12px;
  color: #606266;
}

.ab-cmpbar span {
  margin-right: auto;
}

.ab-chips-row {
  padding: 8px 10px 0;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  border-top: 1px solid #f0f2f5;
}

.ab-chip {
  border: 1px solid var(--el-color-primary, #409eff);
  background: #fff;
  color: var(--el-color-primary, #409eff);
  font-size: 12px;
  line-height: 1.4;
  padding: 4px 12px;
  border-radius: 14px;
  cursor: pointer;
  white-space: nowrap;
}

.ab-chip:hover {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

/* 「帮你找房」：跟普通 FAQ chip 区分开，实心主色，一眼看出是"动作"而不是"问题" */
.ab-chip-primary {
  background: var(--el-color-primary, #409eff);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-weight: 600;
}

.ab-chip-primary:hover {
  background: var(--el-color-primary-light-3, #79bbff);
}

.ab-input-row {
  padding: 8px 10px 10px;
  display: flex;
  gap: 8px;
}

/* ── 候选清单视图 ── */

.ab-cart-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
}

.ab-cart-empty {
  padding: 60px 0;
  text-align: center;
  color: #909399;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.ab-cart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f2f5;
  margin-bottom: 4px;
}

.ab-cart-hint {
  font-size: 12px;
  color: #c0c4cc;
}

.ab-cart-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f5f7fa;
}

.ab-cart-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.ab-cart-footer {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid #f0f2f5;
}

/* ── 对比弹窗 ── */

.ab-cmp-priority {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
}

.ab-cmp-tag {
  margin: 2px 4px 2px 0;
}

.ab-cmp-reco {
  margin-top: 12px;
  padding: 10px 14px;
  background: #ecf5ff;
  border-radius: 6px;
  font-size: 13px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  line-height: 1.6;
}
</style>
