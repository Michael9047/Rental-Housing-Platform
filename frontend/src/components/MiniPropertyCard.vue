<!-- 精简房源卡片 —— 用于对话流和水平滑动行 -->
<template>
  <!-- variant="chat"：横向宽卡片，对话流中 -->
  <div v-if="variant === 'chat'" class="mini-card mini-card--chat">
    <div class="mini-card__image">
      <img v-if="imageUrl" :src="imageUrl" :alt="property.title" />
      <div v-else class="mini-card__placeholder">
        <el-icon :size="28"><PictureFilled /></el-icon>
      </div>
    </div>
    <div class="mini-card__body">
      <h4 class="mini-card__title">{{ property.title }}</h4>
      <div class="mini-card__meta">
        <span class="mini-card__price">¥{{ fmtPrice }}</span>
        <span>{{ property.area_sqm ? property.area_sqm + '㎡' : '' }}</span>
        <span>·</span>
        <span>{{ typeLabel }}</span>
        <span>·</span>
        <span>{{ property.bedrooms }}室{{ property.bathrooms }}卫</span>
      </div>
      <div class="mini-card__desc" v-if="desc">{{ desc }}</div>
      <div class="mini-card__actions">
        <el-button size="small" text type="primary" @click.stop="goDetail">详情</el-button>
        <el-button
          v-if="authStore.isLoggedIn"
          size="small"
          :type="inCart ? 'success' : 'primary'"
          plain
          @click.stop="toggleCart"
        >
          {{ inCart ? '已加入对比' : '加入对比' }}
        </el-button>
      </div>
    </div>
  </div>

  <!-- variant="scroll"：纵向紧凑卡片，水平滑动行 -->
  <div v-else class="mini-card mini-card--scroll">
    <div class="mini-card__image mini-card__image--scroll">
      <img v-if="imageUrl" :src="imageUrl" :alt="property.title" />
      <div v-else class="mini-card__placeholder">
        <el-icon :size="24"><PictureFilled /></el-icon>
      </div>
    </div>
    <div class="mini-card__body mini-card__body--scroll">
      <h4 class="mini-card__title mini-card__title--scroll">{{ property.title }}</h4>
      <div class="mini-card__price mini-card__price--scroll">¥{{ fmtPrice }}/月</div>
      <div class="mini-card__meta--scroll">
        {{ property.area_sqm ? property.area_sqm + '㎡ · ' : '' }}{{ typeLabel }} · {{ property.bedrooms }}室
      </div>
      <el-button
        v-if="authStore.isLoggedIn"
        size="small"
        :type="inCart ? 'success' : 'primary'"
        plain
        class="mini-card__cart-btn"
        @click.stop="toggleCart"
      >
        {{ inCart ? '✓ 已加入' : '+ 对比' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PictureFilled } from '@element-plus/icons-vue'
import { useCartStore } from '@/stores/cart'
import { useAuthStore } from '@/stores/auth'
import type { Property, PropertySearchResult } from '@/types/property'

const props = withDefaults(defineProps<{
  property: Property | PropertySearchResult
  variant?: 'chat' | 'scroll'
  desc?: string
}>(), {
  variant: 'chat',
  desc: '',
})

const router = useRouter()
const cartStore = useCartStore()
const authStore = useAuthStore()
const busy = ref(false)

const typeLabels: Record<string, string> = {
  apartment: '公寓', house: '别墅', studio: '单间', shared: '合租',
}

const typeLabel = computed(() => typeLabels[props.property.property_type] || props.property.property_type)
const fmtPrice = computed(() => {
  const p = props.property.price_monthly
  return p ? Number(p).toLocaleString() : '?'
})
const imageUrl = computed(() => {
  const imgs = props.property.images
  if (!imgs || imgs.length === 0) return null
  const primary = imgs.find((i: any) => i.is_primary) || imgs[0]
  const fn = primary.filename || ''
  if (!fn) return null
  return fn.startsWith('http') ? fn : `/api/v1/uploads/${fn}`
})
const inCart = computed(() => cartStore.has(props.property.id))

function goDetail() {
  router.push(`/property/${props.property.id}`)
}

async function toggleCart() {
  if (busy.value) return
  // 未登录 → 跳转登录页（保留返回路径）
  const token = localStorage.getItem('access_token')
  if (!token) {
    router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    return
  }
  busy.value = true
  try {
    if (inCart.value) {
      await cartStore.remove(props.property.id)
    } else {
      await cartStore.add(props.property.id)
    }
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.mini-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; }

/* ── chat variant ── */
.mini-card--chat { display: flex; max-width: 520px; cursor: pointer; }
.mini-card--chat:hover { border-color: #409EFF; }
.mini-card__image { width: 140px; min-height: 100px; flex-shrink: 0; background: #f5f7fa; }
.mini-card__image img { width: 100%; height: 100%; object-fit: cover; }
.mini-card__placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: #c0c4cc; }
.mini-card__body { flex: 1; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.mini-card__title { margin: 0; font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini-card__meta { font-size: 12px; color: #606266; display: flex; gap: 4px; flex-wrap: wrap; }
.mini-card__price { color: #f56c6c; font-weight: 600; }
.mini-card__desc { font-size: 12px; color: #67c23a; line-height: 1.5; }
.mini-card__actions { display: flex; gap: 8px; margin-top: 4px; }

/* ── scroll variant ── */
.mini-card--scroll { width: 170px; flex-shrink: 0; cursor: pointer; display: flex; flex-direction: column; }
.mini-card--scroll:hover { border-color: #409EFF; }
.mini-card__image--scroll { width: 100%; height: 100px; }
.mini-card__body--scroll { padding: 8px; text-align: center; gap: 4px; }
.mini-card__title--scroll { font-size: 12px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; white-space: normal; }
.mini-card__price--scroll { font-size: 14px; }
.mini-card__meta--scroll { font-size: 11px; color: #909399; }
.mini-card__cart-btn { width: 100%; margin-top: 4px; font-size: 12px; }
</style>
