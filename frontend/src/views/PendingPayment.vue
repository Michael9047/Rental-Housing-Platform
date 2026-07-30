<template>
  <div class="pending-payment-page" v-loading="loading">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>待支付订单详情</h2>
    </div>

    <el-empty v-if="!loading && !booking && !propertyInfo" description="订单未找到" />

    <template v-if="booking || propertyInfo">
      <!-- Booking Info Card -->
      <el-card shadow="never" class="info-card" v-if="booking">
        <template #header>
          <div class="card-header-row">
            <span class="card-title">📋 预约信息</span>
            <el-tag :type="statusTagType" size="large" round>
              {{ statusLabel }}
            </el-tag>
          </div>
        </template>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单编号">#{{ booking.id }}</el-descriptions-item>
          <el-descriptions-item label="房源编号">#{{ booking.property_id }}</el-descriptions-item>
          <el-descriptions-item label="预约日期">{{ booking.scheduled_date || '未指定' }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="押金状态">
            {{ booking.deposit_status === 'paid' ? '已支付' : booking.deposit_status === 'confirmed' ? '已确认' : '待支付' }}
          </el-descriptions-item>
          <el-descriptions-item label="押金金额">¥{{ booking.deposit_amount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="服务费">¥{{ booking.service_fee || 0 }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(booking.created_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="booking.message" label="留言" :span="2">
            {{ booking.message }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Tenant Info Card -->
      <el-card shadow="never" class="info-card" v-if="booking">
        <template #header><span class="card-title">👤 租客信息</span></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="租客ID">#{{ booking.tenant_id }}</el-descriptions-item>
          <el-descriptions-item label="房东ID">#{{ booking.landlord_id }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Property Info Card -->
      <el-card shadow="never" class="info-card" v-if="propertyInfo">
        <template #header><span class="card-title">🏠 房源信息</span></template>
        <div class="property-preview" v-if="propertyInfo">
          <div class="preview-img" v-if="primaryImage">
            <img :src="primaryImage" :alt="propertyInfo.title" />
          </div>
          <div class="preview-body">
            <a class="preview-title" @click="goPropertyDetail(propertyInfo.id || (booking && booking.property_id))">
              {{ propertyInfo.title }}
            </a>
            <p class="preview-addr">{{ propertyInfo.address }}</p>
            <div class="preview-tags">
              <el-tag size="small">{{ propertyInfo.bedrooms }}室{{ propertyInfo.bathrooms }}卫</el-tag>
              <el-tag size="small" type="info">{{ propertyTypeLabel }}</el-tag>
              <el-tag size="small">{{ propertyInfo.district }}</el-tag>
            </div>
            <div class="preview-price">
              <span class="price-num">¥{{ propertyInfo.price_monthly }}</span>
              <span class="price-unit">/月</span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Bottom: Pay Button -->
      <div class="pay-action-bar" v-if="booking">
        <el-button type="primary" size="large" round @click="goDepositPay">
          支付押金
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { bookingService } from '@/services/booking'
import { propertyService } from '@/services/property'
import { getImageUrl } from '@/utils/image'
import { billService } from '@/services/bill'
import type { Booking } from '@/types/booking'

const route = useRoute()
const router = useRouter()

const booking = ref<Booking | null>(null)
const propertyInfo = ref<any>(null)
const loading = ref(false)

const statusLabels: Record<string, string> = {
  pending: '待确认', approved: '已确认', rejected: '已拒绝',
  cancelled: '已取消', completed: '已完成',
}
const statusTags: Record<string, string> = {
  pending: 'warning', approved: 'success', rejected: 'danger',
  cancelled: 'info', completed: '',
}

const typeLabels: Record<string, string> = {
  studio: '单间', '1-bed': '一室', '2-bed': '两室+', shared: '合租', house: '别墅',
}

const statusLabel = computed(() => statusLabels[booking.value?.status || ''] || '')
const statusTagType = computed(() => (statusTags[booking.value?.status || ''] || 'info') as 'warning' | 'success' | 'danger' | 'info' | '')
const propertyTypeLabel = computed(() => typeLabels[propertyInfo.value?.property_type || ''] || '')

const primaryImage = computed(() => {
  const imgs = propertyInfo.value?.images
  if (!imgs?.length) return null
  const p = imgs.find((i: any) => i.is_primary) || imgs[0]
  return getImageUrl(p.filename)
})

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('zh-CN')
}

function goDepositPay() {
  if (booking.value) {
    router.push({ path: `/booking/payment/${booking.value.id}/deposit` })
  }
}

/** 点击房源标题 → 纯客户端路由跳转至房源详情页，不发起任何后端请求 */
function goPropertyDetail(propertyId: number | string | undefined) {
  if (!propertyId) return
  router.push({ name: 'property-detail', params: { id: String(propertyId) } })
}

/** 优先走 bills 接口获取 property_id（需求指定路径 GET /api/v1/bills/{bill_id}） */
async function fetchBillProperty(billId: number): Promise<boolean> {
  try {
    const bill = await billService.getById(billId)
    if (bill?.property_id) {
      propertyInfo.value = await propertyService.getById(bill.property_id)
      // 如有 booking_id，补拉 booking 数据用于展示预约信息
      if (bill.booking_id) {
        try {
          booking.value = await bookingService.getById(bill.booking_id)
        } catch { /* booking fetch failed, property still shown */ }
      }
      return true
    }
  } catch { /* bills 接口暂未就绪，降级到 booking 链路 */ }
  return false
}

/** 降级：走原有 booking 链路 */
async function fetchViaBooking(bookingId: number): Promise<void> {
  booking.value = await bookingService.getById(bookingId)
  if (booking.value) {
    try {
      propertyInfo.value = await propertyService.getById(booking.value.property_id)
    } catch { /* property fetch failed */ }
  }
}

onMounted(async () => {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    // 优先走 bills 接口获取 property_id（需求指定路径）
    const billOk = await fetchBillProperty(id)
    if (!billOk) {
      // 降级：走原有 booking 链路
      await fetchViaBooking(id)
    }
  } catch { /* 两种链路均失败 */ }
  finally { loading.value = false }
})
</script>

<style scoped>
.pending-payment-page {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: 80px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  margin: 0;
}

.info-card {
  margin-bottom: 16px;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

/* ── Property Preview ──────────────── */

.property-preview {
  display: flex;
  gap: 16px;
}

.preview-img {
  width: 200px;
  height: 140px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
}

.preview-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-body {
  flex: 1;
}

.preview-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 4px;
  cursor: pointer;
  text-decoration: none;
  transition: opacity 0.2s;
  display: inline-block;
}

.preview-title:hover {
  opacity: 0.75;
  text-decoration: underline;
}

.preview-addr {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.preview-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.preview-price {
  margin-top: 4px;
}

.price-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--danger);
}

.price-unit {
  font-size: 13px;
  color: var(--text-muted);
  margin-left: 2px;
}

/* ── Pay Action Bar ─────────────────── */

.pay-action-bar {
  position: fixed;
  bottom: 0;
  left: 200px;
  right: 0;
  background: var(--bg-white);
  border-top: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  justify-content: flex-end;
  z-index: 50;
  box-shadow: 0 -2px 12px rgba(0,0,0,0.04);
}
</style>
