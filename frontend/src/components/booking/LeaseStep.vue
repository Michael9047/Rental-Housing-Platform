<template>
  <el-card shadow="never" class="step-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">📝 选择租期</span>
        <span class="card-subtitle">
          最短租期 {{ minLease }} 个月，最长 {{ maxLease }} 个月
        </span>
      </div>
    </template>

    <div class="lease-section">
      <div class="lease-options">
        <div
          v-for="opt in bookingFlow.lease_options"
          :key="opt.value"
          class="lease-option-card"
          :class="{ active: bookingFlow.lease_months === opt.value }"
          @click="selectLease(opt.value)"
        >
          <div class="lease-months">{{ opt.label }}</div>
          <div class="lease-total">
            总租金 {{ formatPrice(opt.value * priceMonthly) }}
          </div>
        </div>
      </div>

      <div class="fee-breakdown" v-if="bookingFlow.lease_months > 0">
        <h4 class="breakdown-title">费用明细</h4>
        <div class="fee-row">
          <span>月租金 × {{ bookingFlow.lease_months }}个月</span>
          <span>{{ formatPrice(totalPrice) }}</span>
        </div>
        <div class="fee-row">
          <span>押金</span>
          <span>{{ formatPrice(bookingFlow.deposit_amount) }}</span>
        </div>
        <div class="fee-row" v-if="bookingFlow.service_fee > 0">
          <span>服务费（{{ serviceFeeRate }}%）</span>
          <span>{{ formatPrice(bookingFlow.service_fee) }}</span>
        </div>
        <div class="fee-row total">
          <span>首次应付合计</span>
          <span class="total-price">{{ formatPrice(firstPayment) }}</span>
        </div>
        <div class="fee-note">* 首期支付：押金 + 首月租金 + 服务费</div>
      </div>
    </div>

    <div class="step-footer">
      <el-button size="large" @click="$emit('prev')">上一步</el-button>
      <el-button type="primary" size="large" :disabled="bookingFlow.lease_months <= 0" @click="$emit('next')">
        下一步：填写个人信息 →
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useBookingFlowStore } from '@/stores/bookingFlow'
import { formatPriceWithDual } from '@/data/currency'

defineEmits<{
  (e: 'prev'): void
  (e: 'next'): void
}>()

const bookingFlow = useBookingFlowStore()

const minLease = computed(() => bookingFlow.property?.min_lease_months ?? 1)
const maxLease = computed(() => bookingFlow.property?.max_lease_months || 60)
const priceMonthly = computed(() => Number(bookingFlow.property?.price_monthly) || 0)
const countryCode = computed(() => bookingFlow.property?.country || 'CN')
const totalPrice = computed(() => bookingFlow.total_price)
const serviceFeeRate = computed(() => {
  const rate = bookingFlow.property?.service_fee_rate
  return rate ? (rate * 100).toFixed(0) : '0'
})
const firstPayment = computed(() => {
  if (!bookingFlow.property) return 0
  const monthly = priceMonthly.value
  return Math.round(monthly + bookingFlow.deposit_amount + bookingFlow.service_fee)
})

function selectLease(months: number) {
  bookingFlow.setLeaseMonths(months)
}

function formatPrice(priceCNY: number): string {
  return formatPriceWithDual(priceCNY, countryCode.value)
}
</script>

<style scoped>
.step-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: normal;
}

.lease-section {
  margin-bottom: 24px;
}

.lease-options {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.lease-option-card {
  border: 2px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.lease-option-card:hover {
  border-color: var(--primary);
  background: var(--primary-light);
}

.lease-option-card.active {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.12);
}

.lease-months {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.lease-total {
  font-size: 15px;
  font-weight: 600;
  color: var(--danger);
}

.fee-breakdown {
  background: var(--bg-light);
  border-radius: var(--radius);
  padding: 16px 20px;
}

.breakdown-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.fee-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.fee-row.total {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  font-weight: 700;
  color: var(--text-primary);
}

.total-price {
  color: var(--danger);
  font-size: 18px;
}

.fee-note {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.step-footer {
  display: flex;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}
</style>
