<!-- 支付结果与预订进度页面。 -->
<template>
  <main class="result-page" v-loading="loading">
    <el-result v-if="error" icon="error" title="无法查看订单" :sub-title="error" />
    <template v-else-if="order">
      <section class="status-card" :class="kind">
        <div class="status-icon" aria-hidden="true">{{ icon }}</div>
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
        <div v-if="isProgressStage" class="progress-steps" aria-label="预订进度">
          <span class="done">1. 支付完成</span><span :class="{ active: kind === 'awaiting_confirmation' }">2. BM 确认房号</span><span :class="{ active: kind === 'awaiting_signature' }">3. 签署合同</span><span>4. 预订成功</span>
        </div>
        <el-alert v-if="isReview" type="warning" :closable="false" title="正在核对付款或退款，请勿重复付款或重新预订" />
      </section>

      <section class="booking-card">
        <img v-if="order.property_image_url" :src="order.property_image_url" :alt="order.snapshot.property_name">
        <div v-else class="image-placeholder">暂无房源图片</div>
        <div class="property"><h2>{{ order.snapshot.property_name }}</h2><p>{{ order.snapshot.property_address }}</p></div>
        <dl>
          <dt>订单编号</dt><dd>{{ order.snapshot.order_number }}</dd>
          <dt>入住日期</dt><dd>{{ order.snapshot.commencement_date }}</dd>
          <dt>租赁结束日期</dt><dd>{{ order.snapshot.expiry_date }}</dd>
          <dt>租期</dt><dd>{{ order.snapshot.tenancy_months }} 个月</dd>
          <dt>订单创建时间</dt><dd>{{ time(order.booking_created_at) }}</dd>
          <dt>状态更新时间</dt><dd>{{ time(order.status_updated_at) }}</dd>
          <dt>实际支付金额</dt><dd>{{ money(order.settlement_amount_minor, order.settlement_currency) }}</dd>
          <dt>支付流水号</dt><dd>{{ maskedTransaction }}</dd>
        </dl>
        <div v-if="kind === 'awaiting_confirmation'" class="detail-note warning-note">
          <b>预订金已支付，订单正在等待 BM 确认。</b>
          <p>BM 确认真实房号后会生成合同并通知你。合同签署完成前，订单不会显示为“预订成功”。</p>
        </div>
        <div v-else-if="kind === 'awaiting_signature'" class="detail-note warning-note">
          <b>房号已确认，请签署合同。</b>
          <p>完成合同签署后，订单才会正式变为“预订成功”。</p>
        </div>
        <div v-else-if="kind === 'success'" class="detail-note success-note"><b>合同已签署，预订正式成功。</b></div>
        <div v-else-if="kind === 'pending'" class="detail-note"><b>剩余有效时间：</b>{{ remaining }}</div>
        <div v-else class="detail-note"><b>状态说明：</b>{{ order.failure_reason || '订单当前未生效，请查看订单状态或联系客服。' }}</div>
      </section>

      <section class="actions">
        <el-button v-if="kind === 'awaiting_signature'" type="primary" @click="openContract">查看并签署合同</el-button>
        <el-button v-if="kind === 'awaiting_confirmation'" :loading="refreshing" @click="load">刷新确认状态</el-button>
        <el-button v-if="kind === 'success'" type="primary" @click="$router.push('/profile')">查看我的订单</el-button>
        <el-button v-if="kind === 'pending' && canRetry" type="primary" @click="retry">重新支付</el-button>
        <el-button v-if="kind === 'pending'" :loading="refreshing" @click="load">刷新支付状态</el-button>
        <el-button @click="property">返回房源详情</el-button>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { paymentService, type PaymentResult } from '@/services/payment'
import { canRetryPayment, paymentResultKind } from '@/utils/paymentResult'

const route = useRoute()
const router = useRouter()
const order = ref<PaymentResult>()
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const now = ref(Date.now())
let timer = 0

const status = computed(() => order.value?.order_status || order.value?.status || '')
const kind = computed(() => paymentResultKind(status.value))
const isReview = computed(() => kind.value === 'review')
const isProgressStage = computed(() => ['awaiting_confirmation', 'awaiting_signature'].includes(kind.value))
const title = computed(() => ({
  awaiting_confirmation: '支付成功，等待 BM 确认房号',
  awaiting_signature: '房号已确认，等待签署合同',
  success: '预订成功 / Booking Confirmed',
  cancelled: '订单已取消', expired: '订单已过期', failed: '支付未成功', review: '付款正在核对',
  pending: status.value === 'payment_processing' ? '支付结果确认中' : '等待支付', unknown: '订单状态更新中', refunded: '款项已退回',
}[kind.value]))
const subtitle = computed(() => ({
  awaiting_confirmation: 'BM 管理员正在核对可用房间，请耐心等待通知。',
  awaiting_signature: '请查看房号和合同内容，完成签署后预订才正式生效。',
  success: '房号已确认，合同已签署，预订现已正式生效。',
  cancelled: '此订单已取消。', expired: '支付期限已过，请重新发起预订。', failed: '可在有效期内安全重试。', review: '请勿重复付款。',
  pending: '请在有效期内完成支付。', unknown: '请稍后刷新查看最新状态。', refunded: '此预订已失效。',
}[kind.value]))
const icon = computed(() => kind.value === 'success' ? '✓' : ['cancelled', 'expired', 'failed'].includes(kind.value) ? '×' : '!')
const canRetry = computed(() => canRetryPayment(status.value, order.value?.expires_at || '', Date.now()))
const remaining = computed(() => { const seconds = Math.max(0, Math.floor((Date.parse(order.value?.expires_at || '') - now.value) / 1000)); return `${Math.floor(seconds / 3600)}小时 ${Math.floor(seconds % 3600 / 60)}分 ${seconds % 60}秒` })
const maskedTransaction = computed(() => { const value = order.value?.transaction_id || ''; return value.length > 8 ? `${value.slice(0, 4)}****${value.slice(-4)}` : '****' })
const money = (minor: number, currency: string) => new Intl.NumberFormat('zh-CN', { style: 'currency', currency }).format(minor / 100)
const time = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value))

async function load() {
  refreshing.value = true
  try {
    order.value = await paymentService.getResult(Number(route.params.bookingId))
    const suffix = kind.value === 'success' ? 'success' : kind.value === 'awaiting_confirmation' ? 'waiting-confirmation' : kind.value === 'awaiting_signature' ? 'awaiting-signature' : kind.value === 'cancelled' ? 'cancelled' : 'payment-status'
    const canonical = `/booking/order/${route.params.bookingId}/${suffix}`
    if (route.path !== canonical) await router.replace(canonical)
  } catch (exception: any) {
    error.value = exception?.response?.status === 403 ? '你无权查看该订单' : exception?.response?.data?.detail || '服务暂时不可用'
  } finally { loading.value = false; refreshing.value = false }
}
function property() { router.push(`/property/${order.value?.snapshot.property_id}`) }
function retry() { router.push(`/booking/payment/${route.params.bookingId}/deposit`) }
function openContract() { router.push(`/booking/order/${route.params.bookingId}/contract`) }
onMounted(() => { load(); timer = window.setInterval(() => { now.value = Date.now() }, 1000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.result-page{max-width:960px;margin:0 auto;padding:32px 20px 70px}.status-card{text-align:center;padding:28px;border-radius:16px;margin-bottom:20px;background:#fff7e8;border:1px solid #f4d28b}.status-card.success{background:#edf9f1;border-color:#b8e3c6}.status-card.cancelled,.status-card.expired,.status-card.failed{background:#f6f6f7;border-color:#ddd}.status-icon{width:58px;height:58px;border-radius:50%;display:grid;place-items:center;margin:auto;background:#d99019;color:#fff;font-size:34px}.success .status-icon{background:#28a466}.status-card h1{margin:12px 0 6px}.progress-steps{display:flex;justify-content:center;flex-wrap:wrap;gap:10px;margin-top:20px}.progress-steps span{padding:7px 11px;border-radius:999px;background:#fff3d2;color:#8b6508}.progress-steps .done{background:#e5f5ea;color:#257a43}.progress-steps .active{background:#f5c85b;color:#5f4300;font-weight:700}.booking-card{display:grid;grid-template-columns:230px 1fr;gap:20px;background:#fff;border:1px solid #e4e7ed;border-radius:16px;padding:22px}.booking-card img,.image-placeholder{width:230px;height:160px;object-fit:cover;border-radius:10px;background:#f2f3f5;display:grid;place-items:center;color:#999}.property{align-self:center}.property h2{margin:0 0 8px}.property p{color:#666}dl{grid-column:1/-1;display:grid;grid-template-columns:150px 1fr 150px 1fr;gap:12px 18px;border-top:1px solid #eee;padding-top:20px}dt{color:#777}dd{margin:0;overflow-wrap:anywhere}.detail-note{grid-column:1/-1;background:#f7f8fa;padding:16px;border-radius:10px;line-height:1.8}.detail-note p{margin:6px 0 0}.warning-note{background:#fff7e8;color:#7d5700}.success-note{background:#edf9f1;color:#237541}.actions{display:flex;justify-content:center;flex-wrap:wrap;gap:12px;margin:24px}@media(max-width:700px){.booking-card{grid-template-columns:1fr}.booking-card img,.image-placeholder{width:100%;height:210px}dl{grid-template-columns:120px 1fr}}
</style>
