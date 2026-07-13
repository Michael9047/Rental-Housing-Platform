<template>
  <!-- 浮动 AI 管家：登录用户可见，/agent 页自身不显示。
       用 v-show 而非 v-if：切到 /agent 再回来时保留会话与消息 -->
  <teleport to="body">
    <div v-show="visible" class="ab-root" :style="rootStyle">
      <!-- 气泡按钮（可拖动） -->
      <button v-show="!open" class="ab-fab" @pointerdown="onDragStart" @click="onFabClick">
        <el-icon :size="20"><ChatDotRound /></el-icon>
        <span>AI 管家</span>
      </button>

      <!-- 迷你对话面板（标题栏可拖动） -->
      <transition name="ab-pop">
        <div v-show="open" class="ab-panel" :class="{ 'is-max': maximized }">
          <div class="ab-header" @pointerdown="onDragStart">
            <div class="ab-title">
              <el-icon :size="16" color="#409eff"><ChatDotRound /></el-icon>
              <span>AI 租房管家</span>
            </div>
            <div class="ab-header-acts">
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

          <div ref="listRef" class="ab-messages">
            <div v-if="messages.length === 0" class="ab-empty">
              <p>你好，我是 AI 租房管家 👋</p>
              <p class="ab-empty-sub">找房、预订、合同、退款…都可以问我</p>
            </div>

            <div v-for="(msg, i) in messages" :key="i" class="ab-msg-block">
              <div class="ab-bubble-row" :class="msg.role">
                <div class="ab-bubble" :class="msg.role">{{ msg.content }}</div>
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

              <!-- 紧凑推荐卡（横滑） -->
              <div v-if="msg.recommendations && msg.recommendations.length" class="ab-recs">
                <div v-for="rec in msg.recommendations" :key="rec.property_id" class="ab-rec">
                  <div class="ab-rec-img">
                    <img v-if="imageUrl(rec.property)" :src="imageUrl(rec.property)!" :alt="rec.property.title" />
                    <div v-else class="ab-rec-placeholder">
                      <el-icon :size="18" color="#c0c4cc"><PictureFilled /></el-icon>
                    </div>
                  </div>
                  <div class="ab-rec-info">
                    <div class="ab-rec-title" :title="rec.property.title">{{ rec.property.title }}</div>
                    <div class="ab-rec-meta">{{ rec.property.district }} · ¥{{ rec.property.price_monthly }}/月</div>
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

          <!-- 快捷 chips -->
          <div v-if="faqChips.length" class="ab-chips-row">
            <button v-for="c in faqChips" :key="c.id" class="ab-chip" @click="send(c.chip)">
              {{ c.chip }}
            </button>
          </div>

          <div class="ab-input-row">
            <el-input
              v-model="inputText"
              size="default"
              placeholder="问我任何租房问题…"
              @keydown.enter.exact.prevent="send()"
            />
            <el-button type="primary" :loading="sending" :disabled="!inputText.trim()" @click="send()">
              发送
            </el-button>
          </div>
        </div>
      </transition>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound,
  Check,
  Close,
  FullScreen,
  PictureFilled,
  Plus,
  ScaleToOriginal,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { agentService } from '@/services/agent'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import type { AgentChatMessage, AgentRecommendation, FaqChip } from '@/types/agent'
import type { PropertySearchResult } from '@/types/property'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const cartStore = useCartStore()

const open = ref(false)
const maximized = ref(false)
const sessionId = ref<number | null>(null)
const messages = ref<AgentChatMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const faqChips = ref<FaqChip[]>([])
const listRef = ref<HTMLElement | null>(null)

// /agent 页有完整管家，不重复显示气泡
const visible = computed(() => authStore.isLoggedIn && route.path !== '/agent')

// ── 拖拽定位（位置存 localStorage，区分点击与拖动）─────────────
const POS_KEY = 'assistant_bubble_pos'
const posRight = ref(22)
const posBottom = ref(26)
const rootStyle = computed(() => ({ right: `${posRight.value}px`, bottom: `${posBottom.value}px` }))

const drag = {
  active: false,
  moved: false,
  startX: 0,
  startY: 0,
  startRight: 0,
  startBottom: 0,
}

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
  if (faqChips.value.length === 0) {
    agentService.getFaqs().then((chips) => (faqChips.value = chips)).catch(() => undefined)
  }
  if (sessionId.value === null) {
    try {
      const session = await agentService.createSession()
      sessionId.value = session.session_id
      // 首次打开：主动打招呼
      if (messages.value.length === 0) {
        messages.value.push({
          role: 'assistant',
          content:
            '你好，我是 AI 租房管家 👋\n找房、预订流程、合同、押金退款…都可以问我，也可以点下面的快捷按钮。',
        })
      }
    } catch {
      ElMessage.error('助手启动失败，请稍后重试')
      open.value = false
    }
  }
}

async function send(preset?: string) {
  const text = (preset ?? inputText.value).trim()
  if (!text || sending.value || sessionId.value === null) return

  messages.value.push({ role: 'user', content: text })
  if (!preset) inputText.value = ''
  sending.value = true
  await scrollToBottom()

  try {
    const resp = await agentService.sendMessage(sessionId.value, { message: text })
    messages.value.push({
      role: 'assistant',
      content: resp.reply,
      recommendations: resp.intent === 'recommend' ? resp.recommendations.slice(0, 3) : undefined,
      quickReplies: resp.quick_replies,
      links: resp.links,
    })
    if (resp.cart_changed) await cartStore.fetch()
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，请求失败了，请稍后再试。' })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
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

function goLink(to: string) {
  open.value = false
  router.push(to)
}
</script>

<style scoped>
.ab-root {
  position: fixed;
  z-index: 3000;
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
}

.ab-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.55);
}

.ab-fab {
  touch-action: none; /* 允许触屏拖动 */
}

/* ── 面板 ── */

.ab-panel {
  width: 372px;
  height: 520px;
  max-height: calc(100vh - 120px);
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.16);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease;
}

/* 放大窗口：更大的对话空间，推荐卡也更好看 */
.ab-panel.is-max {
  width: min(680px, calc(100vw - 44px));
  height: min(820px, calc(100vh - 80px));
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

.ab-empty {
  margin: auto;
  text-align: center;
  color: #606266;
  font-size: 13px;
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

.ab-extras {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* ── 紧凑推荐卡 ── */

.ab-recs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ab-rec {
  display: flex;
  gap: 8px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 7px;
  align-items: center;
}

.ab-rec-img {
  flex-shrink: 0;
  width: 62px;
  height: 48px;
  border-radius: 5px;
  overflow: hidden;
  background: #f5f7fa;
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

.ab-rec-info {
  flex: 1;
  min-width: 0;
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
  font-size: 12px;
  color: #909399;
}

.ab-rec-acts {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
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
}

.ab-add.added {
  background: #b3e19d;
  cursor: default;
  box-shadow: none;
}

/* ── chips / 输入 ── */

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

.ab-input-row {
  padding: 8px 10px 10px;
  display: flex;
  gap: 8px;
}
</style>
