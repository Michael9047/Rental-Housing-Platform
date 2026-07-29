<template>
  <div class="ai-search-page">
    <!-- ═══ 对话区 ═══ -->
    <div class="chat-area">
      <div v-if="messages.length === 0" class="welcome">
        <h1>AI 智能找房</h1>
        <p>用自然语言描述你的需求，AI 帮你找房；点回复下方的选项可以继续收窄</p>
        <div class="example-tags">
          <el-tag v-for="ex in examples" :key="ex" class="example-tag" effect="plain" @click="send(ex)">{{ ex }}</el-tag>
        </div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="msg-wrapper">
        <!-- 用户消息 -->
        <div class="msg-user">{{ msg.user }}</div>
        <!-- AI 回复（流式） -->
        <div v-if="msg.reply" class="msg-ai">
          <div class="ai-label">🤖 AI 分析</div>
          <pre class="ai-text">{{ msg.reply }}</pre>
        </div>

        <!-- 推荐房源卡片横条 -->
        <div v-if="msg.recommendations?.length" class="recs-shell">
          <div class="recs-head">
            <strong>匹配户型 {{ msg.recommendations.length }} 种</strong>
            <span>横向滑动查看更多 · 勾选「对比」可比较</span>
          </div>
          <div class="recs-row">
            <RecPropertyCard
              v-for="r in msg.recommendations.slice(0, 10)"
              :key="r.property_id"
              :rec="r"
              :selected="selectedIds.includes(r.property_id)"
              :in-cart="cartStore.has(r.property_id)"
              @toggle-compare="toggleCompare"
              @toggle-cart="toggleCart"
              @detail="goDetail"
            />
          </div>
        </div>

        <!-- 渐进选房引导 chips -->
        <div v-if="msg.guidedOptions?.length" class="guided-row">
          <span class="guided-hint">继续收窄：</span>
          <button
            v-for="opt in msg.guidedOptions"
            :key="opt.label"
            class="guided-chip"
            :disabled="loading"
            @click="applyGuidedOption(opt)"
          >
            {{ opt.icon }} {{ opt.label }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading-msg">🤔 正在分析...</div>
    </div>

    <!-- 已勾选对比提示条 -->
    <div v-if="selectedIds.length" class="cmp-bar">
      <span>已选 {{ selectedIds.length }} 套用于对比</span>
      <el-button size="small" type="primary" :disabled="selectedIds.length < 2" @click="goCompare">
        对比所选
      </el-button>
      <el-button size="small" text @click="selectedIds = []">清空</el-button>
    </div>

    <!-- ═══ 输入区 ═══ -->
    <div class="input-bar">
      <el-input
        v-model="input"
        size="large"
        placeholder="例如：NUS附近20000以内studio"
        class="query-input"
        clearable
        :disabled="loading"
        @keyup.enter="send()"
      >
        <template #suffix>
          <el-button type="primary" size="large" :loading="loading" :disabled="!input.trim()" @click="send()">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { agentService } from '@/services/agent'
import { useCartStore } from '@/stores/cart'
import RecPropertyCard from '@/components/RecPropertyCard.vue'
import type {
  AgentFilters,
  AgentRecommendation,
  GuidedOption,
} from '@/types/agent'

const route = useRoute()
const router = useRouter()
const cartStore = useCartStore()

interface ChatMessage {
  user: string
  reply?: string
  recommendations?: AgentRecommendation[]
  guidedOptions?: GuidedOption[]
}

const input = ref('')
const loading = ref(false)
const sessionId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])

/** 对比勾选（跨轮共享同一份选择） */
const selectedIds = ref<number[]>([])

/** 渐进选房累积的筛选条件：点 chip 并入，随每条消息发送 */
const filters = reactive<AgentFilters>({
  poi_requirements: [],
  price_max: null,
  amenities: null,
  bathrooms: null,
})

const examples = [
  'NUS附近20000以内studio',
  'UCL周边1500镑以内带独卫',
  '金文泰2w以内',
]

onMounted(async () => {
  try {
    const s = await agentService.createSession()
    sessionId.value = s.session_id
  } catch { /* 会话创建失败仍可使用 */ }
  cartStore.fetch()
  // 从首页搜索框跳转过来 → 自动发送
  const urlQuery = route.query.q as string
  if (urlQuery?.trim()) {
    send(urlQuery.trim())
  }
})

async function ensureSession(): Promise<number | null> {
  if (sessionId.value) return sessionId.value
  try {
    const s = await agentService.createSession()
    sessionId.value = s.session_id
    return s.session_id
  } catch {
    return null
  }
}

/** 发送消息（真流式）：文本逐 token 上屏，meta（卡片+引导选项）结束时到达 */
async function send(text?: string) {
  const msg = (text || input.value).trim()
  if (!msg || loading.value) return
  const sid = await ensureSession()
  if (!sid) return

  input.value = ''
  loading.value = true
  messages.value.push({ user: msg, reply: '' })
  const last = messages.value[messages.value.length - 1]

  try {
    const token = localStorage.getItem('access_token') || ''
    const resp = await fetch(
      `/api/v1/agent/sessions/${sid}/messages/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: msg, filters: activeFilters() }),
      }
    )
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${resp.status}`)
    }

    const reader = resp.body?.getReader()
    if (!reader) throw new Error('No response stream')
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.token) {
              last.reply = (last.reply || '') + parsed.token
            }
            if (parsed.error) {
              throw new Error(parsed.error)
            }
            if (parsed.meta) {
              const meta = parsed.meta
              if (meta.recommendations?.length) {
                last.recommendations = meta.recommendations
              }
              if (meta.guided_options?.length) {
                last.guidedOptions = meta.guided_options
              }
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue // SSE 行内 JSON 截断，跳过
            throw e
          }
        }
      }
    }
  } catch (e: any) {
    last.reply = e.message || '请求失败'
  } finally {
    loading.value = false
  }
}

/** 当前生效的 filters（空字段不带，避免覆盖 LLM 从自然语言提取的条件） */
function activeFilters(): AgentFilters | undefined {
  const out: AgentFilters = {}
  if (filters.poi_requirements?.length) out.poi_requirements = filters.poi_requirements
  if (filters.price_max != null) out.price_max = filters.price_max
  if (filters.amenities?.length) out.amenities = filters.amenities
  if (filters.bathrooms != null) out.bathrooms = filters.bathrooms
  return Object.keys(out).length ? out : undefined
}

/** 点引导 chip：filter_patch 并入累积 filters（数组追加去重，标量覆盖），再以 chip 文案重发 */
async function applyGuidedOption(opt: GuidedOption) {
  const patch = opt.filter_patch
  if (patch && typeof patch === 'object') {
    for (const [key, val] of Object.entries(patch)) {
      if (key === 'poi_requirements' && Array.isArray(val)) {
        const merged = [...(filters.poi_requirements ?? [])]
        for (const req of val as { type: string }[]) {
          if (!merged.some((r) => r.type === req.type)) merged.push(req)
        }
        filters.poi_requirements = merged
      } else if (key === 'amenities' && Array.isArray(val)) {
        const merged = [...(filters.amenities ?? [])]
        for (const a of val as string[]) {
          if (!merged.includes(a)) merged.push(a)
        }
        filters.amenities = merged
      } else {
        ;(filters as Record<string, unknown>)[key] = val
      }
    }
  }
  await send(opt.message)
}

// ── 对比 / 候选清单 / 详情 ──────────────────────────────────────
function toggleCompare(propertyId: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(propertyId)) selectedIds.value.push(propertyId)
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== propertyId)
  }
}

function goCompare() {
  if (selectedIds.value.length < 2) return
  router.push({ path: '/compare', query: { ids: selectedIds.value.join(',') } })
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

function goDetail(propertyId: number) {
  router.push(`/property/${propertyId}`)
}
</script>

<style scoped>
.ai-search-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 110px);
  position: relative;
}
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px 100px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}
.welcome {
  text-align: center;
  padding: 80px 0;
}
.welcome h1 { font-size: 28px; margin-bottom: 8px; }
.welcome p { color: #909399; margin-bottom: 24px; }
.example-tags { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.example-tag { cursor: pointer; }
.msg-wrapper { margin-bottom: 24px; }
.msg-user {
  background: #ecf5ff;
  border-radius: 12px 12px 4px 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
  display: inline-block;
  max-width: 80%;
}
.msg-ai {
  background: #f5f7fa;
  border-radius: 4px 12px 12px 12px;
  padding: 14px 18px;
  margin-bottom: 12px;
}
.ai-label { font-weight: 600; font-size: 13px; color: #409eff; margin-bottom: 8px; }
.ai-text {
  white-space: pre-wrap;
  font: 14px/1.7 system-ui, sans-serif;
  color: #303133;
  margin: 0;
}

/* ── 推荐卡片横条 ── */
.recs-shell {
  border: 1px solid #e8eef7;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fbff 0%, #fff 42px);
  padding: 9px 9px 7px;
  margin-bottom: 12px;
}
.recs-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.recs-head strong { font-size: 12.5px; color: #303133; }
.recs-head span { font-size: 10.5px; color: #909399; }
.recs-row {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 1px 1px 7px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
}
.recs-row::-webkit-scrollbar { height: 5px; }
.recs-row::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 3px; }

/* ── 渐进选房引导 chips ── */
.guided-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.guided-hint { font-size: 12px; color: #909399; }
.guided-chip {
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
.guided-chip:hover:not(:disabled) {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}
.guided-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── 对比提示条 ── */
.cmp-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-top: 1px solid #f0f2f5;
  background: var(--el-color-primary-light-9, #ecf5ff);
  font-size: 12px;
  color: #606266;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}
.cmp-bar span { margin-right: auto; }

.loading-msg { text-align: center; color: #909399; padding: 16px; }
.input-bar {
  position: sticky;
  bottom: 0;
  padding: 12px 16px 20px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  margin-top: auto;
}
.query-input :deep(.el-input__wrapper) { border-radius: 12px; }
</style>
