<template>
  <!-- AI 推荐专用房源卡片：信息密度对标推荐管家场景
       （图+区域角标+对比勾选 / 标题 / 价格 / 规格 / 简介 / 推荐理由 / 设施 / 周边 / 地址 / 操作）。
       通用列表页请用 PropertyCard，别混用。 -->
  <div class="rec-card" :class="{ selected }">
    <div class="rec-card-img">
      <img v-if="imageUrl" :src="imageUrl" :alt="p.title" />
      <div v-else class="rec-img-placeholder">
        <el-icon :size="24" color="#c0c4cc"><PictureFilled /></el-icon>
        <span>暂无房源图片</span>
      </div>
      <span v-if="p.district" class="rec-district">{{ p.district }}</span>
      <label class="rec-check" @click.stop>
        <el-checkbox
          :model-value="selected"
          size="small"
          @change="(v: boolean) => emit('toggle-compare', rec.property_id, v)"
        >
          对比
        </el-checkbox>
      </label>
    </div>

    <div class="rec-body">
      <div class="rec-title" :title="p.title">{{ p.title }}</div>

      <div class="rec-price">
        {{ currencySymbol }}{{ formatPrice(p.price_monthly) }}<span>/月</span>
        <em v-if="p.special_offer" class="rec-offer">{{ p.special_offer }}</em>
      </div>

      <div class="rec-specs">
        <span>{{ p.bedrooms }}室{{ p.bathrooms }}卫</span>
        <span v-if="p.area_sqm">{{ p.area_sqm }}㎡</span>
        <span>{{ leaseLabel }}</span>
      </div>

      <p class="rec-desc">{{ introduction }}</p>

      <div v-if="rec.match_reason" class="rec-reason" :title="rec.match_reason">
        推荐理由：{{ rec.match_reason }}
      </div>

      <div v-if="amenityTags.length" class="rec-tags">
        <span v-for="tag in amenityTags" :key="tag">{{ tag }}</span>
      </div>

      <div class="rec-nearby" :class="{ muted: poiItems.length === 0 }">
        <strong>周边</strong>
        <template v-if="poiItems.length">
          <span v-for="item in poiItems" :key="item.key">{{ item.icon }} {{ item.short }} {{ item.dist }}</span>
        </template>
        <span v-else>周边数据待补充</span>
      </div>

      <div v-if="p.address" class="rec-address" :title="p.address">📍 {{ p.address }}</div>

      <div class="rec-acts">
        <button class="rec-detail" @click="emit('detail', rec.property_id)">查看详情</button>
        <el-tooltip :content="inCart ? '点击移出候选清单' : '加入候选清单'" placement="top">
          <button class="rec-add" :class="{ added: inCart }" @click="emit('toggle-cart', rec)">
            <el-icon :size="13"><Check v-if="inCart" /><Plus v-else /></el-icon>
          </button>
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check, PictureFilled, Plus } from '@element-plus/icons-vue'
import { getImageUrl } from '@/utils/image'
import type { AgentRecommendation } from '@/types/agent'

const props = defineProps<{
  rec: AgentRecommendation
  selected: boolean
  inCart: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-compare', propertyId: number, checked: boolean): void
  (e: 'toggle-cart', rec: AgentRecommendation): void
  (e: 'detail', propertyId: number): void
}>()

const p = computed(() => props.rec.property)

/** POI 类目元数据：与后端 compare_scoring.POI_PREFERENCES 一一对应 */
const POI_META: Record<string, { icon: string; short: string }> = {
  transit: { icon: '🚇', short: '地铁' },
  supermarket: { icon: '🛒', short: '超市' },
  hospital: { icon: '🏥', short: '医院' },
  gym: { icon: '🏋️', short: '健身' },
  dining: { icon: '🍜', short: '餐厅' },
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: '¥', GBP: '£', SGD: 'S$', USD: '$', HKD: 'HK$', JPY: 'JP¥', KRW: '₩', AUD: 'A$',
}

const currencySymbol = computed(() => CURRENCY_SYMBOLS[(p.value.currency || 'CNY').toUpperCase()] ?? '¥')

const imageUrl = computed(() => {
  const images = p.value.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  return getImageUrl(primary.filename)
})

function formatPrice(price: number): string {
  return Number(price).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

const leaseLabel = computed(() => {
  const min = p.value.min_stay_months
  if (min) return `${min}个月起租`
  return '租期可咨询'
})

const introduction = computed(() => {
  const description = String(p.value.description || '').replace(/\s+/g, ' ').trim()
  if (description) return description.length > 88 ? `${description.slice(0, 88)}…` : description
  const parts = [p.value.institute_name, p.value.district].filter(Boolean)
  return parts.length ? `位于${parts.join('·')}，具体配置可进入详情页查看。` : '具体配置可进入详情页查看。'
})

const amenityTags = computed(() => (p.value.amenities || []).filter(Boolean).slice(0, 4))

function formatDistance(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(meters % 1000 === 0 ? 0 : 1)}km`
  return `${Math.round(meters)}m`
}

const poiItems = computed(() => {
  const distances = props.rec.poi_distances || {}
  return Object.entries(distances)
    .filter(([key, meters]) => POI_META[key] && meters != null)
    .slice(0, 4)
    .map(([key, meters]) => ({
      key,
      icon: POI_META[key].icon,
      short: POI_META[key].short,
      dist: formatDistance(meters),
    }))
})
</script>

<style scoped>
.rec-card {
  flex: 0 0 250px;
  width: 250px;
  display: flex;
  flex-direction: column;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  scroll-snap-align: start;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.rec-card:hover {
  border-color: #b8d8ff;
  box-shadow: 0 5px 16px rgba(31, 79, 123, 0.09);
}

.rec-card.selected {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff);
}

.rec-card-img {
  position: relative;
  width: 100%;
  height: 126px;
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
  flex-direction: column;
  gap: 5px;
  color: #b6bdc8;
  font-size: 11px;
}

.rec-district {
  position: absolute;
  right: 7px;
  bottom: 7px;
  max-width: 150px;
  padding: 3px 7px;
  border-radius: 10px;
  background: rgba(20, 31, 51, 0.72);
  color: #fff;
  font-size: 10.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-check {
  position: absolute;
  top: 5px;
  left: 5px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 5px;
  padding: 1px 6px;
  line-height: 1;
}

.rec-check :deep(.el-checkbox__label) {
  font-size: 11px;
  padding-left: 4px;
}

.rec-body {
  flex: 1;
  min-width: 0;
  padding: 9px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rec-title {
  font-size: 13.5px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-price {
  color: #f56c6c;
  font-size: 17px;
  font-weight: 700;
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}

.rec-price span {
  color: #909399;
  font-size: 10.5px;
  font-weight: 400;
}

.rec-offer {
  color: #e6a23c;
  font-size: 10.5px;
  font-weight: 400;
  font-style: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 130px;
}

.rec-specs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.rec-specs span,
.rec-tags span,
.rec-nearby span {
  padding: 2px 6px;
  border-radius: 9px;
  background: #f2f6fc;
  color: #606266;
  font-size: 10.5px;
  line-height: 1.35;
}

.rec-desc {
  margin: 0;
  min-height: 48px;
  color: #606266;
  font-size: 11.5px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.rec-reason {
  font-size: 11.5px;
  color: #67c23a;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.rec-tags,
.rec-nearby {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.rec-tags span {
  background: #f0f9eb;
  color: #529b2e;
}

.rec-nearby {
  padding-top: 5px;
  border-top: 1px dashed #ebeef5;
}

.rec-nearby strong {
  color: #606266;
  font-size: 11px;
}

.rec-nearby span {
  background: #ecf5ff;
  color: #337ecc;
}

.rec-nearby.muted span {
  background: #f4f4f5;
  color: #a8abb2;
}

.rec-address {
  color: #909399;
  font-size: 10.8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-acts {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 4px;
}

.rec-detail {
  height: 27px;
  padding: 0 11px;
  border: 1px solid var(--el-color-primary, #409eff);
  border-radius: 6px;
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
}

.rec-detail:hover {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.rec-add {
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

.rec-add.added {
  background: #b3e19d;
  box-shadow: none;
}
</style>
