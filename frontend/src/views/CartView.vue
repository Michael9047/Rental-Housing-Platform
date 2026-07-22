<template>
  <div class="cart-view">
    <div class="cart-view-header">
      <div class="cart-view-title">
        <el-icon :size="20" color="#67c23a"><ShoppingCart /></el-icon>
        <span>我的候选清单</span>
        <span class="cart-view-count">{{ cartStore.count }} 套</span>
      </div>
      <el-button
        type="primary"
        :icon="ChatDotRound"
        :disabled="cartStore.count < 2"
        @click="goCompare"
      >
        对比候选清单
      </el-button>
    </div>

    <div v-if="cartStore.count === 0" class="cart-view-empty">
      <el-icon :size="52" color="#dcdfe6"><ShoppingCart /></el-icon>
      <p>候选清单还是空的</p>
      <p class="cart-view-hint">在房源卡片右下角点绿色「+」即可加入</p>
      <el-button type="primary" @click="router.push('/search')">去找房</el-button>
    </div>

    <div v-else class="cart-grid">
      <div
        v-for="item in cartStore.items"
        :key="item.id"
        class="cart-house"
        @click="goDetail(item.property_id)"
      >
        <div class="cart-house-img">
          <img
            v-if="imageUrl(item.property)"
            :src="imageUrl(item.property)!"
            :alt="item.property.title"
          />
          <div v-else class="cart-house-placeholder">
            <el-icon :size="30" color="#c0c4cc"><PictureFilled /></el-icon>
          </div>
          <el-button
            class="cart-house-remove"
            :icon="Delete"
            circle
            size="small"
            @click.stop="handleRemove(item.property_id)"
          />
        </div>
        <div class="cart-house-body">
          <div class="cart-house-title" :title="item.property.title">{{ item.property.title }}</div>
          <div class="cart-house-tags">
            <el-tag size="small" type="info">{{ typeLabels[item.property.property_type] }}</el-tag>
            <el-tag size="small">{{ item.property.bedrooms }}室{{ item.property.bathrooms }}卫</el-tag>
            <el-tag v-if="item.property.area_sqm" size="small" type="info">{{ item.property.area_sqm }}㎡</el-tag>
          </div>
          <div class="cart-house-addr">
            <el-icon :size="13"><LocationFilled /></el-icon>
            {{ item.property.district }} · {{ item.property.address }}
          </div>
          <div v-if="item.reason" class="cart-house-reason" :title="item.reason">
            <el-icon :size="13" color="#67c23a"><Star /></el-icon>
            {{ item.reason }}
          </div>
          <div class="cart-house-foot">
            <span class="cart-house-price">¥{{ item.property.price_monthly }}<i>/月</i></span>
            <el-button size="small" text type="primary" @click.stop="goDetail(item.property_id)">
              查看详情
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChatDotRound,
  Delete,
  LocationFilled,
  PictureFilled,
  ShoppingCart,
  Star,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useCartStore } from '@/stores/cart'
import type { PropertySearchResult, PropertyType } from '@/types/property'
import { getImageUrl } from '@/utils/image'

const router = useRouter()
const cartStore = useCartStore()

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}

function imageUrl(property: PropertySearchResult): string | null {
  const images = property.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  return getImageUrl(primary.filename)
}

function goDetail(propertyId: number) {
  router.push(`/property/${propertyId}`)
}

function goCompare() {
  if (cartStore.count < 2) {
    ElMessage.warning('候选清单至少需要 2 套房源才能对比')
    return
  }
  router.push({
    name: 'compare',
    query: { ids: cartStore.items.map((item) => item.property_id).join(',') },
  })
}

async function handleRemove(propertyId: number) {
  try {
    await cartStore.remove(propertyId)
  } catch {
    // 错误提示由 api 拦截器统一处理
  }
}

onMounted(() => {
  cartStore.fetch()
})
</script>

<style scoped>
.cart-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cart-view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-white, #fff);
  border: 1px solid var(--border, #e4e7ed);
  border-radius: var(--radius, 8px);
  padding: 14px 18px;
}

.cart-view-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.cart-view-count {
  font-size: 13px;
  font-weight: 400;
  color: #909399;
}

.cart-view-empty {
  padding: 90px 0;
  text-align: center;
  color: #909399;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.cart-view-hint {
  font-size: 13px;
  color: #c0c4cc;
}

.cart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.cart-house {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border, #e4e7ed);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.cart-house:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.09);
  border-color: var(--primary, #409eff);
}

.cart-house-img {
  position: relative;
  height: 168px;
  background: #f5f7fa;
}

.cart-house-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cart-house-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cart-house-remove {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(255, 255, 255, 0.9) !important;
}

.cart-house-body {
  padding: 12px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  flex: 1;
}

.cart-house-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cart-house-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.cart-house-addr {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cart-house-reason {
  font-size: 12px;
  color: #67c23a;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.45;
}

.cart-house-foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cart-house-price {
  font-size: 19px;
  font-weight: 700;
  color: var(--danger, #f56c6c);
}

.cart-house-price i {
  font-size: 12px;
  font-weight: 400;
  font-style: normal;
  color: #909399;
}
</style>
