<template>
  <div class="property-card" @click="goDetail">
    <!-- Image -->
    <div class="card-image">
      <img
        v-if="primaryImageUrl"
        :src="primaryImageUrl"
        :alt="property.title"
        class="property-img"
      />
      <div v-else class="image-placeholder">
        <el-icon :size="40" color="#c0c4cc"><PictureFilled /></el-icon>
        <span>暂无图片</span>
      </div>
      <!-- Match Badge -->
      <span v-if="showSimilarity && property.similarity != null" class="match-badge">
        匹配 {{ (property.similarity * 100).toFixed(0) }}%
      </span>
      <!-- District Tag -->
      <span class="district-badge">{{ property.district }}</span>
    </div>

    <!-- Info -->
    <div class="card-body">
      <h3 class="card-title" :title="property.title">{{ property.title }}</h3>

      <div class="card-tags">
        <el-tag size="small" type="info">{{ typeLabels[property.property_type] || property.property_type }}</el-tag>
        <el-tag size="small">{{ property.bedrooms }}室{{ property.bathrooms }}卫</el-tag>
        <el-tag size="small" type="info" v-if="property.area_sqm">{{ property.area_sqm }}㎡</el-tag>
      </div>

      <div class="card-amenities" v-if="amenityTags.length > 0">
        <el-tag
          v-for="tag in amenityTags"
          :key="tag"
          size="small"
          effect="plain"
          round
          class="amenity-tag"
        >{{ tag }}</el-tag>
      </div>

      <p class="card-address" :title="property.address">
        <el-icon :size="14"><LocationFilled /></el-icon>
        {{ property.address }}
      </p>

      <div class="card-footer">
        <div class="price-block">
          <span class="card-price">¥{{ property.price_monthly }}</span>
          <span class="price-unit">/月</span>
        </div>
        <div class="card-actions" @click.stop>
          <el-button size="small" text type="primary" @click="goDetail">查看详情</el-button>
          <el-button
            v-if="showQuickBook"
            size="small"
            type="primary"
            @click="handleBook"
          >
            一键预订
          </el-button>
          <el-tooltip
            v-if="authStore.isLoggedIn"
            :content="inCart ? '点击移出候选清单' : '加入候选清单'"
            placement="top"
          >
            <button
              class="add-cart-btn"
              :class="{ 'is-added': inCart }"
              :disabled="busy"
              @click="handleToggleCart"
            >
              <el-icon><Check v-if="inCart" /><Plus v-else /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PictureFilled, LocationFilled, Plus, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { Property, PropertySearchResult, PropertyType } from '@/types/property'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const props = defineProps<{
  property: Property | PropertySearchResult
  showSimilarity?: boolean
  showQuickBook?: boolean
}>()

const emit = defineEmits<{
  (e: 'book', property: Property | PropertySearchResult): void
}>()

const router = useRouter()
const authStore = useAuthStore()
const cartStore = useCartStore()

const busy = ref(false)
const inCart = computed(() => cartStore.has(props.property.id))

async function handleToggleCart() {
  if (busy.value) return
  busy.value = true
  try {
    if (inCart.value) {
      await cartStore.remove(props.property.id)
      ElMessage.info(`已从候选清单移出「${props.property.title}」`)
    } else {
      await cartStore.add(props.property.id)
      ElMessage.success(`已将「${props.property.title}」加入候选清单`)
    }
  } catch {
    // 错误提示由 api 拦截器统一处理
  } finally {
    busy.value = false
  }
}

const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}

const primaryImageUrl = computed(() => {
  const images = props.property.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  return `/api/v1/uploads/${primary.filename}`
})

// Smart amenity tags inferred from property attributes
const amenityTags = computed(() => {
  const tags: string[] = []
  const p = props.property

  // District-based
  if (p.district) {
    if (/苏州|北京|上海|广州|深圳|杭州|南京|成都|武汉/.test(p.district)) {
      tags.push(`${p.district}本地`)
    } else if (/伦敦|曼彻斯特|爱丁堡|剑桥|牛津/.test(p.district)) {
      tags.push('英国留学')
    } else if (/纽约|洛杉矶|旧金山|波士顿|芝加哥/.test(p.district)) {
      tags.push('美国留学')
    } else if (/悉尼|墨尔本|布里斯班/.test(p.district)) {
      tags.push('澳洲留学')
    } else {
      tags.push(p.district)
    }
  }

  // Property type-based
  if (p.property_type === 'apartment') {
    tags.push('电梯', 'WiFi')
  } else if (p.property_type === 'studio') {
    tags.push('独立卫浴', 'WiFi')
  } else if (p.property_type === 'house') {
    tags.push('车位', '全屋家电')
  } else if (p.property_type === 'shared') {
    tags.push('包水电', 'WiFi')
  }

  // Bedrooms-based
  if (p.bedrooms >= 2) {
    tags.push('近地铁')
  }

  // Price-based
  if (p.price_monthly < 3000) {
    tags.push('平价好房')
  } else if (p.price_monthly > 8000) {
    tags.push('精装修')
  }

  // Description keyword hints
  if (p.description) {
    if (/短租|短租/.test(p.description)) tags.push('短租支持')
    if (/宠物|猫|狗/.test(p.description)) tags.push('可养宠物')
    if (/暖气/.test(p.description)) tags.push('暖气')
  }

  // Deduplicate while preserving order
  return [...new Set(tags)].slice(0, 5)
})

function goDetail() {
  router.push(`/property/${props.property.id}`)
}

function handleBook() {
  emit('book', props.property)
}
</script>

<style scoped>
.property-card {
  background: var(--bg-white);
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid var(--border);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.property-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--primary);
}

/* ── Image ────────────────────────── */

.card-image {
  position: relative;
  height: 200px;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.property-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #c0c4cc;
  font-size: 13px;
}

.match-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  background: linear-gradient(135deg, #67c23a, #85ce61);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(103, 194, 58, 0.3);
}

.district-badge {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 4px;
}

/* ── Body ─────────────────────────── */

.card-body {
  padding: 14px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.card-amenities {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.amenity-tag {
  font-size: 11px !important;
  padding: 2px 10px !important;
  background: #fdf6ec !important;
  border-color: #f5dab1 !important;
  color: #b88230 !important;
}

.card-address {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 12px;
}

.card-footer {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.price-block {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.card-price {
  font-size: 22px;
  font-weight: 700;
  color: var(--danger);
  line-height: 1;
}

.price-unit {
  font-size: 12px;
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 右下角绿色圆形「加入候选清单」按钮 */
.add-cart-btn {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border: none;
  border-radius: 50%;
  background: #67c23a;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(103, 194, 58, 0.4);
  transition: transform 0.15s, background 0.15s;
}

.add-cart-btn:hover:not(:disabled) {
  transform: scale(1.12);
  background: #5daf34;
}

.add-cart-btn.is-added {
  background: #b3e19d;
  cursor: default;
  box-shadow: none;
}

.add-cart-btn :deep(.el-icon) {
  font-size: 15px;
}
</style>
