<template>
  <el-card shadow="never" class="info-card room-type-card">
    <template #header>
      <span class="card-header-text">🏠 房屋类型</span>
    </template>

    <!-- 第一行：左侧图片 + 右侧房屋概述 -->
    <div class="room-type-row1">
      <div class="room-type-image">
        <img
          v-if="primaryImageUrl"
          :src="primaryImageUrl"
          :alt="property.title"
          class="room-img"
        />
        <div v-else class="image-placeholder">
          <span class="placeholder-icon">🏠</span>
          <span>暂无图片</span>
        </div>
      </div>

      <div class="room-summary">
        <p class="summary-text">{{ roomSummary }}</p>
      </div>
    </div>

    <!-- 第二行：设施标签（全宽，最多 5×2=10 个，仅文字） -->
    <div class="room-type-row2">
      <div class="feature-tags" ref="tagsContainer">
        <span
          v-for="tag in visibleFeatureTags"
          :key="tag"
          class="feature-tag"
        >{{ tag }}</span>
      </div>
      <el-button
        v-if="allFeatureTags.length > visibleCount"
        text
        type="primary"
        size="small"
        class="view-more-btn"
        @click="showFeatureDialog = true"
      >
        查看更多 →
      </el-button>
    </div>

    <!-- 第三行：价格 + 起租时长（全宽） -->
    <div class="room-type-row3">
      <div class="footer-price">
        <span class="price-value">¥{{ property.price_monthly }}</span>
        <span class="price-unit">/月</span>
      </div>
      <div class="footer-lease">
        <span class="lease-icon">📅</span>
        <span>起租{{ displayLeaseMonths }}个月</span>
      </div>
    </div>

    <!-- 查看全部设施弹窗 -->
    <el-dialog
      v-model="showFeatureDialog"
      title="全部设施"
      width="560px"
      :close-on-click-modal="true"
      class="feature-dialog"
    >
      <div class="feature-grid">
        <div
          v-for="tag in allFeatureTags"
          :key="tag"
          class="feature-grid-item"
        >
          {{ tag }}
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="showFeatureDialog = false">
          关闭
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Property } from '@/types/property'

const props = defineProps<{
  property: Property
}>()

// ── 弹窗状态 ──
const showFeatureDialog = ref(false)

// 行内最多展示 5 列 × 2 行 = 10 个
const visibleCount = 10

// ── 主图 URL ──
const primaryImageUrl = computed(() => {
  const images = props.property.images
  if (!images || images.length === 0) return null
  const primary = images.find((img) => img.is_primary) || images[0]
  const fn = primary.filename
  return fn.startsWith('http') ? fn : `/api/v1/uploads/${fn}`
})

// ── 房屋概述（一句自然描述） ──
const roomSummary = computed(() => {
  const p = props.property
  const parts: string[] = []

  // 卧室
  if (p.property_type === 'studio') {
    parts.push('单间')
  } else if (p.bedrooms === 0) {
    parts.push('开间')
  } else {
    parts.push(`${p.bedrooms}室`)
  }

  // 卫浴
  const hasEnsuite =
    p.property_type === 'studio' ||
    (p.bathrooms >= p.bedrooms && p.bedrooms > 0) ||
    (p.amenities || []).includes('独立卫浴')
  parts.push(hasEnsuite ? '独立卫浴' : '公共卫浴')

  // 厨房
  const hasPrivateKitchen =
    p.property_type === 'house' ||
    p.property_type === 'apartment' ||
    p.property_type === '1-bed' ||
    p.property_type === '2-bed' ||
    (p.amenities || []).includes('独立厨房')
  parts.push(hasPrivateKitchen ? '独立厨房' : '共享厨房')

  return parts.join(' · ')
})

// ── 合法设施白名单 ──
const VALID_AMENITIES: string[] = [
  '电梯', '空调', '洗衣机', '冰箱', 'WiFi', '暖气', '阳台',
  '独立卫浴', '健身房', '自习室', '游泳池', '停车场',
  '24小时前台', '校车接驳', '签证咨询', '可养宠物', '近地铁',
  '包水电', '精装修', '首次出租', '南北通透',
]

// ── 全部设施标签（DB数据 + 智能默认 + 描述关键词） ──
const allFeatureTags = computed<string[]>(() => {
  const p = props.property
  const tags = new Set<string>()

  // 优先使用 DB 中的 amenities
  if (p.amenities && p.amenities.length > 0) {
    p.amenities.forEach((a) => {
      if (VALID_AMENITIES.includes(a)) tags.add(a)
    })
  }

  // 基于房屋类型的智能默认（始终补充）
  const typeDefaults: Record<string, string[]> = {
    apartment: ['电梯', 'WiFi', '空调'],
    house: ['车位', '全屋家电', '阳台'],
    studio: ['独立卫浴', 'WiFi', '空调'],
    shared: ['包水电', 'WiFi'],
  }
  const defaults = typeDefaults[p.property_type] || []
  defaults.forEach((d) => tags.add(d))

  // 从描述中提取关键词
  if (p.description) {
    if (/宠物|猫|狗/.test(p.description)) tags.add('可养宠物')
    if (/暖气/.test(p.description)) tags.add('暖气')
    if (/阳台/.test(p.description)) tags.add('阳台')
    if (/地铁|交通/.test(p.description)) tags.add('近地铁')
    if (/精装/.test(p.description)) tags.add('精装修')
  }

  // 基于属性的智能规则
  if (p.area_sqm && p.area_sqm > 60) tags.add('阳台')
  if (p.price_monthly > 8000) tags.add('精装修')
  if (p.floor && p.floor > 1) tags.add('电梯')

  return Array.from(tags)
})

// 行内展示前 N 个
const visibleFeatureTags = computed(() =>
  allFeatureTags.value.slice(0, visibleCount)
)

// 起租月数（缺省兜底 12）
const displayLeaseMonths = computed(() => {
  const m = props.property.min_lease_months
  return m && m > 0 ? m : 12
})
</script>

<style scoped>
/* ── 第一行：图片 + 概述 ────────────── */
.room-type-row1 {
  display: flex;
  gap: 20px;
  align-items: center;
  margin-bottom: 16px;
}

@media (max-width: 750px) {
  .room-type-row1 {
    flex-direction: column;
    align-items: flex-start;
  }
}

/* ── 左侧图片 ──────────────────────── */
.room-type-image {
  flex: 0 0 300px;
  width: 300px;
  height: 200px;
  border-radius: var(--radius);
  overflow: hidden;
  background: #f5f7fa;
  position: relative;
}

.room-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  color: #c0c4cc;
  font-size: 13px;
}

.placeholder-icon {
  font-size: 40px;
}

/* ── 右侧概述文字 ──────────────────── */
.room-summary {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}

.summary-text {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.6;
  margin: 0;
}

/* ── 第二行：设施标签（全宽）────────── */
.room-type-row2 {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;
}

.feature-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
  overflow: hidden;
}

.feature-tag {
  display: inline-block;
  font-size: 13px;
  padding: 4px 14px;
  border-radius: 6px;
  background: #f5f7fa;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  white-space: nowrap;
  line-height: 1.5;
}

.view-more-btn {
  flex-shrink: 0;
  font-size: 13px;
  margin-top: 2px;
}

/* ── 第三行：价格 + 起租（全宽）─────── */
.room-type-row3 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.footer-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.footer-price .price-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--danger);
  line-height: 1;
}

.footer-price .price-unit {
  font-size: 13px;
  color: var(--text-muted);
}

.footer-lease {
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.lease-icon {
  font-size: 15px;
}

/* ── 全部设施弹窗 ──────────────────── */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 8px 0;
}

.feature-grid-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 12px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  font-size: 14px;
  color: var(--text-primary);
  transition: all 0.2s;
}

.feature-grid-item:hover {
  background: var(--primary-light);
  border-color: var(--primary);
}

/* ── 暗色模式 ──────────────────────── */
[data-theme="dark"] .feature-tag {
  background: #262727;
  border-color: #3a3a3c;
  color: #c8c8cc;
}

[data-theme="dark"] .room-type-image {
  background: #1e1e1e;
}

[data-theme="dark"] .image-placeholder {
  color: #666;
}
</style>
