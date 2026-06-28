<template>
  <div class="deposit-payment-page" v-loading="loading">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>支付押金</h2>
    </div>

    <el-empty v-if="!loading && !booking" description="订单未找到" />

    <template v-if="booking && !paySuccess">
      <!-- Deposit Amount Card -->
      <el-card shadow="never" class="amount-card">
        <template #header><span class="card-title">💰 押金金额</span></template>

        <div class="deposit-amount-section">
          <div class="amount-primary">
            <span class="amount-label">应付押金</span>
            <span class="amount-value">¥{{ depositAmount }}</span>
          </div>
          <el-divider />
          <div class="amount-dual">
            <div class="dual-item">
              <span class="dual-label">人民币 (CNY)</span>
              <span class="dual-value cny">¥{{ depositAmount }}</span>
            </div>
            <div class="dual-item">
              <span class="dual-label">美元 (USD)</span>
              <span class="dual-value usd">${{ usdAmount }}</span>
            </div>
          </div>
          <p class="amount-note">* 汇率参考中国银行当日现汇卖出价，实际以支付页面为准</p>
        </div>
      </el-card>

      <!-- Order Summary Card -->
      <el-card shadow="never" class="info-card">
        <template #header><span class="card-title">📋 订单摘要</span></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单编号">#{{ booking.id }}</el-descriptions-item>
          <el-descriptions-item label="房源编号">#{{ booking.property_id }}</el-descriptions-item>
          <el-descriptions-item label="押金金额">¥{{ depositAmount }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">{{ bookingStatusLabel }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Payment Methods -->
      <el-card shadow="never" class="info-card">
        <template #header><span class="card-title">💳 选择支付方式</span></template>

        <div class="method-options">
          <div
            class="method-card"
            :class="{ active: payMethod === 'wechat' }"
            @click="payMethod = 'wechat'"
          >
            <span class="method-icon">💚</span>
            <span class="method-name">微信支付</span>
            <span class="method-desc">当前环境使用模拟回调确认支付</span>
          </div>
        </div>
      </el-card>

      <!-- Pay Button -->
      <div class="pay-footer">
        <div class="pay-total">
          <span class="total-label">应付押金：</span>
          <span class="total-amount">¥{{ depositAmount }}</span>
          <span class="total-usd">（≈ ${{ usdAmount }}）</span>
        </div>
        <el-button type="primary" size="large" round :loading="paying" @click="doPayment">
          确认支付 ¥{{ depositAmount }}
        </el-button>
      </div>
    </template>

    <!-- Success -->
    <el-result
      v-if="paySuccess"
      icon="success"
      title="支付成功！"
      sub-title="押金已支付！电子合同已生成，可在个人中心「支付中心」查看"
    >
      <template #extra>
        <el-button v-if="contractId" type="primary" @click="$router.push(`/contract/${contractId}`)">
          查看电子合同
        </el-button>
        <el-button type="primary" plain @click="$router.push('/profile?tab=contracts')">查看支付中心</el-button>
        <el-button @click="$router.push('/')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { bookingService } from '@/services/booking'
import { paymentService } from '@/services/payment'
import { contractService } from '@/services/contract'
import type { Booking } from '@/types/booking'

const route = useRoute()

const booking = ref<Booking | null>(null)
const loading = ref(false)
const paying = ref(false)
const paySuccess = ref(false)
const payMethod = ref('wechat')
const contractId = ref<string | null>(null)

// Exchange rate: ~7.25 CNY per USD (approximate reference rate)
const USD_RATE = 7.25

const depositAmount = computed(() => {
  return booking.value?.deposit_amount || 0
})

const usdAmount = computed(() => {
  return (depositAmount.value / USD_RATE).toFixed(2)
})

const bookingStatusLabel = computed(() => {
  const labels: Record<string, string> = {
    pending: '待确认', approved: '已确认', rejected: '已拒绝',
    cancelled: '已取消', completed: '已完成',
  }
  return labels[booking.value?.status || ''] || ''
})

async function doPayment() {
  if (!booking.value) return
  paying.value = true
  try {
    const payment = await paymentService.createPayment({
      booking_id: booking.value.id,
      amount: depositAmount.value,
    })
    await paymentService.paymentCallback(payment.id)
    const contract = await contractService.generate(booking.value.id)
    contractId.value = contract.id
    paySuccess.value = true
    ElMessage.success('定金支付成功！')
  } catch {
    ElMessage.error('支付失败，请重试')
  } finally {
    paying.value = false
  }
}

onMounted(async () => {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    booking.value = await bookingService.getById(id)
  } catch { /* handle */ }
  finally { loading.value = false }
})
</script>

<style scoped>
.deposit-payment-page {
  max-width: 700px;
  margin: 0 auto;
  padding-bottom: 100px;
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

/* ── Amount Card ────────────────────── */

.amount-card {
  margin-bottom: 16px;
  border: 2px solid var(--primary);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.deposit-amount-section {
  text-align: center;
}

.amount-primary {
  padding: 20px 0;
}

.amount-label {
  display: block;
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.amount-value {
  font-size: 48px;
  font-weight: 800;
  color: var(--danger);
  letter-spacing: -1px;
}

.amount-dual {
  display: flex;
  justify-content: center;
  gap: 48px;
  padding: 12px 0;
}

.dual-item {
  text-align: center;
}

.dual-label {
  display: block;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.dual-value {
  font-size: 22px;
  font-weight: 700;
}

.dual-value.cny {
  color: var(--danger);
}

.dual-value.usd {
  color: var(--primary);
}

.amount-note {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

/* ── Info Card ──────────────────────── */

.info-card {
  margin-bottom: 16px;
}

/* ── Payment Methods ─────────────────── */

.method-options {
  display: flex;
  gap: 16px;
}

.method-card {
  flex: 1;
  padding: 20px;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.method-card:hover {
  border-color: var(--primary);
}

.method-card.active {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.12);
}

.method-icon {
  font-size: 32px;
}

.method-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.method-desc {
  font-size: 12px;
  color: var(--text-muted);
}

/* ── Pay Footer ──────────────────────── */

.pay-footer {
  position: fixed;
  bottom: 0;
  left: 200px;
  right: 0;
  background: var(--bg-white);
  border-top: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 50;
  box-shadow: 0 -2px 12px rgba(0,0,0,0.04);
}

.pay-total {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.total-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.total-amount {
  font-size: 28px;
  font-weight: 700;
  color: var(--danger);
}

.total-usd {
  font-size: 13px;
  color: var(--text-muted);
}
</style>
