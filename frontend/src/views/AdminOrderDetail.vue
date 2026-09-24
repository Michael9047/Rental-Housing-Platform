<template>
  <main class="order-detail" v-loading="loading">
    <el-result v-if="error" icon="error" title="无法查看订单" :sub-title="error">
      <template #extra>
        <el-button @click="load">重新加载</el-button>
        <el-button @click="router.push({ name: 'bm-orders' })">返回订单管理</el-button>
      </template>
    </el-result>

    <template v-else-if="order">
      <nav class="back-row" aria-label="订单导航">
        <el-button link @click="router.push({ name: 'bm-orders' })">← 返回订单管理</el-button>
        <span>BM 订单视图</span>
      </nav>

      <header class="order-hero">
        <div>
          <p class="eyebrow">ORDER #{{ order.id }}</p>
          <h1>订单详情</h1>
          <p class="hero-copy">{{ statusView.description }}</p>
        </div>
        <el-tag :type="statusView.type" effect="dark" size="large" round>{{ statusView.label }}</el-tag>
      </header>

      <section class="progress-panel" aria-label="订单流程">
        <div v-for="(item, index) in progressItems" :key="item.label" class="progress-item" :class="{ done: statusView.step >= index + 1 }">
          <span class="progress-dot">{{ statusView.step >= index + 1 ? '✓' : index + 1 }}</span>
          <div><b>{{ item.label }}</b><small>{{ item.detail }}</small></div>
        </div>
      </section>

      <el-alert v-if="order.status_reason" type="warning" :closable="false" :title="order.status_reason" />

      <el-card shadow="never">
        <template #header><b>申请人信息</b></template>
        <dl>
          <dt>姓名</dt><dd>{{ order.tenant_name || '未填写' }}</dd>
          <dt>手机号码</dt><dd>{{ order.phone || '未提供' }}</dd>
        </dl>
      </el-card>

      <el-card shadow="never">
        <template #header><b>房源信息</b></template>
        <div class="property-grid">
          <img v-if="order.property_image_url" :src="order.property_image_url" :alt="order.unit_type_name" />
          <div v-else class="image-placeholder">暂无图片</div>
          <dl>
            <dt>公寓名称</dt><dd>{{ order.institute_name }}</dd>
            <dt>户型名称</dt><dd>{{ order.unit_type_name }}</dd>
            <dt>类型</dt><dd>{{ propertyType }}</dd>
            <dt>城市 / 国家地区</dt><dd>{{ locationText }}</dd>
            <dt>地址</dt><dd>{{ order.property_address || '未填写' }}</dd>
            <dt>确认房号</dt><dd>{{ order.room_number || '等待确认' }}</dd>
            <dt>月租</dt><dd>{{ propertyMoney(order.monthly_rent) }}</dd>
            <dt>入住日期</dt><dd>{{ order.move_in_date || '—' }}</dd>
            <dt>结束日期</dt><dd>{{ order.contract_end || '—' }}</dd>
            <dt>租期</dt><dd>{{ order.lease_months ? `${order.lease_months} 个月` : '—' }}</dd>
            <dt>简介</dt><dd>{{ order.property_description || '暂无简介' }}</dd>
          </dl>
        </div>
        <el-button v-if="order.unit_type_id" @click="router.push(`/property/${order.unit_type_id}`)">查看房源详情</el-button>
      </el-card>

      <el-card shadow="never">
        <template #header><b>订单与支付</b></template>
        <dl>
          <dt>订单编号</dt><dd>#{{ order.id }}</dd>
          <dt>订单状态</dt><dd>{{ statusView.label }}（{{ order.status_source }}）</dd>
          <dt>支付状态</dt><dd>{{ paymentStatusLabel }}</dd>
          <dt>预订金</dt><dd>{{ minorMoney(order.booking_deposit_minor, order.payment_currency) }}</dd>
          <dt>支付方式</dt><dd>{{ order.payment_method || '—' }}</dd>
          <dt>支付时间</dt><dd>{{ dateTime(order.paid_at) }}</dd>
          <dt>房源押金参考</dt><dd>{{ propertyMoney(order.property_deposit) }}</dd>
          <dt>租金总额参考</dt><dd>{{ propertyMoney(order.total_rent) }}</dd>
          <dt>订单创建时间</dt><dd>{{ dateTime(order.created_at) }}</dd>
          <dt>状态更新时间</dt><dd>{{ dateTime(order.finalized_at) }}</dd>
        </dl>
      </el-card>

      <el-card shadow="never">
        <template #header><b>合同信息</b></template>
        <dl>
          <dt>合同编号</dt><dd>{{ order.agreement_number || '—' }}</dd>
          <dt>合同状态</dt><dd>{{ contractStatusLabel }}</dd>
          <dt>合同模板</dt><dd>{{ order.contract_template_name || '—' }}</dd>
          <dt>模板版本</dt><dd>{{ order.contract_template_version || '—' }}</dd>
          <dt>合同开始日期</dt><dd>{{ order.contract_start || '—' }}</dd>
          <dt>合同结束日期</dt><dd>{{ order.contract_end || '—' }}</dd>
          <dt>合同生成时间</dt><dd>{{ dateTime(order.contract_generated_at) }}</dd>
          <dt>租客签署时间</dt><dd>{{ dateTime(order.contract_signed_at) }}</dd>
        </dl>
      </el-card>

      <footer>
        <el-button @click="load">刷新订单状态</el-button>
        <el-button type="primary" @click="router.push({ name: 'landlord-contracts' })">进入合同管理</el-button>
      </footer>
    </template>
  </main>
</template>

<script setup lang="ts">
// BM 订单详情复制租客详情的信息架构，但使用独立路由、权限接口与展示语义。
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { adminOrderStatusPresentation } from '@/utils/adminOrderPresentation'

interface AdminOrderDetail {
  id: number
  tenant_name: string
  phone: string | null
  institute_id: number | null
  institute_name: string
  unit_type_id: number | null
  unit_type_name: string
  property_type: string | null
  property_description: string | null
  property_image_url: string | null
  property_address: string | null
  property_city: string | null
  property_country: string | null
  room_number: string | null
  move_in_date: string | null
  lease_months: number | null
  contract_start: string | null
  contract_end: string | null
  status: string
  status_source: string
  status_reason: string | null
  created_at: string
  finalized_at: string
  monthly_rent: number | null
  total_rent: number | null
  property_deposit: number | null
  property_currency: string | null
  booking_deposit_minor: number | null
  payment_currency: string
  payment_status: string | null
  paid_at: string | null
  payment_method: string | null
  agreement_id: string | null
  agreement_number: string | null
  contract_status: string | null
  contract_template_name: string | null
  contract_template_version: string | null
  contract_generated_at: string | null
  contract_signed_at: string | null
}

const route = useRoute()
const router = useRouter()
const order = ref<AdminOrderDetail>()
const loading = ref(true)
const error = ref('')

const statusView = computed(() => adminOrderStatusPresentation(order.value?.status_source || ''))
const propertyType = computed(() => ({ apartment: '公寓', house: '独立屋', studio: '单间', shared: '合租' } as Record<string, string>)[order.value?.property_type || ''] || order.value?.property_type || '未填写')
const locationText = computed(() => [order.value?.property_city, order.value?.property_country].filter(Boolean).join(' / ') || '未填写')
const paymentStatusLabel = computed(() => ({ success: '支付成功', pending: '等待支付', processing: '处理中', failed: '支付失败', expired: '已过期', review: '待人工核验', refunded: '已退款' } as Record<string, string>)[order.value?.payment_status || ''] || order.value?.payment_status || '—')
const contractStatusLabel = computed(() => ({ generated: '已生成，待签署', signed: '已签署并生效' } as Record<string, string>)[order.value?.contract_status || ''] || order.value?.contract_status || '—')
const progressItems = [
  { label: '提交订单', detail: '租客资料与租期已确认' },
  { label: '支付成功', detail: '平台预订金已到账' },
  { label: '确认房号', detail: 'BM 确认房号并生成合同' },
  { label: '合同生效', detail: '租客完成签署' },
]

function minorMoney(amount: number | null, currency = 'CNY') {
  if (amount === null || amount === undefined) return '—'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency }).format(amount / 100)
}

function propertyMoney(amount: number | null) {
  if (amount === null || amount === undefined || !order.value?.property_currency) return '—'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: order.value.property_currency }).format(amount)
}

function dateTime(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value)) : '—'
}

async function load() {
  const bookingId = Number(route.params.id)
  if (!Number.isInteger(bookingId) || bookingId <= 0) {
    error.value = '订单编号无效'
    loading.value = false
    return
  }
  loading.value = true
  try {
    order.value = (await api.get(`/admin/orders/${bookingId}`)).data
    error.value = ''
  } catch (requestError: any) {
    const code = requestError?.response?.status
    error.value = code === 403 ? '无权查看该订单' : code === 404 ? '订单不存在或尚未进入订单管理' : '订单详情加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.order-detail { --ink: #172238; --muted: #69758a; width: min(1050px, calc(100% - 32px)); margin: 28px auto 70px; color: var(--ink); }
.back-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; color: var(--muted); font-size: 13px; }
.order-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; padding: 28px 30px; color: white; background: linear-gradient(120deg, #12213d, #214f78 72%, #2c7181); border-radius: 18px; box-shadow: 0 18px 42px rgb(20 51 78 / 18%); }
.eyebrow { margin: 0 0 8px; color: #9ed9e1; font-size: 12px; font-weight: 800; letter-spacing: .16em; }
.order-hero h1 { margin: 0; font-family: Georgia, 'Noto Serif SC', serif; font-size: 34px; letter-spacing: .02em; }
.hero-copy { max-width: 650px; margin: 12px 0 0; color: #dcecf3; line-height: 1.7; }
.progress-panel { display: grid; grid-template-columns: repeat(4, 1fr); margin: 18px 0; padding: 18px 20px; background: #f7fafb; border: 1px solid #e1eaed; border-radius: 14px; }
.progress-item { position: relative; display: flex; align-items: center; gap: 10px; color: #8b95a6; }
.progress-item:not(:last-child)::after { position: absolute; top: 16px; right: 10px; width: calc(100% - 145px); height: 2px; background: #dbe3e7; content: ''; }
.progress-item.done { color: #176d64; }
.progress-item.done:not(:last-child)::after { background: #76b7aa; }
.progress-dot { display: grid; place-items: center; flex: 0 0 32px; height: 32px; color: white; background: #aeb8c5; border-radius: 50%; font-weight: 800; }
.done .progress-dot { background: #168273; }
.progress-item b, .progress-item small { display: block; }
.progress-item small { margin-top: 3px; font-size: 11px; }
.el-card { margin-top: 18px; border-color: #e2e8ed; border-radius: 14px; }
:deep(.el-card__header) { padding: 18px 22px; background: #fbfcfd; }
dl { display: grid; grid-template-columns: 145px minmax(0, 1fr) 145px minmax(0, 1fr); gap: 14px 20px; margin: 0; }
dt { color: var(--muted); }
dd { margin: 0; overflow-wrap: anywhere; }
.property-grid { display: grid; grid-template-columns: 240px 1fr; gap: 22px; margin-bottom: 16px; }
.property-grid img, .image-placeholder { width: 240px; height: 180px; object-fit: cover; border-radius: 12px; background: linear-gradient(145deg, #eef2f5, #dfe8ec); }
.image-placeholder { display: grid; place-items: center; color: #8793a3; }
footer { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 22px; }
@media (max-width: 860px) { .progress-panel { grid-template-columns: 1fr 1fr; gap: 18px; } .progress-item::after { display: none; } }
@media (max-width: 768px) { .order-detail { width: min(100% - 20px, 1050px); } .order-hero { padding: 22px; } .order-hero h1 { font-size: 28px; } dl { grid-template-columns: 110px 1fr; } .property-grid { grid-template-columns: 1fr; } .property-grid img, .image-placeholder { width: 100%; height: 210px; } footer { justify-content: flex-start; } }
@media (max-width: 480px) { .order-hero { flex-direction: column; } .progress-panel { grid-template-columns: 1fr; } }
</style>
