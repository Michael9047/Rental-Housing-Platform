<!-- 可复用对比工作台：兼容独立页面和主 Agent 浮层两种承载方式。 -->
<template>
  <div class="compare-page compare-workspace" :class="{ 'is-overlay': isOverlay }">
    <header class="compare-top">
      <el-button
        text
        circle
        :aria-label="isOverlay ? '关闭对比工作台' : '返回'"
        @click="handleBack"
      ><el-icon><ArrowLeft /></el-icon></el-button>
      <nav v-if="!showSelection" class="compare-tabs">
        <button :class="{ active: tab === 'overview' }" @click="tab = 'overview'">综合对比</button>
        <button :class="{ active: tab === 'spec' }" @click="tab = 'spec'">配置对比</button>
        <button :class="{ active: tab === 'image' }" @click="tab = 'image'">图片对比</button>
      </nav>
      <strong v-if="showSelection" class="selection-title">选择要对比的具体户型</strong>
      <div v-if="!showSelection || isOverlay" class="compare-top-actions">
        <el-select
          v-if="!showSelection"
          v-model="priority"
          size="small"
          style="width: 118px"
          @change="rerunWithPriority"
        >
          <el-option v-for="option in priorityOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-button v-if="!showSelection" size="small" @click="openSelection">添加 / 编辑</el-button>
        <el-button
          v-if="isOverlay"
          size="small"
          :disabled="newPageIds.length < 2"
          @click="openInNewPage"
        >新页面打开</el-button>
      </div>
    </header>

    <section v-if="showSelection" class="selection-page">
      <div class="selection-intro">
        <div>
          <h1>选择 2–5 个具体户型</h1>
          <p>候选清单保存 UnitType；普通搜索中的公寓 Building 不能直接参与对比。</p>
        </div>
        <el-tag type="warning" effect="plain">已选 {{ draftIds.length }} / 5</el-tag>
      </div>

      <div v-if="draftIds.length" class="picked-block">
        <div class="section-label">已选户型</div>
        <div class="picked-list">
          <span v-for="id in draftIds" :key="id">
            {{ itemTitle(id) }}
            <button aria-label="移除" @click="removeDraft(id)"><el-icon><Close /></el-icon></button>
          </span>
        </div>
      </div>

      <div class="section-label">从候选清单选择</div>
      <el-empty v-if="cartStore.count === 0" description="候选清单为空；也可以保留从 Agent 推荐带过来的已选户型">
        <el-button type="primary" @click="router.push('/search')">去找房</el-button>
      </el-empty>
      <div v-else class="selection-list">
        <article
          v-for="item in cartStore.items"
          :key="item.property_id"
          :class="{ active: draftIds.includes(item.property_id) }"
          @click="toggleDraft(item.property_id)"
        >
          <span class="selection-check"><el-icon v-if="draftIds.includes(item.property_id)"><Check /></el-icon></span>
          <img v-if="unitImage(item.property)" :src="unitImage(item.property)!" alt="" />
          <div v-else class="selection-placeholder">暂无图</div>
          <div>
            <strong>{{ unitTitle(item.property) }}</strong>
            <span>{{ item.property.institute_name || '所属公寓' }} · {{ formatUnitRent(item.property) }}/月</span>
          </div>
        </article>
      </div>

      <div class="selection-footer">
        <el-button v-if="selectedIds.length >= 2" @click="showSelection = false">取消</el-button>
        <el-button type="primary" :disabled="draftIds.length < 2 || draftIds.length > 5" @click="confirmSelection">
          开始对比（{{ draftIds.length }}）
        </el-button>
      </div>
    </section>

    <template v-else>
      <el-alert
        v-if="store.error"
        class="compare-error"
        :title="store.error"
        type="error"
        show-icon
        closable
        @close="store.error = null"
      />

      <section class="pinned-row" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(190px, 1fr))` }">
        <article v-for="item in items" :key="item.id">
          <button class="pin-remove" aria-label="移出对比" @click="removeFromCompare(item.id)"><el-icon><Close /></el-icon></button>
          <span class="pin-institute">{{ item.detail?.institute_name || '所属公寓' }}</span>
          <strong @click="goDetail(item.id)">{{ itemTitle(item.id) }}</strong>
          <b>{{ formatItemRent(item) }}/月</b>
        </article>
      </section>

      <main v-loading="store.loading && !store.reply" class="compare-body">
        <section v-if="tab === 'overview'" class="overview-tab">
          <article v-for="dimension in dimensions" :key="dimension.key" class="dimension-card">
            <h2>{{ dimension.label }}</h2>
            <div class="dimension-row" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(150px, 1fr))` }">
              <div
                v-for="item in items"
                :key="item.id"
                :class="{ winner: winnersOf(dimension).has(item.id) }"
              >
                <strong>{{ dimension.display(item) }}</strong>
                <span v-if="winnersOf(dimension).has(item.id)">{{ dimension.winnerTag }}</span>
                <small>{{ itemTitle(item.id) }}</small>
              </div>
            </div>
          </article>

          <article class="tradeoff-card">
            <h2>优缺点概览</h2>
            <div class="tradeoff-grid" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(190px, 1fr))` }">
              <section v-for="tradeoff in tradeoffItems" :key="tradeoff.id">
                <header>
                  <strong>{{ tradeoff.title }}</strong>
                  <small>{{ tradeoff.institute }}</small>
                </header>
                <div class="tradeoff-list pros">
                  <b>优势</b>
                  <ul><li v-for="text in tradeoff.pros" :key="text">{{ text }}</li></ul>
                </div>
                <div class="tradeoff-list cons">
                  <b>需注意</b>
                  <ul><li v-for="text in tradeoff.cons" :key="text">{{ text }}</li></ul>
                </div>
              </section>
            </div>
          </article>

          <article class="analysis-card">
            <header>
              <span><el-icon><ChatDotRound /></el-icon></span>
              <div><strong>AI 对比总结</strong><small>基于当前户型的真实信息</small></div>
            </header>
            <p>{{ visibleReply || (store.loading ? '正在整理分析…' : '暂无分析结果') }}</p>
            <div v-if="store.loading" class="streaming-note">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ store.streamStatus || (visibleReply ? '正在继续生成…' : '正在整理分析…') }}</span>
            </div>
            <div class="followup-row">
              <el-input
                v-model="followupText"
                placeholder="继续追问，例如：如果更看重通勤，应该选哪个？"
                :disabled="store.loading"
                @keyup.enter.exact="sendFollowup"
              />
              <el-button type="primary" :loading="store.loading" @click="sendFollowup">追问</el-button>
            </div>
            <div class="followup-hints">
              <button v-for="hint in followupHints" :key="hint" @click="followupText = hint; sendFollowup()">{{ hint }}</button>
            </div>
          </article>
        </section>

        <section v-else-if="tab === 'spec'" class="spec-tab">
          <div class="spec-toolbar"><el-switch v-model="onlyDiff" /><span>仅看差异</span></div>
          <div class="spec-table">
            <div
              v-for="row in visibleSpecRows"
              :key="row.label"
              class="spec-row"
              :class="{ different: !rowIsSame(row) }"
              :style="{ gridTemplateColumns: gridColumns }"
            >
              <strong>{{ row.label }}</strong>
              <span v-for="item in items" :key="item.id">{{ row.get(item) }}</span>
            </div>
            <el-empty v-if="visibleSpecRows.length === 0" description="当前字段完全一致" />
          </div>
        </section>

        <section v-else class="image-tab">
          <p>每列对应一个具体户型；图片来自 main 的 UnitType 数据。</p>
          <div class="image-grid" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(210px, 1fr))` }">
            <article v-for="item in items" :key="item.id">
              <strong>{{ itemTitle(item.id) }}</strong>
              <span>{{ item.detail?.institute_name || '所属公寓' }}</span>
              <div v-if="unitImages(item.detail).length" class="unit-gallery">
                <img v-for="(url, index) in unitImages(item.detail).slice(0, 4)" :key="`${url}-${index}`" :src="url" alt="" />
              </div>
              <div v-else class="image-empty"><el-icon :size="30"><PictureFilled /></el-icon><span>暂无户型图片</span></div>
              <b>{{ formatItemRent(item) }}/月</b>
            </article>
          </div>
        </section>
      </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  ChatDotRound,
  Check,
  Close,
  Loading,
  PictureFilled,
} from '@element-plus/icons-vue'
import { useCartStore } from '@/stores/cart'
import { useCompareStore } from '@/stores/compare'
import { propertyService } from '@/services/property'
import { countryToCurrency, formatPrice } from '@/data/currency'
import { getImageUrl } from '@/utils/image'
import { propertyTypeLabels, type Property, type PropertySearchResult } from '@/types/property'
import type { ComparePriority, EnrichedPropertyData } from '@/types/compare'

const props = withDefaults(defineProps<{
  mode?: 'page' | 'overlay'
  initialIds?: number[]
}>(), {
  mode: 'page',
  initialIds: () => [],
})

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'open-new-page', ids: number[]): void
}>()

const route = useRoute()
const router = useRouter()
const cartStore = useCartStore()
const store = useCompareStore()
const isOverlay = computed(() => props.mode === 'overlay')

type TabKey = 'overview' | 'spec' | 'image'
interface ComparisonItem {
  id: number
  detail: PropertySearchResult | null
  enriched: EnrichedPropertyData | null
}

const tab = ref<TabKey>('overview')
const selectedIds = ref<number[]>([])
const draftIds = ref<number[]>([])
const showSelection = ref(false)
const priority = ref<ComparePriority>('balanced')
const unitDetails = ref<Record<number, PropertySearchResult>>({})
const onlyDiff = ref(false)
const followupText = ref('')
const followupHints = ['我更看重通勤', '我更看重价格', '我更看重空间', '哪个更适合长期住？']
let comparisonEpoch = 0
let componentReady = false
let internalRouteSignature: string | null = null

const priorityOptions: Array<{ value: ComparePriority; label: string }> = [
  { value: 'balanced', label: '均衡优先' },
  { value: 'budget', label: '预算优先' },
  { value: 'commute', label: '通勤优先' },
  { value: 'space', label: '空间优先' },
  { value: 'safety', label: '安全优先' },
]

const items = computed<ComparisonItem[]>(() => selectedIds.value.map((id) => ({
  id,
  detail: unitDetails.value[id] || null,
  enriched: store.propertyData[id] || null,
})))

const newPageIds = computed(() => {
  const source = showSelection.value ? draftIds.value : selectedIds.value
  return normalizeIds(source)
})

function normalizeIds(values: readonly unknown[]): number[] {
  return [...new Set(values.map((value) => Number(value)))]
    .filter((id) => Number.isInteger(id) && id > 0)
    .slice(0, 5)
}

function parseQueryIds(): number[] {
  const raw = route.query.ids
  const text = Array.isArray(raw) ? raw.join(',') : String(raw || '')
  return normalizeIds(text.split(',').map((part) => part.trim()))
}

function sameIds(left: number[], right: number[]): boolean {
  return left.length === right.length && left.every((id, index) => id === right[index])
}

async function syncSelectionFromRoute(): Promise<void> {
  const ids = parseQueryIds()
  if (ids.length >= 2) {
    const selectionChanged = !sameIds(ids, selectedIds.value)
    selectedIds.value = ids
    draftIds.value = [...ids]
    showSelection.value = false
    if (selectionChanged || store.sessionId === null) await runComparison(false)
    return
  }

  comparisonEpoch += 1
  store.reset()
  selectedIds.value = []
  draftIds.value = ids.length ? ids : cartStore.items.map((item) => item.property_id).slice(0, 5)
  await loadUnitDetails(draftIds.value)
  showSelection.value = true
}

async function syncSelectionFromInitialIds(): Promise<void> {
  const ids = normalizeIds(props.initialIds)
  if (ids.length >= 2) {
    const selectionChanged = !sameIds(ids, selectedIds.value)
    selectedIds.value = ids
    draftIds.value = [...ids]
    showSelection.value = false
    if (selectionChanged || store.sessionId === null) await runComparison(false)
    return
  }

  comparisonEpoch += 1
  store.reset()
  selectedIds.value = []
  draftIds.value = ids.length ? ids : cartStore.items.map((item) => item.property_id).slice(0, 5)
  await loadUnitDetails(draftIds.value)
  showSelection.value = true
}

onMounted(async () => {
  if (!cartStore.loaded) await cartStore.fetch()
  rememberCartDetails()
  componentReady = true
  if (isOverlay.value) await syncSelectionFromInitialIds()
  else await syncSelectionFromRoute()
})

watch(() => route.query.ids, () => {
  if (isOverlay.value) return
  const signature = parseQueryIds().join(',')
  if (internalRouteSignature === signature) {
    internalRouteSignature = null
    return
  }
  if (componentReady) void syncSelectionFromRoute()
})

watch(() => normalizeIds(props.initialIds).join(','), () => {
  if (componentReady && isOverlay.value) void syncSelectionFromInitialIds()
})

watch(() => props.mode, () => {
  if (!componentReady) return
  if (isOverlay.value) void syncSelectionFromInitialIds()
  else void syncSelectionFromRoute()
})

onBeforeUnmount(() => {
  comparisonEpoch += 1
  store.reset()
})

function rememberCartDetails() {
  const next = { ...unitDetails.value }
  for (const item of cartStore.items) next[item.property_id] = item.property
  unitDetails.value = next
}

async function loadUnitDetails(ids: number[]) {
  rememberCartDetails()
  const missing = ids.filter((id) => !unitDetails.value[id])
  const responses = await Promise.allSettled(missing.map((id) => propertyService.getById(id)))
  const next = { ...unitDetails.value }
  responses.forEach((response, index) => {
    if (response.status === 'fulfilled') next[missing[index]] = response.value as PropertySearchResult
  })
  unitDetails.value = next
}

async function replaceCompareQuery(ids: number[]): Promise<void> {
  if (isOverlay.value) return
  const nextQuery = { ...route.query }
  if (ids.length) nextQuery.ids = ids.join(',')
  else delete nextQuery.ids
  const current = parseQueryIds()
  if (sameIds(current, ids)) return
  internalRouteSignature = ids.join(',')
  try {
    await router.replace({ name: 'compare', query: nextQuery })
  } catch (error) {
    internalRouteSignature = null
    throw error
  }
}

async function runComparison(syncRoute = !isOverlay.value) {
  if (selectedIds.value.length < 2 || selectedIds.value.length > 5) {
    showSelection.value = true
    return
  }
  const ids = [...selectedIds.value]
  const activePriority = priority.value
  const epoch = ++comparisonEpoch
  store.reset()
  if (syncRoute) await replaceCompareQuery(ids)
  if (epoch !== comparisonEpoch || !sameIds(ids, selectedIds.value)) return
  // 户型详情和 AI 总结并行加载，让流式首字无需等待所有详情请求完成。
  await Promise.all([
    loadUnitDetails(ids),
    store.startComparison(ids, activePriority),
  ])
}

async function rerunWithPriority() {
  await runComparison()
}

function handleBack() {
  if (isOverlay.value) emit('close')
  else router.back()
}

function openInNewPage() {
  if (newPageIds.value.length < 2) return
  emit('open-new-page', [...newPageIds.value])
}

function openSelection() {
  rememberCartDetails()
  draftIds.value = [...selectedIds.value]
  showSelection.value = true
}

function toggleDraft(id: number) {
  if (draftIds.value.includes(id)) {
    removeDraft(id)
    return
  }
  if (draftIds.value.length >= 5) {
    ElMessage.warning('一次最多对比 5 个具体户型')
    return
  }
  draftIds.value = [...draftIds.value, id]
}

function removeDraft(id: number) {
  draftIds.value = draftIds.value.filter((item) => item !== id)
}

async function confirmSelection() {
  const ids = [...new Set(draftIds.value)].slice(0, 5)
  if (ids.length < 2) {
    ElMessage.warning('请至少选择 2 个具体户型')
    return
  }
  selectedIds.value = ids
  showSelection.value = false
  await runComparison()
}

async function removeFromCompare(id: number) {
  const next = selectedIds.value.filter((item) => item !== id)
  if (next.length < 2) {
    draftIds.value = next
    selectedIds.value = []
    comparisonEpoch += 1
    store.reset()
    showSelection.value = true
    await replaceCompareQuery(next)
    return
  }
  selectedIds.value = next
  await runComparison()
}

function unitTitle(property: PropertySearchResult | Property): string {
  return property.name || property.title || property.unit_type_name || `户型 ${property.id}`
}

function itemTitle(id: number): string {
  return unitDetails.value[id] ? unitTitle(unitDetails.value[id]) : store.propertyData[id]?.title || `户型 ${id}`
}

function normalizeImage(source: string): string {
  if (/^(https?:)?\/\//.test(source) || source.startsWith('data:') || source.startsWith('/')) return source
  return getImageUrl(source)
}

function unitImages(property: PropertySearchResult | null): string[] {
  if (!property) return []
  const images: string[] = (property.images || [])
    .slice()
    .sort((left, right) => Number(right.is_primary) - Number(left.is_primary) || left.sort_order - right.sort_order)
    .map((image) => image.filename)
  if (property.primary_image_url) images.unshift(property.primary_image_url)
  if (property.image_urls?.length) images.push(...property.image_urls)
  return [...new Set<string>(images.filter(Boolean).map(normalizeImage))]
}

function unitImage(property: PropertySearchResult): string | null {
  return unitImages(property)[0] || null
}

function itemPrice(item: ComparisonItem): number | null {
  const value = item.detail?.base_rent ?? item.detail?.price_monthly ?? item.enriched?.price_monthly
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatUnitRent(property: PropertySearchResult): string {
  const currency = property.currency || countryToCurrency(property.country)
  return formatPrice(property.base_rent ?? property.price_monthly, currency, property.country)
}

function formatItemRent(item: ComparisonItem): string {
  const price = itemPrice(item)
  if (price == null) return '价格待确认'
  if (!item.detail) return `${price.toLocaleString('zh-CN')}（币种待确认）`
  const currency = item.detail.currency || countryToCurrency(item.detail.country)
  return formatPrice(price, currency, item.detail.country)
}

function typeLabel(item: ComparisonItem): string {
  const type = item.detail?.property_type || item.enriched?.property_type
  return type ? propertyTypeLabels[type] || String(type) : '—'
}

function goDetail(id: number) {
  const instituteId = Number(unitDetails.value[id]?.institute_id)
  if (Number.isInteger(instituteId) && instituteId > 0) {
    void router.push({
      name: 'building-detail',
      params: { id: instituteId },
      query: { unit_type_id: String(id) },
    })
  } else {
    void router.push({ name: 'property-detail', params: { id } })
  }
}

interface Dimension {
  key: string
  label: string
  display: (item: ComparisonItem) => string
  value: (item: ComparisonItem) => number | null
  higherBetter: boolean
  winnerTag: string
}

function commuteMeters(item: ComparisonItem): number | null {
  const text = item.enriched?.transit_display || ''
  const kilometers = text.match(/(\d+(?:\.\d+)?)\s*km/i)
  if (kilometers) return Number(kilometers[1]) * 1000
  const meters = text.match(/(\d+(?:\.\d+)?)\s*m(?!in)/i)
  return meters ? Number(meters[1]) : null
}

function leaseMonths(item: ComparisonItem): number | null {
  const value = Number(item.detail?.min_stay_months ?? item.enriched?.min_lease_months)
  return Number.isFinite(value) && value > 0 ? value : null
}

const currenciesComparable = computed(() => {
  const currencies = items.value.map((item) => {
    if (!item.detail) return null
    return item.detail.currency || countryToCurrency(item.detail.country)
  })
  return currencies.every(Boolean) && new Set(currencies).size === 1
})

const dimensions = computed<Dimension[]>(() => [
  {
    key: 'price', label: '月租金',
    display: formatItemRent,
    value: (item) => currenciesComparable.value ? itemPrice(item) : null,
    higherBetter: false, winnerTag: '同币种更低',
  },
  {
    key: 'commute', label: '通勤',
    display: (item) => item.enriched?.transit_display || '暂无数据',
    value: commuteMeters,
    higherBetter: false, winnerTag: '现有交通距离更短',
  },
  {
    key: 'space', label: '面积',
    display: (item) => item.detail?.area_sqm != null || item.enriched?.area_sqm != null
      ? `${item.detail?.area_sqm ?? item.enriched?.area_sqm}㎡` : '—',
    value: (item) => Number(item.detail?.area_sqm ?? item.enriched?.area_sqm) || null,
    higherBetter: true, winnerTag: '空间更大',
  },
  {
    key: 'lease', label: '最短租期',
    display: (item) => leaseMonths(item) != null ? `${leaseMonths(item)} 个月` : '暂无数据',
    value: leaseMonths,
    higherBetter: false, winnerTag: '租期更灵活',
  },
])

function winnersOf(dimension: Dimension): Set<number> {
  const values = items.value
    .map((item) => ({ id: item.id, value: dimension.value(item) }))
    .filter((item): item is { id: number; value: number } => item.value != null)
  if (values.length < 2) return new Set()
  const uniqueValues = new Set(values.map((item) => item.value))
  if (uniqueValues.size < 2) return new Set()
  const best = dimension.higherBetter
    ? Math.max(...values.map((item) => item.value))
    : Math.min(...values.map((item) => item.value))
  return new Set(values.filter((item) => item.value === best).map((item) => item.id))
}

interface TradeoffItem {
  id: number
  title: string
  institute: string
  pros: string[]
  cons: string[]
}

const tradeoffItems = computed<TradeoffItem[]>(() => {
  const comparablePrices = currenciesComparable.value
    ? items.value.map(itemPrice).filter((value): value is number => value != null)
    : []
  const knownAreas = items.value
    .map((item) => Number(item.detail?.area_sqm ?? item.enriched?.area_sqm))
    .filter((value) => Number.isFinite(value) && value > 0)
  const knownCommutes = items.value.map(commuteMeters).filter((value): value is number => value != null)
  const knownLeases = items.value.map(leaseMonths).filter((value): value is number => value != null)
  const amenityCounts = items.value.map((item) => (
    item.detail?.amenities || item.enriched?.amenities || []
  ).length)

  return items.value.map((item) => {
    const pros: string[] = []
    const cons: string[] = []
    const price = itemPrice(item)
    const area = Number(item.detail?.area_sqm ?? item.enriched?.area_sqm)
    const commute = commuteMeters(item)
    const lease = leaseMonths(item)
    const amenities = item.detail?.amenities || item.enriched?.amenities || []

    if (price != null && comparablePrices.length >= 2) {
      const lowest = Math.min(...comparablePrices)
      const highest = Math.max(...comparablePrices)
      if (highest > lowest && price === lowest) pros.push(`同币种月租最低：${formatItemRent(item)}`)
      if (highest > lowest && price === highest) cons.push(`同币种月租较高：${formatItemRent(item)}`)
    }
    if (Number.isFinite(area) && area > 0 && knownAreas.length >= 2) {
      const smallest = Math.min(...knownAreas)
      const largest = Math.max(...knownAreas)
      if (largest > smallest && area === largest) pros.push(`已登记面积最大：${area}㎡`)
      if (largest > smallest && area === smallest) cons.push(`已登记面积相对较小：${area}㎡`)
    } else if (!Number.isFinite(area) || area <= 0) {
      cons.push('面积信息待补充')
    }
    if (commute != null && knownCommutes.length >= 2) {
      const shortest = Math.min(...knownCommutes)
      const longest = Math.max(...knownCommutes)
      if (longest > shortest && commute === shortest) {
        pros.push(`现有交通距离更短：${item.enriched?.transit_display}`)
      }
    } else if (commute == null) {
      cons.push('通勤信息待补充')
    }
    if (lease != null && knownLeases.length >= 2) {
      const shortestLease = Math.min(...knownLeases)
      const longestLease = Math.max(...knownLeases)
      if (longestLease > shortestLease && lease === shortestLease) {
        pros.push(`最短租期更灵活：${lease} 个月`)
      }
    }
    if (amenities.length) {
      const fewestAmenities = Math.min(...amenityCounts)
      const mostAmenities = Math.max(...amenityCounts)
      if (mostAmenities > fewestAmenities && amenities.length === mostAmenities) {
        pros.push(`已登记设施较多：${amenities.slice(0, 3).join('、')}`)
      }
    } else cons.push('设施信息待补充')

    return {
      id: item.id,
      title: itemTitle(item.id),
      institute: item.detail?.institute_name || '所属公寓',
      pros: pros.length ? pros.slice(0, 3) : ['当前资料未显示明显单项优势'],
      cons: cons.length ? cons.slice(0, 3) : ['当前资料未显示明确短板'],
    }
  })
})

/** 隐藏后端分析文本中的算法分值和排行，仅保留事实、取舍与建议。 */
function removeVisibleScores(reply: string): string {
  if (!reply.trim()) return ''
  const output: string[] = []
  let skippingRanking = false

  for (const rawLine of reply.split('\n')) {
    const trimmed = rawLine.trim()
    if (/^#{1,6}\s*.*(?:综合排序|综合评分|得分排行|评分排行)/.test(trimmed)) {
      skippingRanking = true
      continue
    }
    if (skippingRanking) {
      if (/^#{1,6}\s+/.test(trimmed) || /^💡/.test(trimmed)) skippingRanking = false
      else continue
    }
    if (/(?:系统|综合|总)得分/.test(trimmed)) continue
    if (/按.*(?:评分|得分).*最高/.test(trimmed)) continue
    if (/^(?:🥇|🥈|🥉|4️⃣|5️⃣|\d+[.)]).*(?:得分|\d+(?:\.\d+)?\s*分)/.test(trimmed)) continue

    const cleaned = rawLine
      .replace(/(\d+(?:\.\d+)?)\s*\/\s*5（\s*(\d+)\s*条(?:评价)?\s*）/g, '$2 条评价')
      .replace(/★\s*\d+(?:\.\d+)?(?:\s*\/\s*5)?/g, '已有评价')
      .replace(/安全\s*\d+(?:\.\d+)?\s*\/\s*5/g, '已有安全记录')
      .replace(/\d+(?:\.\d+)?\s*\/\s*5/g, '')
      .replace(/（[^（）]*(?:得分|评分)[^（）]*）/g, '')
      .replace(/\([^()]*(?:得分|评分)[^()]*\)/g, '')
      .replace(/(?:综合|价格|通勤|空间|安全|评价)?(?:得分|评分)\s*[:：]?\s*\d+(?:\.\d+)?(?:\s*分)?/g, '')
      .replace(/\d+(?:\.\d+)?\s*分(?=[（(，,。；;、\s]|$)/g, '')
      .replace(/暂无安全评分/g, '暂无安全数据')
      .replace(/暂无评分/g, '暂无评价')
      .replace(/评分/g, '评价')
      .replace(/得分/g, '')
      .replace(/[（(]\s*[）)]/g, '')
      .replace(/[ \t]+$/g, '')
    output.push(cleaned)
  }

  return output.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

const visibleReply = computed(() => removeVisibleScores(store.reply))

interface SpecRow {
  label: string
  get: (item: ComparisonItem) => string
}

const specRows = computed<SpecRow[]>(() => [
  { label: '月租金', get: (item) => `${formatItemRent(item)}/月` },
  { label: '所属公寓', get: (item) => item.detail?.institute_name || '—' },
  { label: '户型类型', get: typeLabel },
  { label: '卧室 / 卫生间', get: (item) => `${item.detail?.bedrooms ?? item.enriched?.bedrooms ?? '—'} / ${item.detail?.bathrooms ?? item.enriched?.bathrooms ?? '—'}` },
  { label: '面积', get: (item) => item.detail?.area_sqm != null || item.enriched?.area_sqm != null ? `${item.detail?.area_sqm ?? item.enriched?.area_sqm}㎡` : '—' },
  {
    label: '押金',
    get: (item) => {
      const amount = item.detail?.deposit_amount ?? item.enriched?.deposit_amount
      if (amount == null) return item.detail?.deposit_type || item.enriched?.deposit_type || '—'
      if (!item.detail) return String(amount)
      return formatPrice(amount, item.detail.currency || countryToCurrency(item.detail.country), item.detail.country)
    },
  },
  { label: '最短租期', get: (item) => `${item.detail?.min_stay_months ?? item.enriched?.min_lease_months ?? '—'} 个月` },
  { label: '空置数量', get: (item) => item.detail?.available_count != null ? `${item.detail.available_count} 套` : '—' },
  { label: '通勤', get: (item) => item.enriched?.transit_display || '暂无数据' },
  { label: '已审核评价', get: (item) => item.enriched?.review_count ? `${item.enriched.review_count} 条` : '暂无评价' },
  { label: '设施', get: (item) => (item.detail?.amenities || item.enriched?.amenities || []).join('、') || '—' },
])

function rowIsSame(row: SpecRow): boolean {
  const values = items.value.map((item) => row.get(item))
  return values.every((value) => value === values[0])
}

const visibleSpecRows = computed(() => onlyDiff.value ? specRows.value.filter((row) => !rowIsSame(row)) : specRows.value)
const gridColumns = computed(() => `110px repeat(${items.value.length}, minmax(150px, 1fr))`)

async function sendFollowup() {
  const message = followupText.value.trim()
  if (!message || store.loading) return
  followupText.value = ''
  let newPriority: ComparePriority | null = null
  if (/通勤|交通|距离/.test(message)) newPriority = 'commute'
  else if (/价格|预算|便宜|性价比/.test(message)) newPriority = 'budget'
  else if (/空间|面积|宽敞/.test(message)) newPriority = 'space'
  else if (/安全|治安/.test(message)) newPriority = 'safety'
  if (newPriority) priority.value = newPriority
  await store.sendFollowup(message, newPriority)
}
</script>

<style scoped>
.compare-page { min-height: 100%; background: #f5f6f8; }
.compare-workspace.is-overlay {
  height: 100%; min-height: 0; overflow-y: auto; overscroll-behavior: contain;
}
.compare-top {
  position: sticky; z-index: 10; top: 0; min-height: 48px; padding: 5px 12px;
  display: flex; align-items: center; gap: 9px; background: #fff; border-bottom: 1px solid #ebeef2;
}
.compare-tabs { flex: 1; display: flex; justify-content: center; gap: 20px; }
.compare-tabs button {
  position: relative; padding: 6px 0; color: #606266; background: none; border: 0;
  font-size: 14px; cursor: pointer;
}
.compare-tabs button.active { color: #303133; font-weight: 700; }
.compare-tabs button.active::after {
  position: absolute; right: 20%; bottom: 0; left: 20%; height: 3px;
  content: ''; background: #409eff; border-radius: 3px;
}
.compare-top-actions { display: flex; gap: 8px; }
.compare-top-actions .el-button + .el-button { margin-left: 0; }
.selection-title { flex: 1; }
.selection-page { max-width: 800px; margin: 0 auto; padding: 18px 14px 78px; }
.selection-intro { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.selection-intro h1 { margin: 0; color: #303133; font-size: 20px; }
.selection-intro p { margin: 7px 0 0; color: #909399; font-size: 13px; }
.section-label { margin: 16px 0 7px; color: #606266; font-size: 13px; font-weight: 700; }
.picked-list { display: flex; flex-wrap: wrap; gap: 7px; }
.picked-list > span {
  max-width: 240px; padding: 5px 7px 5px 12px; display: flex; align-items: center; gap: 6px;
  overflow: hidden; color: #337ecc; background: #ecf5ff; border: 1px solid #b3d8ff;
  border-radius: 999px; font-size: 12px; text-overflow: ellipsis; white-space: nowrap;
}
.picked-list button { width: 18px; height: 18px; padding: 0; display: flex; align-items: center; justify-content: center; color: #fff; background: #409eff; border: 0; border-radius: 50%; cursor: pointer; }
.selection-list { display: flex; flex-direction: column; gap: 7px; }
.selection-list article {
  padding: 8px 10px; display: flex; align-items: center; gap: 10px; cursor: pointer;
  background: #fff; border: 2px solid transparent; border-radius: 10px;
}
.selection-list article.active { border-color: #409eff; }
.selection-check { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; color: #fff; background: #fff; border: 2px solid #c0c4cc; border-radius: 50%; }
.selection-list article.active .selection-check { background: #409eff; border-color: #409eff; }
.selection-list img, .selection-placeholder { width: 70px; height: 50px; flex: 0 0 auto; object-fit: cover; border-radius: 7px; }
.selection-placeholder { display: flex; align-items: center; justify-content: center; color: #a8abb2; background: #f0f2f5; font-size: 11px; }
.selection-list article > div { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.selection-list strong { overflow: hidden; color: #303133; text-overflow: ellipsis; white-space: nowrap; }
.selection-list span { color: #909399; font-size: 12px; }
.selection-footer { position: fixed; z-index: 20; right: 0; bottom: 0; left: 0; padding: 9px; display: flex; justify-content: center; gap: 7px; background: #fff; border-top: 1px solid #e4e7ed; }
.compare-workspace.is-overlay .selection-page {
  min-height: calc(100% - 49px); padding-bottom: 0; display: flex; flex-direction: column; box-sizing: border-box;
}
.compare-workspace.is-overlay .selection-footer {
  position: sticky; right: auto; bottom: 0; left: auto; margin: auto -14px 0;
}
.compare-error { margin: 8px 12px 0; }
.pinned-row { padding: 8px 12px; display: grid; gap: 7px; overflow-x: auto; background: #fff; border-bottom: 1px solid #e4e7ed; }
.pinned-row article { position: relative; min-width: 190px; padding: 7px 26px 7px 10px; display: flex; flex-direction: column; gap: 3px; background: #f5f8ff; border-radius: 8px; }
.pinned-row strong { overflow: hidden; color: #303133; cursor: pointer; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.pinned-row b { color: #f56c6c; font-size: 13px; }
.pin-institute { overflow: hidden; color: #909399; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.pin-remove { position: absolute; top: 5px; right: 5px; padding: 3px; color: #909399; background: none; border: 0; cursor: pointer; }
.compare-body { min-height: 360px; padding: 10px 12px 14px; }
.overview-tab { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.dimension-card { margin: 0; padding: 9px; background: #fff; border-radius: 9px; }
.dimension-card h2 { margin: 0 0 7px; color: #303133; font-size: 13px; }
.dimension-row { display: grid; gap: 6px; overflow-x: auto; }
.dimension-row > div { min-width: 150px; padding: 8px 6px; display: flex; align-items: center; flex-direction: column; gap: 3px; background: #fafafa; border-radius: 7px; text-align: center; }
.dimension-row > div.winner { background: #ecf5ff; outline: 1px solid #79bbff; }
.dimension-row strong { color: #303133; font-size: 14px; }
.dimension-row span { padding: 2px 8px; color: #fff; background: #409eff; border-radius: 999px; font-size: 10px; }
.dimension-row small { max-width: 100%; overflow: hidden; color: #909399; text-overflow: ellipsis; white-space: nowrap; }
.tradeoff-card { grid-column: 1 / -1; padding: 10px; background: #fff; border-radius: 9px; }
.tradeoff-card > h2 { margin: 0 0 7px; color: #303133; font-size: 13px; }
.tradeoff-grid { display: grid; gap: 7px; overflow-x: auto; }
.tradeoff-grid > section { min-width: 190px; padding: 9px; background: #fafbfc; border: 1px solid #ebeef2; border-radius: 8px; }
.tradeoff-grid header { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.tradeoff-grid header strong, .tradeoff-grid header small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tradeoff-grid header strong { color: #303133; font-size: 12px; }
.tradeoff-grid header small { color: #909399; font-size: 10px; }
.tradeoff-list { margin-top: 7px; display: grid; grid-template-columns: 42px 1fr; align-items: start; gap: 4px; }
.tradeoff-list b { padding: 2px 5px; border-radius: 5px; font-size: 10px; text-align: center; }
.tradeoff-list ul { margin: 0; padding-left: 15px; color: #606266; font-size: 11px; line-height: 1.45; }
.tradeoff-list.pros b { color: #3d7b2b; background: #edf7e9; }
.tradeoff-list.cons b { color: #a16b21; background: #fdf3e5; }
.analysis-card { grid-column: 1 / -1; padding: 12px; color: #303133; background: linear-gradient(135deg, #f7faff, #edf5ff); border: 1px solid #d8e8ff; border-radius: 9px; }
.analysis-card header { display: flex; align-items: center; gap: 9px; }
.analysis-card header > span { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; color: #fff; background: #409eff; border-radius: 9px; }
.analysis-card header > div { display: flex; flex-direction: column; }
.analysis-card header small { color: #909399; font-size: 10px; }
.analysis-card p { margin: 10px 0; color: #606266; font-size: 12px; line-height: 1.6; white-space: pre-wrap; }
.streaming-note { margin: -3px 0 8px; display: flex; align-items: center; gap: 5px; color: #7a93ad; font-size: 11px; }
.followup-row { display: flex; gap: 8px; }
.followup-hints { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 5px; }
.followup-hints button { padding: 4px 9px; color: #337ecc; background: #fff; border: 1px solid #b3d8ff; border-radius: 999px; cursor: pointer; font-size: 11px; }
.spec-toolbar { margin-bottom: 7px; display: flex; align-items: center; gap: 7px; color: #606266; font-size: 12px; }
.spec-table { overflow-x: auto; background: #fff; border-radius: 9px; }
.spec-row { min-width: max-content; display: grid; border-bottom: 1px solid #ebeef5; }
.spec-row:last-child { border-bottom: 0; }
.spec-row > * { padding: 8px 10px; border-right: 1px solid #ebeef5; font-size: 12px; line-height: 1.4; }
.spec-row > *:last-child { border-right: 0; }
.spec-row > strong { position: sticky; left: 0; z-index: 1; color: #606266; background: #f7f8fa; }
.spec-row > span { color: #303133; background: #fff; }
.spec-row.different > strong { color: #337ecc; background: #ecf5ff; }
.image-tab > p { margin: 0 0 8px; color: #909399; font-size: 12px; }
.image-grid { display: grid; gap: 8px; overflow-x: auto; }
.image-grid > article { min-width: 210px; padding: 9px; display: flex; flex-direction: column; gap: 5px; background: #fff; border-radius: 9px; }
.image-grid > article > strong { overflow: hidden; color: #303133; text-overflow: ellipsis; white-space: nowrap; }
.image-grid > article > span { color: #909399; font-size: 11px; }
.image-grid > article > b { color: #f56c6c; font-size: 13px; }
.unit-gallery { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.unit-gallery img { width: 100%; height: 90px; object-fit: cover; border-radius: 6px; }
.image-empty { height: 184px; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 6px; color: #a8abb2; background: #f5f7fa; border-radius: 7px; font-size: 12px; }
@media (max-width: 720px) {
  .compare-top { flex-wrap: wrap; }
  .compare-tabs { order: 3; width: 100%; gap: 18px; }
  .compare-top-actions { min-width: 0; margin-left: auto; flex-wrap: wrap; justify-content: flex-end; }
  .overview-tab { grid-template-columns: 1fr; }
  .followup-row { flex-direction: column; }
}
</style>
