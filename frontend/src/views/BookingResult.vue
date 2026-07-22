<template>
  <main class="result-page" v-loading="loading">
    <el-result v-if="error" icon="error" title="无法查看订单" :sub-title="error" />
    <template v-else-if="order">
      <section class="status-card" :class="kind">
        <div class="status-icon" aria-hidden="true">{{ icon }}</div>
        <h1>{{ title }}</h1><p>{{ subtitle }}</p>
        <el-alert v-if="isReview" type="warning" :closable="false" title="正在核对/退款，请勿重复付款或重新预订" />
      </section>
      <section class="booking-card">
        <img v-if="order.property_image_url" :src="order.property_image_url" :alt="order.snapshot.property_name">
        <div v-else class="image-placeholder">暂无房源图片</div>
        <div class="property"><h2>{{ order.snapshot.property_name }}</h2><p>{{ order.snapshot.property_address }}</p></div>
        <dl>
          <dt>订单编号</dt><dd>{{ order.snapshot.order_number }}</dd><dt>合同编号</dt><dd>{{ order.snapshot.agreement_number }}</dd>
          <dt>入住日期</dt><dd>{{ order.snapshot.commencement_date }}</dd><dt>租赁结束日期</dt><dd>{{ order.snapshot.expiry_date }}</dd>
          <dt>租期</dt><dd>{{ order.snapshot.tenancy_months }} 个月</dd><dt>订单创建时间</dt><dd>{{ time(order.booking_created_at) }}</dd>
          <dt>状态更新时间</dt><dd>{{ time(order.status_updated_at) }}</dd><dt>实际支付币种及金额</dt><dd>{{ money(order.settlement_amount_minor, order.settlement_currency) }}</dd>
          <dt>人民币金额{{ order.settlement_currency==='CNY'?'':'（参考）' }}</dt><dd>{{ money(order.cny_reference_amount_minor, 'CNY') }}</dd>
          <dt>房源所在地货币金额</dt><dd>{{ money(order.settlement_amount_minor, order.property_currency) }}</dd>
        </dl>
        <div v-if="kind==='success'" class="detail-note"><b>支付成功时间：</b>{{ order.paid_at ? time(order.paid_at) : '已确认' }}<br><b>支付流水号：</b>{{ maskedTransaction }}<br><b>已支付金额：</b>{{ money(order.settlement_amount_minor, order.settlement_currency) }}<p>下一步：请留意账户通知，并提前准备合同中列明的身份证明及入住材料。</p></div>
        <div v-else-if="kind==='pending'" class="detail-note"><b>剩余有效时间：</b>{{ remaining }}<br><b v-if="order.failure_reason">说明：</b>{{ order.failure_reason }}</div>
        <div v-else class="detail-note"><b>取消原因：</b>超过24小时未完成支付<br><b>原支付截止时间：</b>{{ time(order.expires_at) }}<br><b>库存状态：</b>房源预留已释放</div>
      </section>
      <section class="actions">
        <template v-if="kind==='success'"><el-button type="primary" @click="$router.push('/bookings/tenant')">查看我的预订</el-button><el-button @click="property">返回房源详情</el-button></template>
        <template v-else-if="kind==='pending'"><el-button v-if="canRetry" type="primary" @click="retry">重新支付</el-button><el-button :loading="refreshing" @click="load">刷新支付状态</el-button></template>
        <template v-else><el-button @click="property">重新查看该房源</el-button><el-button type="primary" @click="rebook">重新发起预订</el-button></template>
      </section>
      <nav><a @click.prevent="property">返回房源详情</a><router-link to="/bookings/tenant">查看订单</router-link><a @click.prevent="download">查看/下载合同</a><router-link to="/customer-service">联系客服</router-link></nav>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { paymentService, type PaymentResult } from '@/services/payment'
import { contractService } from '@/services/contract'
import { canRetryPayment, paymentResultKind } from '@/utils/paymentResult'
const route=useRoute(), router=useRouter(); const order=ref<PaymentResult>(); const loading=ref(true), refreshing=ref(false), error=ref(''), now=ref(Date.now()); let timer=0
const status=computed(()=>order.value?.order_status || 'payment_pending'); const isReview=computed(()=>['payment_review','refund_pending'].includes(status.value))
const kind=computed(()=>paymentResultKind(status.value))
const title=computed(()=>isReview.value?'付款正在核对/退款':kind.value==='success'?'预订成功 / Booking Confirmed':kind.value==='cancelled'?'订单已自动取消':status.value==='payment_processing'?'支付结果确认中':status.value==='payment_failed'?'支付未成功':'等待支付')
const subtitle=computed(()=>isReview.value?'付款信息正在核对，必要时将安排退款。':kind.value==='success'?'付款已确认，房源预订成功。':kind.value==='cancelled'?'超过24小时未完成支付。':status.value==='payment_processing'?'请勿重复支付。':status.value==='payment_failed'?'可在有效期内重试。':'请在有效期内完成支付。')
const icon=computed(()=>kind.value==='success'?'✓':kind.value==='cancelled'?'×':isReview.value?'!':'…'); const canRetry=computed(()=>canRetryPayment(status.value,order.value?.expires_at||'',Date.now()))
const remaining=computed(()=>{const s=Math.max(0,Math.floor((Date.parse(order.value?.expires_at||'')-now.value)/1000));return `${Math.floor(s/3600)}小时 ${Math.floor(s%3600/60)}分 ${s%60}秒`})
const maskedTransaction=computed(()=>{const v=order.value?.transaction_id||'';return v.length>8?`${v.slice(0,4)}****${v.slice(-4)}`:'****'})
const money=(minor:number,currency:string)=>new Intl.NumberFormat('zh-CN',{style:'currency',currency}).format(minor/100); const time=(v:string)=>new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'medium'}).format(new Date(v))
async function load(){refreshing.value=true;try{order.value=await paymentService.getResult(Number(route.params.id));const suffix=kind.value==='success'?'success':kind.value==='cancelled'?'cancelled':'payment-status';const canonical=`/booking/order/${route.params.id}/${suffix}`;if(route.path!==canonical)await router.replace(canonical)}catch(e:any){error.value=e?.response?.status===403?'你无权查看该订单':e?.response?.data?.detail||'服务器暂时不可用'}finally{loading.value=false;refreshing.value=false}}
function property(){router.push(`/property/${order.value?.snapshot.property_id}`)} function rebook(){router.push(`/booking/${order.value?.snapshot.property_id}/move-in-date`)} function retry(){router.push(`/booking/payment/${route.params.id}/deposit`)}
async function download(){if(!order.value)return;const blob=await contractService.download(order.value.snapshot.agreement_id);const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`${order.value.snapshot.agreement_number}.pdf`;a.click();URL.revokeObjectURL(url)}
onMounted(()=>{load();timer=window.setInterval(()=>now.value=Date.now(),1000)});onBeforeUnmount(()=>clearInterval(timer))
</script>

<style scoped>
.result-page{max-width:960px;margin:0 auto;padding:32px 20px 70px}.status-card{text-align:center;padding:28px;border-radius:16px;margin-bottom:20px;background:#fff7e8}.status-card.success{background:#edf9f1}.status-card.cancelled{background:#f6f6f7}.status-icon{width:58px;height:58px;border-radius:50%;display:grid;place-items:center;margin:auto;background:#d99019;color:#fff;font-size:34px}.success .status-icon{background:#28a466}.cancelled .status-icon{background:#777}.status-card h1{margin:12px 0 6px}.booking-card{display:grid;grid-template-columns:230px 1fr;gap:20px;background:#fff;border:1px solid #e4e7ed;border-radius:16px;padding:22px}.booking-card img,.image-placeholder{width:230px;height:160px;object-fit:cover;border-radius:10px;background:#f2f3f5;display:grid;place-items:center;color:#999}.property{align-self:center}.property h2{margin:0 0 8px}.property p{color:#666}dl{grid-column:1/-1;display:grid;grid-template-columns:150px 1fr 150px 1fr;gap:12px 18px;border-top:1px solid #eee;padding-top:20px}dt{color:#777}dd{margin:0;overflow-wrap:anywhere}.detail-note{grid-column:1/-1;background:#f7f8fa;padding:16px;border-radius:10px;line-height:1.9}.actions{display:flex;justify-content:center;gap:12px;margin:24px}nav{display:flex;justify-content:center;flex-wrap:wrap;gap:24px}nav a{cursor:pointer;color:#1769e0}@media(max-width:700px){.booking-card{grid-template-columns:1fr}.booking-card img,.image-placeholder{width:100%;height:210px}dl{grid-template-columns:120px 1fr}.actions{flex-wrap:wrap}}
</style>
