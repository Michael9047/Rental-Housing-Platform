<!-- 候选清单：只保存 UnitType，并以 2–5 个 UnitType 进入独立对比页。 -->
<template>
  <div class="cart-view">
    <header class="cart-view-header">
      <div>
        <div class="cart-view-title">
          <el-icon :size="20" color="#67c23a"><ShoppingCart /></el-icon>
          <span>我的候选清单</span>
          <span class="cart-view-count">{{ cartStore.count }} 个具体户型</span>
        </div>
        <p>这里保存的是公寓中的具体户型，不是公寓聚合卡片。</p>
      </div>
      <el-button
        type="primary"
        :icon="DataAnalysis"
        :disabled="selectedIds.length < 2"
        @click="goCompare"
      >
        开始综合对比（{{ selectedIds.length }} / 5）
      </el-button>
    </header>

    <el-alert
      v-if="cartStore.count > 5"
      type="info"
      :closable="false"
      show-icon
      title="一次可选择 2–5 个具体户型；当前已默认勾选前 5 个，你可以随时调整。"
    />

    <div v-if="cartStore.count === 0" class="cart-view-empty">
      <el-icon :size="52" color="#dcdfe6"><ShoppingCart /></el-icon>
      <p>候选清单还是空的</p>
      <p class="cart-view-hint">先进入公寓详情，从户型列表或 AI 推荐中加入具体户型</p>
      <el-button type="primary" @click="router.push('/search')">去找房</el-button>
    </div>

    <div v-else class="cart-grid">
      <article
        v-for="item in cartStore.items"
        :key="item.id"
        class="cart-house"
        :class="{ selected: selectedIds.includes(item.property_id) }"
        @click="goDetail(item)"
      >
        <div class="cart-house-img">
          <img v-if="imageUrl(item.property)" :src="imageUrl(item.property)!" :alt="unitTitle(item.property)" />
          <div v-else class="cart-house-placeholder">
            <el-icon :size="30" color="#c0c4cc"><PictureFilled /></el-icon>
          </div>
          <label class="cart-house-select" @click.stop>
            <el-checkbox
              :model-value="selectedIds.includes(item.property_id)"
              :disabled="!selectedIds.includes(item.property_id) && selectedIds.length >= 5"
              @change="(checked: boolean) => toggleSelection(item.property_id, checked)"
            >
              对比
            </el-checkbox>
          </label>
          <el-button
            class="cart-house-remove"
            :icon="Delete"
            circle
            size="small"
            aria-label="移出候选清单"
            @click.stop="handleRemove(item.property_id)"
          />
        </div>

        <div class="cart-house-body">
          <div class="cart-house-institute">{{ item.property.institute_name || '所属公寓' }}</div>
          <div class="cart-house-title" :title="unitTitle(item.property)">{{ unitTitle(item.property) }}</div>
          <div class="cart-house-tags">
            <el-tag size="small" type="info">{{ typeLabel(item.property.property_type) }}</el-tag>
            <el-tag size="small">{{ item.property.bedrooms ?? 0 }}室{{ item.property.bathrooms ?? 0 }}卫</el-tag>
            <el-tag v-if="item.property.area_sqm" size="small" type="info">{{ item.property.area_sqm }}㎡</el-tag>
          </div>
          <div class="cart-house-addr">
            <el-icon :size="13"><LocationFilled /></el-icon>
            {{ unitLocation(item.property) }}
          </div>
          <div v-if="item.reason" class="cart-house-reason" :title="item.reason">
            <el-icon :size="13" color="#67c23a"><Star /></el-icon>
            {{ item.reason }}
          </div>
          <div class="cart-house-foot">
            <span class="cart-house-price">{{ formatRent(item.property) }}<i>/月</i></span>
            <el-button size="small" text type="primary" @click.stop="goDetail(item)">查看公寓与户型</el-button>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  DataAnalysis,
  Delete,
  LocationFilled,
  PictureFilled,
  ShoppingCart,
  Star,
} from '@element-plus/icons-vue'
import { useCartStore } from '@/stores/cart'
import { countryToCurrency, formatPrice } from '@/data/currency'
import { getImageUrl } from '@/utils/image'
import { propertyTypeLabels, type PropertySearchResult } from '@/types/property'
import type { CartItem } from '@/types/agent'

const router = useRouter()
const cartStore = useCartStore()
const selectedIds = ref<number[]>([])

function unitTitle(property: PropertySearchResult): string {
  return property.name || property.title || property.unit_type_name || `户型 ${property.id}`
}

function unitLocation(property: PropertySearchResult): string {
  return [property.city, property.district, property.institute_address || property.address]
    .filter(Boolean)
    .join(' · ') || '地址待补充'
}

function typeLabel(type: PropertySearchResult['property_type']): string {
  return type ? propertyTypeLabels[type] || String(type) : '户型待确认'
}

function normalizeImage(source: string): string {
  if (/^(https?:)?\/\//.test(source) || source.startsWith('data:') || source.startsWith('/')) return source
  return getImageUrl(source)
}

function imageUrl(property: PropertySearchResult): string | null {
  if (property.primary_image_url) return normalizeImage(property.primary_image_url)
  const images = property.images || []
  const primary = images.find((image) => image.is_primary) || images[0]
  if (primary?.filename) return normalizeImage(primary.filename)
  if (property.image_urls?.[0]) return normalizeImage(property.image_urls[0])
  return null
}

function formatRent(property: PropertySearchResult): string {
  const rent = property.base_rent ?? property.price_monthly
  const currency = property.currency || countryToCurrency(property.country)
  return formatPrice(rent, currency, property.country)
}

function goDetail(item: CartItem) {
  const instituteId = Number(item.property.institute_id)
  if (Number.isInteger(instituteId) && instituteId > 0) {
    void router.push({
      name: 'building-detail',
      params: { id: instituteId },
      query: { unit_type_id: String(item.property_id) },
    })
  } else {
    void router.push({ name: 'property-detail', params: { id: item.property_id } })
  }
}

function toggleSelection(propertyId: number, checked: boolean) {
  if (checked) {
    if (selectedIds.value.length >= 5) {
      ElMessage.warning('一次最多对比 5 个具体户型')
      return
    }
    if (!selectedIds.value.includes(propertyId)) selectedIds.value = [...selectedIds.value, propertyId]
    return
  }
  selectedIds.value = selectedIds.value.filter((id) => id !== propertyId)
}

function goCompare() {
  const ids = [...new Set(selectedIds.value)].slice(0, 5)
  if (ids.length < 2) {
    ElMessage.warning('请至少选择 2 个具体户型')
    return
  }
  void router.push({ name: 'compare', query: { ids: ids.join(',') } })
}

async function handleRemove(propertyId: number) {
  try {
    await cartStore.remove(propertyId)
    selectedIds.value = selectedIds.value.filter((id) => id !== propertyId)
  } catch {
    // 错误提示由 API 拦截器统一处理。
  }
}

onMounted(async () => {
  await cartStore.fetch()
  selectedIds.value = cartStore.items.map((item) => item.property_id).slice(0, 5)
})
</script>

<style scoped>
.cart-view { display: flex; flex-direction: column; gap: 16px; }
.cart-view-header {
  display: flex; align-items: center; justify-content: space-between; gap: 18px;
  background: var(--bg-white, #fff); border: 1px solid var(--border, #e4e7ed);
  border-radius: var(--radius, 8px); padding: 14px 18px;
}
.cart-view-header p { margin: 5px 0 0 28px; color: #909399; font-size: 12px; }
.cart-view-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
.cart-view-count { color: #909399; font-size: 13px; font-weight: 400; }
.cart-view-empty {
  padding: 90px 0; display: flex; flex-direction: column; align-items: center;
  gap: 12px; color: #909399; text-align: center;
}
.cart-view-hint { color: #c0c4cc; font-size: 13px; }
.cart-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.cart-house {
  overflow: hidden; display: flex; flex-direction: column; cursor: pointer;
  background: var(--bg-white, #fff); border: 1px solid var(--border, #e4e7ed);
  border-radius: 10px; transition: transform .2s, box-shadow .2s, border-color .2s;
}
.cart-house:hover { transform: translateY(-3px); border-color: #9bc9ff; box-shadow: 0 6px 18px rgba(0, 0, 0, .09); }
.cart-house.selected { border-color: var(--primary, #409eff); box-shadow: 0 0 0 1px var(--primary, #409eff); }
.cart-house-img { position: relative; height: 168px; background: #f5f7fa; }
.cart-house-img img { width: 100%; height: 100%; object-fit: cover; }
.cart-house-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
.cart-house-select {
  position: absolute; top: 8px; left: 8px; padding: 2px 8px;
  background: rgba(255, 255, 255, .94); border-radius: 6px;
}
.cart-house-remove { position: absolute; top: 8px; right: 8px; background: rgba(255, 255, 255, .92) !important; }
.cart-house-body { padding: 12px 14px 14px; display: flex; flex: 1; flex-direction: column; gap: 7px; }
.cart-house-institute { color: #909399; font-size: 11px; }
.cart-house-title { overflow: hidden; color: #303133; font-size: 15px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.cart-house-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.cart-house-addr {
  overflow: hidden; display: flex; align-items: center; gap: 4px;
  color: #909399; font-size: 12px; text-overflow: ellipsis; white-space: nowrap;
}
.cart-house-reason {
  overflow: hidden; display: -webkit-box; color: #67c23a; font-size: 12px;
  line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2;
}
.cart-house-foot { margin-top: auto; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.cart-house-price { color: var(--danger, #f56c6c); font-size: 19px; font-weight: 700; }
.cart-house-price i { color: #909399; font-size: 12px; font-style: normal; font-weight: 400; }
@media (max-width: 700px) {
  .cart-view-header { align-items: stretch; flex-direction: column; }
  .cart-view-header p { margin-left: 0; }
}
</style>
