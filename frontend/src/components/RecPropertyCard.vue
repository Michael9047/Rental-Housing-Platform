<!-- AI 推荐专用卡片：候选/对比使用 UnitType ID，详情进入所属 Institute。 -->
<template>
  <article class="rec-card" :class="{ selected }">
    <div class="rec-image">
      <img v-if="imageUrl" :src="imageUrl" :alt="`${instituteName} ${unitTypeName}`" />
      <div v-else class="image-placeholder">
        <el-icon :size="26"><PictureFilled /></el-icon>
        <span>暂无公寓图片</span>
      </div>

      <span v-if="locationLabel" class="location-badge">{{ locationLabel }}</span>
      <label class="compare-check" @click.stop>
        <el-checkbox
          :model-value="selected"
          size="small"
          @change="(checked: boolean) => emit('toggle-compare', rec.property_id, checked)"
        >
          对比
        </el-checkbox>
      </label>
    </div>

    <div class="rec-body">
      <div class="title-group">
        <div class="institute-name" :title="instituteName">{{ instituteName }}</div>
        <h3 :title="unitTypeName">{{ unitTypeName }}</h3>
      </div>

      <div class="price-row">
        <strong>{{ monthlyRent }}</strong><span>/月</span>
        <em v-if="p.special_offer" :title="p.special_offer">{{ p.special_offer }}</em>
      </div>

      <div class="spec-row">
        <span v-if="bedroomLabel">{{ bedroomLabel }}</span>
        <span v-if="bathroomLabel">{{ bathroomLabel }}</span>
        <span v-if="p.area_sqm">{{ p.area_sqm }}㎡</span>
        <span>{{ leaseLabel }}</span>
      </div>

      <div v-if="rec.match_reason" class="match-reason" :title="rec.match_reason">
        <b>推荐理由</b>
        <span>{{ rec.match_reason }}</span>
      </div>
      <p v-else class="description">{{ introduction }}</p>

      <div v-if="amenityTags.length" class="amenity-row">
        <span v-for="amenity in amenityTags" :key="amenity">{{ amenity }}</span>
      </div>

      <div class="nearby-row" :class="{ muted: !poiItems.length }">
        <b>周边</b>
        <template v-if="poiItems.length">
          <span v-for="item in poiItems" :key="item.key">
            {{ item.icon }} {{ item.label }} {{ item.distance }}
          </span>
        </template>
        <span v-else>数据待补充</span>
      </div>

      <div v-if="address" class="address" :title="address">
        <el-icon><LocationFilled /></el-icon>{{ address }}
      </div>

      <div class="actions">
        <button
          class="detail-button"
          type="button"
          @click="emit('detail', rec.property_id, p.institute_id || undefined)"
        >
          查看公寓与户型
        </button>
        <el-tooltip :content="inCart ? '移出候选清单' : '加入候选清单'" placement="top">
          <button
            class="cart-button"
            :class="{ added: inCart }"
            type="button"
            :aria-label="inCart ? '移出候选清单' : '加入候选清单'"
            @click="emit('toggle-cart', rec)"
          >
            <el-icon><Check v-if="inCart" /><Plus v-else /></el-icon>
          </button>
        </el-tooltip>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check, LocationFilled, PictureFilled, Plus } from '@element-plus/icons-vue'
import { countryToCurrency, formatPrice } from '@/data/currency'
import { getImageUrl } from '@/utils/image'
import type { AgentRecommendation } from '@/types/agent'

const props = defineProps<{
  rec: AgentRecommendation
  selected: boolean
  inCart: boolean
}>()

const emit = defineEmits<{
  (event: 'toggle-compare', unitTypeId: number, checked: boolean): void
  (event: 'toggle-cart', recommendation: AgentRecommendation): void
  (event: 'detail', unitTypeId: number, instituteId?: number): void
}>()

const p = computed(() => props.rec.property)

const instituteName = computed(() => (
  p.value.institute_name
  || p.value.district
  || p.value.city
  || '公寓信息'
))

const unitTypeName = computed(() => (
  p.value.name
  || p.value.unit_type_name
  || p.value.title
  || '未命名户型'
))

const locationLabel = computed(() => (
  p.value.district || p.value.city || p.value.country || ''
))

const address = computed(() => (
  p.value.institute_address || p.value.address || ''
))

const imageUrl = computed(() => {
  if (p.value.primary_image_url) return getImageUrl(p.value.primary_image_url)
  const imageUrls = p.value.image_urls
  if (imageUrls?.length) return getImageUrl(imageUrls[0])
  const images = p.value.images
  if (!images?.length) return ''
  const primary = images.find((image) => image.is_primary) || images[0]
  return getImageUrl(primary.filename)
})

const monthlyRent = computed(() => {
  const amount = p.value.base_rent ?? p.value.price_monthly ?? 0
  const currency = p.value.currency || countryToCurrency(p.value.country)
  return formatPrice(amount, currency, p.value.country)
})

const bedroomLabel = computed(() => {
  const bedrooms = Number(p.value.bedrooms)
  if (!Number.isFinite(bedrooms)) return ''
  return bedrooms === 0 ? 'Studio' : `${bedrooms}室`
})

const bathroomLabel = computed(() => {
  const bathrooms = Number(p.value.bathrooms)
  return Number.isFinite(bathrooms) && bathrooms > 0 ? `${bathrooms}卫` : ''
})

const leaseLabel = computed(() => {
  const months = Number(p.value.min_stay_months || p.value.min_lease_months || 0)
  return months > 0 ? `${months}个月起租` : '租期可咨询'
})

const introduction = computed(() => {
  const description = String(p.value.description || '').replace(/\s+/g, ' ').trim()
  if (description) return description.length > 90 ? `${description.slice(0, 90)}…` : description
  return `${instituteName.value}的${unitTypeName.value}，具体库存和楼层价格请进入详情查看。`
})

const amenityTags = computed(() => {
  const tags = [...(p.value.amenities || [])]
  if (p.value.female_only) tags.unshift('仅限女生')
  if (p.value.has_elevator) tags.push('电梯')
  return [...new Set(tags.filter(Boolean))].slice(0, 5)
})

const POI_META: Record<string, { icon: string; label: string }> = {
  transit: { icon: '🚇', label: '交通' },
  '地铁': { icon: '🚇', label: '地铁' },
  '地铁站': { icon: '🚇', label: '地铁' },
  supermarket: { icon: '🛒', label: '超市' },
  '超市': { icon: '🛒', label: '超市' },
  hospital: { icon: '🏥', label: '医院' },
  '医院': { icon: '🏥', label: '医院' },
  gym: { icon: '🏋️', label: '健身' },
  '健身房': { icon: '🏋️', label: '健身' },
  dining: { icon: '🍜', label: '餐饮' },
  '餐厅': { icon: '🍜', label: '餐饮' },
  university: { icon: '🎓', label: '学校' },
  '学校': { icon: '🎓', label: '学校' },
}

function formatDistance(meters: number): string {
  if (meters >= 1000) {
    const kilometers = meters / 1000
    return `${kilometers.toFixed(Number.isInteger(kilometers) ? 0 : 1)}km`
  }
  return `${Math.round(meters)}m`
}

const poiItems = computed(() => Object.entries(props.rec.poi_distances || {})
  .filter(([key, meters]) => POI_META[key] && Number.isFinite(Number(meters)))
  .slice(0, 4)
  .map(([key, meters]) => ({
    key,
    ...POI_META[key],
    distance: formatDistance(Number(meters)),
  })))
</script>

<style scoped>
.rec-card {
  flex: 0 0 324px;
  width: 324px;
  min-height: 520px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e1e7ee;
  border-radius: 14px;
  background: #fff;
  scroll-snap-align: start;
  transition: border-color 150ms, box-shadow 150ms, transform 150ms;
}

.rec-card:hover {
  border-color: #9ec5e9;
  box-shadow: 0 8px 22px rgb(45 88 128 / 12%);
  transform: translateY(-1px);
}

.rec-card.selected {
  border-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff);
}

.rec-image {
  position: relative;
  height: 164px;
  overflow: hidden;
  background: #f3f6f9;
}

.rec-image img { width: 100%; height: 100%; object-fit: cover; }
.image-placeholder { height: 100%; display: grid; place-content: center; justify-items: center; gap: 7px; color: #aab4c0; font-size: 12px; }
.location-badge { position: absolute; right: 10px; bottom: 10px; max-width: 210px; padding: 4px 10px; overflow: hidden; border-radius: 999px; color: #fff; background: rgb(23 38 56 / 76%); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.compare-check { position: absolute; top: 9px; left: 9px; padding: 3px 9px; border-radius: 7px; background: rgb(255 255 255 / 95%); }
.compare-check :deep(.el-checkbox__label) { padding-left: 5px; font-size: 12px; }

.rec-body { flex: 1; min-width: 0; padding: 14px 15px 15px; display: flex; flex-direction: column; gap: 9px; }
.title-group { min-width: 0; }
.institute-name { overflow: hidden; color: #718197; font-size: 11.5px; text-overflow: ellipsis; white-space: nowrap; }
.title-group h3 { min-height: 42px; margin: 3px 0 0; overflow: hidden; color: #2f3d4e; font-size: 16px; line-height: 1.35; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.price-row { display: flex; align-items: baseline; gap: 4px; min-width: 0; }
.price-row strong { color: #e45b48; font-size: 21px; }
.price-row span { color: #8d98a5; font-size: 11px; }
.price-row em { margin-left: 4px; overflow: hidden; color: #d78b20; font-size: 11px; font-style: normal; text-overflow: ellipsis; white-space: nowrap; }
.spec-row, .amenity-row, .nearby-row { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
.spec-row span, .amenity-row span, .nearby-row span { padding: 3px 7px; border-radius: 999px; color: #5f6d7c; background: #f1f4f7; font-size: 11px; }
.amenity-row span { color: #4c7d34; background: #eff8ea; }
.match-reason {
  min-height: 126px;
  padding: 10px 11px;
  overflow: hidden;
  border: 1px solid #d8ecd3;
  border-radius: 10px;
  color: #415548;
  background: linear-gradient(145deg, #f2faef, #fbfef9);
  box-sizing: border-box;
}
.match-reason b { display: block; margin-bottom: 5px; color: #2f7d4a; font-size: 12px; letter-spacing: .02em; }
.match-reason span { overflow: hidden; font-size: 12.5px; line-height: 1.6; overflow-wrap: anywhere; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 5; }
.description { min-height: 104px; margin: 0; overflow: hidden; color: #5b6878; font-size: 12.5px; line-height: 1.6; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 5; }
.nearby-row { padding-top: 8px; border-top: 1px dashed #e3e8ee; }
.nearby-row b { color: #657486; font-size: 11px; }
.nearby-row span { color: #356f9f; background: #edf5fc; }
.nearby-row.muted span { color: #9aa4ae; background: #f3f4f5; }
.address { display: flex; align-items: center; gap: 4px; overflow: hidden; color: #8a96a4; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.actions { margin-top: auto; padding-top: 5px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.detail-button { height: 33px; padding: 0 14px; border: 1px solid var(--el-color-primary, #409eff); border-radius: 8px; color: var(--el-color-primary, #409eff); background: #f3f8fd; font-size: 12px; font-weight: 600; cursor: pointer; }
.detail-button:hover { color: #fff; background: var(--el-color-primary, #409eff); }
.cart-button { width: 32px; height: 32px; flex: 0 0 32px; display: grid; place-content: center; border: 0; border-radius: 50%; color: #fff; background: #67c23a; box-shadow: 0 2px 7px rgb(103 194 58 / 35%); cursor: pointer; }
.cart-button.added { color: #417d25; background: #dff2d4; box-shadow: none; }
</style>
