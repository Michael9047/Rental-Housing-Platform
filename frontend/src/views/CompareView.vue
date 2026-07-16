<!-- 房源对比页：仿懂车帝多 Tab 对比（综合 PK / 配置表 / 图片），选择列表接候选清单 -->
<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Close, Plus, Check, Star, Search } from '@element-plus/icons-vue'
import { agentService } from '@/services/agent'
import { propertyService } from '@/services/property'
import { useCartStore } from '@/stores/cart'
import type { CompareItem, CompareResponse, ComparePriority } from '@/types/agent'
import type { PropertySearchResult, PropertyType } from '@/types/property'

const route = useRoute()
const router = useRouter()
const cartStore = useCartStore()

// ── 视图状态 ───────────────────────────────────────────────────
type TabKey = 'overview' | 'spec' | 'image'
const tab = ref<TabKey>('overview')
// 参与对比的房源 id（选择步确认后生效）
const selectedIds = ref<number[]>([])
// 选择步临时勾选（未点"开始对比"前不影响正在展示的对比）
const draftIds = ref<number[]>([])
const showSelection = ref(false)

const priority = ref<ComparePriority>('balanced')
const loading = ref(false)
const result = ref<CompareResponse | null>(null)

// 图片对比的分类（先都用占位图，真实图接入后按 tag 过滤）
const imageCategory = ref<'exterior' | 'living' | 'bedroom'>('exterior')
const imageCategories = [
  { key: 'exterior', label: '外观' },
  { key: 'living', label: '客厅' },
  { key: 'bedroom', label: '卧室' },
] as const

// 配置对比：仅看差异
const onlyDiff = ref(false)

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}

const priorityOptions: { value: ComparePriority; label: string }[] = [
  { value: 'balanced', label: '均衡' },
  { value: 'budget', label: '预算优先' },
  { value: 'commute', label: '通勤优先' },
  { value: 'space', label: '空间优先' },
]

// ── 添加车型：选择步顶部可以搜任意房源加入对比，不限于候选清单 ─────────
const searchKeyword = ref('')
const searchResults = ref<PropertySearchResult[]>([])
const searching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 已选房源的完整数据（渲染"已选"卡片用）：候选清单里的、搜索出来的都会记一份，
// 避免为了显示标题/价格再单独发请求查一次。
const draftPropertyMap = ref<Record<number, PropertySearchResult>>({})

function rememberProperties(list: PropertySearchResult[]) {
  for (const p of list) draftPropertyMap.value[p.id] = p
}

function syncCartIntoMap() {
  for (const it of cartStore.items) draftPropertyMap.value[it.property_id] = it.property
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    searchResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      const results = await propertyService.search({ q: keyword, limit: 8 })
      searchResults.value = results
      rememberProperties(results)
    } catch {
      // axios 拦截器统一提示
    } finally {
      searching.value = false
    }
  }, 300)
}

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

function addDraft(pid: number) {
  if (!draftIds.value.includes(pid)) draftIds.value.push(pid)
}

function removeDraft(pid: number) {
  draftIds.value = draftIds.value.filter((id) => id !== pid)
}

// ── 初始化：读 query ids，够两套直接对比，否则进选择步 ────────────
onMounted(async () => {
  if (!cartStore.loaded) await cartStore.fetch()
  syncCartIntoMap()
  const ids = parseQueryIds()
  if (ids.length >= 2) {
    selectedIds.value = ids
    await runCompare()
  } else {
    // 不足两套：把候选清单预勾选进选择步，让用户挑
    draftIds.value = ids.length ? ids : cartStore.items.map((it) => it.property_id)
    showSelection.value = true
  }
})

function parseQueryIds(): number[] {
  const raw = route.query.ids
  if (!raw) return []
  const text = Array.isArray(raw) ? raw.join(',') : String(raw)
  return text
    .split(',')
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isFinite(n) && n > 0)
}

// ── 对比请求 ───────────────────────────────────────────────────
async function runCompare() {
  if (selectedIds.value.length < 2) {
    showSelection.value = true
    return
  }
  loading.value = true
  try {
    result.value = await agentService.compareCart(selectedIds.value, priority.value)
    // 同步 URL，方便刷新/分享
    router.replace({ name: 'compare', query: { ids: selectedIds.value.join(',') } })
  } catch {
    // axios 拦截器统一提示
  } finally {
    loading.value = false
  }
}

function onPriorityChange() {
  if (result.value) runCompare()
}

// ── 选择步（车型对比列表，接候选清单）─────────────────────────────
function openSelection() {
  syncCartIntoMap()
  // 正在对比的房源也要能在"已选"里看到（不只是候选清单里的）
  for (const it of items.value) {
    if (it.property) draftPropertyMap.value[it.property_id] = it.property
  }
  draftIds.value = [...selectedIds.value]
  if (draftIds.value.length === 0) {
    draftIds.value = cartStore.items.map((it) => it.property_id)
  }
  showSelection.value = true
}

function toggleDraft(pid: number) {
  if (draftIds.value.includes(pid)) {
    draftIds.value = draftIds.value.filter((id) => id !== pid)
  } else {
    draftIds.value.push(pid)
  }
}

async function confirmSelection() {
  if (draftIds.value.length < 2) {
    ElMessage.warning('至少选择 2 套房源才能对比')
    return
  }
  selectedIds.value = [...draftIds.value]
  showSelection.value = false
  await runCompare()
}

// 顶部钉住卡里点"移除"：从对比中去掉一套
async function removeFromCompare(pid: number) {
  const next = selectedIds.value.filter((id) => id !== pid)
  if (next.length < 2) {
    // 剩不足两套 → 回到选择步
    draftIds.value = next
    selectedIds.value = []
    result.value = null
    showSelection.value = true
    return
  }
  selectedIds.value = next
  await runCompare()
}

// ── 派生：参与对比的房源（有序，跟 selectedIds 对齐）────────────────
const items = computed<CompareItem[]>(() => result.value?.items ?? [])

function imageUrl(p: PropertySearchResult | null): string | null {
  if (!p?.images || p.images.length === 0) return null
  const primary = p.images.find((img) => img.is_primary) || p.images[0]
  return `/api/v1/uploads/${primary.filename}`
}

// ── 综合对比 PK：四个维度，各维高亮胜者 + 角标 ────────────────────
type Dim = {
  key: 'price' | 'commute' | 'space' | 'rating'
  label: string
  // 取每套房在该维度的展示值
  display: (it: CompareItem) => string
  // 取用于比大小的数值（null = 无数据不参与评优）
  value: (it: CompareItem) => number | null
  // true = 越大越好，false = 越小越好
  higherBetter: boolean
  // 胜者角标文案
  winnerTag: string
}

// 金额/面积字段后端以字符串形式序列化 Decimal（如 "2800.00"），比较前统一转数字
function toNum(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const dims: Dim[] = [
  {
    key: 'price',
    label: '月租金',
    display: (it) => (it.property ? `¥${it.property.price_monthly}` : '—'),
    value: (it) => toNum(it.property?.price_monthly),
    higherBetter: false,
    winnerTag: '最便宜',
  },
  {
    key: 'commute',
    label: '通勤',
    display: (it) => it.commute || '暂无数据',
    value: (it) => it.score_breakdown?.commute ?? null,
    higherBetter: true,
    winnerTag: '更近',
  },
  {
    key: 'space',
    label: '面积',
    display: (it) => (it.property?.area_sqm != null ? `${it.property.area_sqm}㎡` : '—'),
    value: (it) => toNum(it.property?.area_sqm),
    higherBetter: true,
    winnerTag: '更大',
  },
  {
    key: 'rating',
    label: '评分',
    display: (it) => (it.rating != null ? `★ ${it.rating}（${it.review_count}）` : '暂无'),
    value: (it) => it.rating ?? null,
    higherBetter: true,
    winnerTag: '更高',
  },
]

// 每个维度的胜者 property_id 集合（可能并列）
function winnersOf(dim: Dim): Set<number> {
  const vals = items.value
    .map((it) => ({ id: it.property_id, v: dim.value(it) }))
    .filter((x): x is { id: number; v: number } => x.v != null)
  if (vals.length === 0) return new Set()
  const best = dim.higherBetter
    ? Math.max(...vals.map((x) => x.v))
    : Math.min(...vals.map((x) => x.v))
  return new Set(vals.filter((x) => x.v === best).map((x) => x.id))
}

// 月租金维度：最便宜的显示"比次低省 ¥X"，其余显示"贵 ¥X"
function priceDiffText(it: CompareItem): string | null {
  const prices = items.value
    .map((x) => toNum(x.property?.price_monthly))
    .filter((p): p is number => p != null)
  const cur = toNum(it.property?.price_monthly)
  if (prices.length < 2 || cur == null) return null
  const sorted = [...prices].sort((a, b) => a - b)
  const min = sorted[0]
  if (cur === min) {
    const secondMin = sorted.find((p) => p > min)
    return secondMin != null ? `比次低省 ¥${secondMin - min}` : null
  }
  return `贵 ¥${cur - min}`
}

// 综合得分胜者
const scoreWinners = computed<Set<number>>(() => {
  if (items.value.length === 0) return new Set()
  const best = Math.max(...items.value.map((it) => it.score))
  return new Set(items.value.filter((it) => it.score === best).map((it) => it.property_id))
})

function scoreColor(score: number): string {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

// ── 配置对比表：字段行 ──────────────────────────────────────────
type SpecRow = {
  label: string
  get: (it: CompareItem) => string
}

const specRows: SpecRow[] = [
  { label: '月租金', get: (it) => (it.property ? `¥${it.property.price_monthly}/月` : '—') },
  {
    label: '户型',
    get: (it) =>
      it.property ? `${it.property.bedrooms}室${it.property.bathrooms}卫` : '—',
  },
  { label: '面积', get: (it) => (it.property?.area_sqm != null ? `${it.property.area_sqm}㎡` : '—') },
  {
    label: '类型',
    get: (it) => (it.property ? typeLabels[it.property.property_type] : '—'),
  },
  { label: '楼层', get: (it) => (it.property?.floor != null ? `${it.property.floor}层` : '—') },
  { label: '区域', get: (it) => it.property?.district || '—' },
  {
    label: '押金',
    get: (it) =>
      it.property?.deposit_amount != null ? `¥${it.property.deposit_amount}` : '—',
  },
  {
    label: '服务费',
    get: (it) =>
      it.property?.service_fee_rate != null
        ? `${(it.property.service_fee_rate * 100).toFixed(1)}%`
        : '—',
  },
  { label: '通勤', get: (it) => it.commute || '暂无数据' },
  {
    label: '评分',
    get: (it) => (it.rating != null ? `${it.rating} 分（${it.review_count} 条）` : '暂无'),
  },
  {
    label: '配置',
    get: (it) =>
      it.property?.amenities && it.property.amenities.length
        ? it.property.amenities.join('、')
        : '—',
  },
]

// 某行各房源取值是否完全一致（用于"仅看差异"过滤和差异高亮）
function rowIsSame(row: SpecRow): boolean {
  const vals = items.value.map((it) => row.get(it))
  return vals.every((v) => v === vals[0])
}

const visibleSpecRows = computed(() =>
  onlyDiff.value ? specRows.filter((row) => !rowIsSame(row)) : specRows,
)

// 网格列模板：左侧字段名固定，房源列等分
const gridCols = computed(() => `92px repeat(${items.value.length}, minmax(120px, 1fr))`)

function goDetail(pid: number) {
  router.push(`/property/${pid}`)
}
</script>

<template>
  <div class="cmp">
    <!-- 顶栏：综合对比/配置对比/图片对比这几个 tab 是看"对比结果"用的，
         选房源那一步还没有结果可看，不能露出来，否则像是能跳过选房源直接看对比 -->
    <header class="cmp-top">
      <button class="cmp-back" @click="router.back()">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <template v-if="!showSelection">
        <nav class="cmp-tabs">
          <button :class="{ on: tab === 'overview' }" @click="tab = 'overview'">综合对比</button>
          <button :class="{ on: tab === 'spec' }" @click="tab = 'spec'">配置对比</button>
          <button :class="{ on: tab === 'image' }" @click="tab = 'image'">图片对比</button>
        </nav>
        <div class="cmp-top-right">
          <el-select
            v-model="priority"
            size="small"
            style="width: 106px"
            @change="onPriorityChange"
          >
            <el-option
              v-for="o in priorityOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </div>
      </template>
    </header>

    <!-- 选择步：搜索添加车型 + 已选 + 候选清单快捷勾选 -->
    <section v-if="showSelection" class="cmp-select">
      <div class="cmp-select-head">
        <h2>选择要对比的房源</h2>
        <span class="cmp-select-sub">搜索添加，或从候选清单快速勾选，至少 2 套</span>
      </div>

      <!-- 添加车型：搜任意房源加入对比，不限于候选清单 -->
      <div class="cmp-add-block">
        <div class="cmp-add-search">
          <el-icon :size="15" color="#999"><Search /></el-icon>
          <input
            v-model="searchKeyword"
            class="cmp-add-input"
            placeholder="搜索房源标题、区域，添加到对比"
            @input="onSearchInput"
          />
        </div>
        <ul v-if="searchKeyword.trim()" class="cmp-add-results">
          <li v-if="searching" class="cmp-add-empty">搜索中…</li>
          <template v-else>
            <li v-if="searchResults.length === 0" class="cmp-add-empty">没有找到匹配的房源</li>
            <li v-for="p in searchResults" :key="p.id" class="cmp-add-item">
            <img v-if="imageUrl(p)" :src="imageUrl(p)!" class="cmp-add-thumb" alt="" />
            <div v-else class="cmp-add-thumb cmp-thumb-ph">暂无图</div>
            <div class="cmp-select-info">
              <div class="cmp-select-title">{{ p.title }}</div>
              <div class="cmp-select-meta">{{ p.district }} · ¥{{ p.price_monthly }}/月</div>
            </div>
            <el-button
              size="small"
              :type="draftIds.includes(p.id) ? 'info' : 'primary'"
              :disabled="draftIds.includes(p.id)"
              @click="addDraft(p.id)"
            >
              {{ draftIds.includes(p.id) ? '已添加' : '添加' }}
            </el-button>
            </li>
          </template>
        </ul>
      </div>

      <!-- 已选 -->
      <div v-if="draftIds.length" class="cmp-picked-block">
        <div class="cmp-select-subhead">已选（{{ draftIds.length }}）</div>
        <div class="cmp-picked-list">
          <div v-for="pid in draftIds" :key="pid" class="cmp-picked-chip">
            <span>{{ draftPropertyMap[pid]?.title || `房源 ${pid}` }}</span>
            <button class="cmp-picked-x" @click="removeDraft(pid)">
              <el-icon :size="12"><Close /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <!-- 候选清单快捷勾选 -->
      <div class="cmp-select-subhead">候选清单</div>
      <div v-if="cartStore.count === 0" class="cmp-empty cmp-empty-inline">
        <p>候选清单还是空的，也可以直接用上面的搜索添加</p>
        <el-button size="small" type="primary" @click="router.push('/search')">去找房</el-button>
      </div>

      <ul v-else class="cmp-select-list">
        <li
          v-for="it in cartStore.items"
          :key="it.property_id"
          class="cmp-select-item"
          :class="{ on: draftIds.includes(it.property_id) }"
          @click="toggleDraft(it.property_id)"
        >
          <span class="cmp-check" :class="{ on: draftIds.includes(it.property_id) }">
            <el-icon v-if="draftIds.includes(it.property_id)"><Check /></el-icon>
          </span>
          <img
            v-if="imageUrl(it.property)"
            :src="imageUrl(it.property)!"
            class="cmp-select-thumb"
            alt=""
          />
          <div v-else class="cmp-select-thumb cmp-thumb-ph">暂无图</div>
          <div class="cmp-select-info">
            <div class="cmp-select-title">{{ it.property.title }}</div>
            <div class="cmp-select-meta">
              {{ it.property.district }} · ¥{{ it.property.price_monthly }}/月 ·
              {{ it.property.bedrooms }}室
            </div>
          </div>
        </li>
      </ul>

      <div class="cmp-select-foot">
        <el-button @click="showSelection = false" v-if="result">取消</el-button>
        <el-button type="primary" :disabled="draftIds.length < 2" @click="confirmSelection">
          开始对比（{{ draftIds.length }}）
        </el-button>
      </div>
    </section>

    <!-- 对比主体 -->
    <template v-else>
      <!-- 顶部钉住的房源卡 -->
      <div class="cmp-pins" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(150px, 1fr)) 96px` }">
        <div v-for="it in items" :key="it.property_id" class="cmp-pin">
          <button class="cmp-pin-x" @click="removeFromCompare(it.property_id)">
            <el-icon><Close /></el-icon>
          </button>
          <div class="cmp-pin-title" @click="goDetail(it.property_id)">{{ it.title }}</div>
          <div class="cmp-pin-price">¥{{ it.property?.price_monthly }}/月</div>
        </div>
        <button class="cmp-pin-add" @click="openSelection">
          <el-icon><Plus /></el-icon>
          <span>添加/编辑</span>
        </button>
      </div>

      <div v-loading="loading" class="cmp-body">
        <!-- ═══ 综合对比 PK ═══ -->
        <div v-if="tab === 'overview'" class="cmp-pk">
          <div class="cmp-pk-block" v-for="dim in dims" :key="dim.key">
            <div class="cmp-pk-dim">{{ dim.label }}</div>
            <div
              class="cmp-pk-row"
              :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(120px, 1fr))` }"
            >
              <div
                v-for="it in items"
                :key="it.property_id"
                class="cmp-pk-cell"
                :class="{ win: winnersOf(dim).has(it.property_id) }"
              >
                <div class="cmp-pk-val">{{ dim.display(it) }}</div>
                <div v-if="winnersOf(dim).has(it.property_id)" class="cmp-pk-badge">
                  {{ dim.winnerTag }}
                </div>
                <div
                  v-if="dim.key === 'price' && priceDiffText(it)"
                  class="cmp-pk-diff"
                  :class="{ cheap: winnersOf(dim).has(it.property_id) }"
                >
                  {{ priceDiffText(it) }}
                </div>
              </div>
            </div>
          </div>

          <!-- 综合得分 -->
          <div class="cmp-pk-block">
            <div class="cmp-pk-dim">综合得分</div>
            <div
              class="cmp-pk-row"
              :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(120px, 1fr))` }"
            >
              <div
                v-for="it in items"
                :key="it.property_id"
                class="cmp-pk-cell"
                :class="{ win: scoreWinners.has(it.property_id) }"
              >
                <el-progress
                  type="dashboard"
                  :width="76"
                  :percentage="it.score"
                  :color="scoreColor(it.score)"
                />
                <div v-if="scoreWinners.has(it.property_id)" class="cmp-pk-badge">推荐</div>
              </div>
            </div>
          </div>

          <div v-if="result?.recommendation" class="cmp-reco">
            <el-icon color="#409eff"><Star /></el-icon>
            <span>{{ result.recommendation }}</span>
          </div>
        </div>

        <!-- ═══ 配置对比表 ═══ -->
        <div v-else-if="tab === 'spec'" class="cmp-spec">
          <div class="cmp-spec-toolbar">
            <el-switch v-model="onlyDiff" />
            <span>仅看差异</span>
          </div>
          <div class="cmp-spec-table">
            <div
              v-for="row in visibleSpecRows"
              :key="row.label"
              class="cmp-spec-row"
              :style="{ gridTemplateColumns: gridCols }"
              :class="{ diff: !rowIsSame(row) }"
            >
              <div class="cmp-spec-key">{{ row.label }}</div>
              <div v-for="it in items" :key="it.property_id" class="cmp-spec-val">
                {{ row.get(it) }}
              </div>
            </div>
            <div v-if="visibleSpecRows.length === 0" class="cmp-spec-empty">
              这些房源在以上字段上完全一致
            </div>
          </div>
        </div>

        <!-- ═══ 图片对比（占位）═══ -->
        <div v-else class="cmp-image">
          <div class="cmp-image-cats">
            <button
              v-for="c in imageCategories"
              :key="c.key"
              :class="{ on: imageCategory === c.key }"
              @click="imageCategory = c.key"
            >
              {{ c.label }}
            </button>
          </div>
          <div
            class="cmp-image-grid"
            :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(150px, 1fr))` }"
          >
            <div v-for="it in items" :key="it.property_id" class="cmp-image-col">
              <img
                v-if="imageUrl(it.property)"
                :src="imageUrl(it.property)!"
                class="cmp-image-pic"
                alt=""
              />
              <div v-else class="cmp-image-pic cmp-thumb-ph">图片待补充</div>
              <div class="cmp-image-cap">{{ it.title }}</div>
              <div class="cmp-image-sub">
                ¥{{ it.property?.price_monthly }}/月 ·
                {{ it.property?.area_sqm != null ? it.property.area_sqm + '㎡' : '—' }}
              </div>
            </div>
          </div>
          <p class="cmp-image-note">图片分类为示意，真实多角度图接入后按分类展示</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cmp {
  min-height: 100%;
  background: #f5f6f8;
}

/* 顶栏 */
.cmp-top {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.cmp-back {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 18px;
  color: #333;
  display: flex;
  align-items: center;
}
.cmp-tabs {
  flex: 1;
  display: flex;
  justify-content: center;
  gap: 28px;
}
.cmp-tabs button {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 16px;
  color: #666;
  padding: 4px 0;
  position: relative;
}
.cmp-tabs button.on {
  color: #1a1a1a;
  font-weight: 600;
}
.cmp-tabs button.on::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -6px;
  transform: translateX(-50%);
  width: 60%;
  height: 3px;
  border-radius: 2px;
  background: #ffd21e;
}

/* 选择步 */
.cmp-select {
  max-width: 760px;
  margin: 0 auto;
  padding: 20px 16px 96px;
}
.cmp-select-head h2 {
  margin: 0;
  font-size: 18px;
}
.cmp-select-sub {
  color: #999;
  font-size: 13px;
}

/* 添加车型：搜索框 + 结果列表 */
.cmp-add-block {
  margin-top: 16px;
}
.cmp-add-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  padding: 10px 14px;
}
.cmp-add-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  background: transparent;
}
.cmp-add-results {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #f0f0f0;
}
.cmp-add-empty {
  padding: 14px;
  color: #999;
  font-size: 13px;
  text-align: center;
}
.cmp-add-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #f5f5f5;
}
.cmp-add-item:last-child {
  border-bottom: none;
}
.cmp-add-thumb {
  width: 52px;
  height: 40px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  font-size: 11px;
}

/* 已选 */
.cmp-select-subhead {
  margin-top: 20px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #666;
}
.cmp-picked-block {
  margin-top: 0;
}
.cmp-picked-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cmp-picked-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff5ef;
  border: 1px solid #ffb38a;
  border-radius: 16px;
  padding: 5px 8px 5px 14px;
  font-size: 13px;
  color: #333;
  max-width: 220px;
}
.cmp-picked-chip span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cmp-picked-x {
  border: none;
  background: #ffb38a;
  color: #fff;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.cmp-empty-inline {
  padding: 20px 0;
}

.cmp-select-list {
  list-style: none;
  margin: 16px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cmp-select-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #fff;
  border: 2px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.cmp-select-item.on {
  border-color: #ff6b35;
}
.cmp-check {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid #ccc;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.cmp-check.on {
  background: #ff6b35;
  border-color: #ff6b35;
}
.cmp-select-thumb {
  width: 84px;
  height: 60px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
}
.cmp-thumb-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  color: #aaa;
  font-size: 12px;
}
.cmp-select-info {
  min-width: 0;
}
.cmp-select-title {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cmp-select-meta {
  color: #888;
  font-size: 13px;
  margin-top: 4px;
}
.cmp-select-foot {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: center;
  gap: 12px;
}
.cmp-empty {
  text-align: center;
  padding: 60px 0;
  color: #999;
}

/* 钉住卡 */
.cmp-pins {
  display: grid;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
  overflow-x: auto;
}
.cmp-pin {
  position: relative;
  background: #f6f8ff;
  border-radius: 10px;
  padding: 10px 26px 10px 12px;
}
.cmp-pin-x {
  position: absolute;
  top: 6px;
  right: 6px;
  border: none;
  background: none;
  cursor: pointer;
  color: #aaa;
  font-size: 13px;
}
.cmp-pin-title {
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.cmp-pin-price {
  color: #ff6b35;
  font-size: 13px;
  margin-top: 6px;
}
.cmp-pin-add {
  border: 1px dashed #ffb38a;
  background: #fff8f3;
  border-radius: 10px;
  color: #ff6b35;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 12px;
}

/* 主体 */
.cmp-body {
  padding: 16px;
  min-height: 300px;
}

/* 综合 PK */
.cmp-pk-block {
  background: #fff;
  border-radius: 12px;
  padding: 14px 12px;
  margin-bottom: 12px;
}
.cmp-pk-dim {
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
  padding-left: 4px;
}
.cmp-pk-row {
  display: grid;
  gap: 10px;
  overflow-x: auto;
}
.cmp-pk-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  border-radius: 10px;
  background: #fafafa;
  text-align: center;
}
.cmp-pk-cell.win {
  background: #fff5ef;
  outline: 1.5px solid #ffb38a;
}
.cmp-pk-val {
  font-size: 16px;
  font-weight: 600;
  color: #222;
}
.cmp-pk-badge {
  font-size: 11px;
  color: #fff;
  background: #ff6b35;
  border-radius: 10px;
  padding: 1px 8px;
}
.cmp-pk-diff {
  font-size: 12px;
  color: #999;
}
.cmp-pk-diff.cheap {
  color: #67c23a;
}
.cmp-reco {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  background: #eef5ff;
  border-radius: 10px;
  padding: 12px 14px;
  color: #333;
  line-height: 1.6;
}

/* 配置表 */
.cmp-spec-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: #555;
  font-size: 14px;
}
.cmp-spec-table {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}
.cmp-spec-row {
  display: grid;
  border-bottom: 1px solid #f0f0f0;
}
.cmp-spec-row:last-child {
  border-bottom: none;
}
.cmp-spec-row.diff .cmp-spec-val {
  background: #fffdf5;
}
.cmp-spec-key {
  padding: 12px;
  color: #888;
  font-size: 13px;
  background: #fafafa;
}
.cmp-spec-val {
  padding: 12px;
  font-size: 14px;
  color: #222;
  border-left: 1px solid #f5f5f5;
  word-break: break-all;
}
.cmp-spec-empty {
  padding: 40px;
  text-align: center;
  color: #999;
}

/* 图片对比 */
.cmp-image-cats {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.cmp-image-cats button {
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 16px;
  padding: 5px 16px;
  cursor: pointer;
  color: #555;
}
.cmp-image-cats button.on {
  border-color: #ff6b35;
  color: #ff6b35;
  background: #fff5ef;
}
.cmp-image-grid {
  display: grid;
  gap: 12px;
}
.cmp-image-col {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}
.cmp-image-pic {
  width: 100%;
  height: 150px;
  object-fit: cover;
  display: block;
}
.cmp-image-cap {
  padding: 8px 10px 2px;
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cmp-image-sub {
  padding: 0 10px 10px;
  color: #888;
  font-size: 12px;
}
.cmp-image-note {
  margin-top: 12px;
  text-align: center;
  color: #aaa;
  font-size: 12px;
}
</style>
