<template>
  <main class="payment-page" v-loading="loading">
    <header><h1>支付当前应付金额</h1><el-tag type="warning">支付服务商测试模式 · 不会真实扣款</el-tag></header>
    <el-result v-if="error" icon="error" title="无法加载支付订单" :sub-title="error" />
    <template v-else-if="payment">
      <section class="amount-panel">
        <p>本次应付押金 / 当前应付金额</p>
        <strong>{{ money(payment.settlement_amount_minor, payment.settlement_currency) }}</strong>
        <span class="charge-label">实际扣款币种：{{ payment.settlement_currency }}</span>
        <div class="currency-grid">
          <div><small>人民币金额</small><b>{{ money(payment.cny_reference_amount_minor, 'CNY') }}</b><em>{{ payment.settlement_currency === 'CNY' ? '实际扣款' : '汇率参考' }}</em></div>
          <div><small>房源所在地货币</small><b>{{ money(payment.settlement_amount_minor, payment.property_currency) }}</b><em>{{ payment.settlement_currency === payment.property_currency ? '实际扣款' : '汇率参考' }}</em></div>
        </div>
        <p class="rate">汇率：1 {{ payment.property_currency }} = {{ payment.exchange_rate }} CNY · 来源：{{ payment.exchange_rate_source }} · 锁定：{{ dateTime(payment.exchange_rate_timestamp) }}</p>
      </section>
      <el-alert :type="expired ? 'error' : 'warning'" :closable="false" :title="expired ? '支付订单已过期' : `支付剩余时间：${countdown}`" />
      <section class="cards">
        <el-card shadow="never"><template #header><b>订单信息</b></template><dl>
          <dt>订单编号</dt><dd>{{ payment.snapshot.order_number }}</dd><dt>订单状态</dt><dd>{{ statusLabel }}</dd>
          <dt>房源编号</dt><dd>{{ payment.snapshot.property_id }}</dd><dt>房源名称</dt><dd>{{ payment.snapshot.property_name }}</dd>
          <dt>完整地址</dt><dd>{{ payment.snapshot.property_address }}</dd><dt>租客姓名</dt><dd>{{ payment.snapshot.tenant_name }}</dd>
          <dt>入住日期</dt><dd>{{ payment.snapshot.commencement_date }}</dd><dt>租赁结束</dt><dd>{{ payment.snapshot.expiry_date }}</dd>
          <dt>租期</dt><dd>{{ payment.snapshot.tenancy_months }} 个月</dd><dt>合同编号</dt><dd>{{ payment.snapshot.agreement_number }}</dd>
          <dt>支付截止</dt><dd>{{ dateTime(payment.expires_at) }}</dd>
        </dl></el-card>
        <el-card shadow="never"><template #header><b>费用明细</b></template><dl class="fees">
          <dt>押金</dt><dd>{{ format(payment.snapshot.fees.deposit) }}</dd><dt>服务费</dt><dd>{{ format(payment.snapshot.fees.service_fee) }}</dd>
          <dt>税费</dt><dd>{{ format(payment.snapshot.fees.tax) }}</dd><dt class="total">当前总计</dt><dd class="total">{{ format(payment.snapshot.fees.current_total) }}</dd>
        </dl><el-divider/><p><b>支付方式</b></p>
          <el-radio-group v-model="selectedMethod" class="payment-methods">
            <el-radio v-for="item in methods" :key="item.method" :value="item.method" :disabled="!item.available">
              {{ methodLabel(item.method) }}
              <el-tag v-if="item.test_mode" size="small" type="warning">测试模式</el-tag>
              <small v-else-if="!item.available">{{ item.reason || '暂未开通' }}</small>
            </el-radio>
          </el-radio-group>
          <p class="card-safety">银行卡由收单机构托管页面处理，平台不会接收或保存卡号、CVV、磁道数据或验证码。</p>
        </el-card>
      </section>
      <footer><div><router-link :to="`/property/${payment.snapshot.property_id}`">返回房源</router-link><router-link :to="`/contract/${payment.snapshot.agreement_id}`">查看已签合同</router-link></div><el-button type="primary" size="large" :disabled="expired || payment.status === 'success'" @click="checkout">{{ payment.status === 'success' ? '支付成功' : '进入测试收银台' }}</el-button></footer>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { paymentService, type Money, type PaymentMethod, type PaymentMethodAvailability, type PaymentResponse } from '@/services/payment'

const route = useRoute(); const payment = ref<PaymentResponse>(); const methods = ref<PaymentMethodAvailability[]>([]); const selectedMethod = ref<PaymentMethod>('CARD_CHECKOUT'); const loading = ref(true); const error = ref(''); const now = ref(Date.now()); let timer = 0
const expired = computed(() => !payment.value || now.value >= Date.parse(payment.value.expires_at))
const countdown = computed(() => { const s = Math.max(0, Math.floor((Date.parse(payment.value?.expires_at || '') - now.value) / 1000)); return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s%3600/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}` })
const statusLabel = computed(() => { const status=payment.value?.order_status || payment.value?.status || ''; return ({ contract_signed:'合同已签', payment_pending:'等待付款', payment_processing:'支付处理中', paid:'支付成功、预订成功', payment_failed:'支付失败，可在期限内重试', payment_expired:'超过24小时未付款', cancelled:'订单已取消', refund_pending:'异常付款等待退款', refunded:'已退款', payment_review:'金额或回调异常，等待人工核对' } as Record<string,string>)[status] || status })
const money = (minor:number, currency:string) => new Intl.NumberFormat('zh-CN',{style:'currency',currency}).format(minor/100)
const format = (v:Money) => `${v.currency} ${v.decimal}`
const dateTime = (v:string) => new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'medium'}).format(new Date(v))
function checkout(){ if (payment.value?.checkout_url) window.location.assign(payment.value.checkout_url) }
const methodLabel = (method:PaymentMethod) => ({ WECHAT_PAY:'微信支付', ALIPAY:'支付宝', CARD_CHECKOUT:'银行卡托管收银台' } as Record<PaymentMethod,string>)[method]
function idempotencyKey(bookingId:number, purpose:string){const storageKey=`payment-idempotency:${bookingId}:${purpose}`;let key=sessionStorage.getItem(storageKey);if(!key){key=crypto.randomUUID();sessionStorage.setItem(storageKey,key)}return key}
async function load(){ const id=Number(route.params.id); try { methods.value=await paymentService.getAvailableMethods(); selectedMethod.value=methods.value.find(item=>item.available)?.method || 'CARD_CHECKOUT'; const existing=await paymentService.getByBooking(id); if(existing.order_status==='payment_failed'&&Date.now()<Date.parse(existing.expires_at)){payment.value=await paymentService.createPayment(id,idempotencyKey(id,`retry:${existing.id}`),selectedMethod.value)}else{payment.value=existing} } catch(e:any) { if(e?.response?.status===404){ payment.value=await paymentService.createPayment(id,idempotencyKey(id,'initial'),selectedMethod.value) } else error.value=e?.response?.data?.detail || '服务器暂时不可用' } finally { loading.value=false } }
onMounted(()=>{ load(); timer=window.setInterval(async()=>{ now.value=Date.now(); if(route.query.returned && payment.value && payment.value.status!=='success') payment.value=await paymentService.getPayment(payment.value.id) },1000) }); onBeforeUnmount(()=>clearInterval(timer))
</script>

<style scoped>
.payment-page{max-width:1100px;margin:0 auto;padding:28px 24px 110px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.amount-panel{background:linear-gradient(135deg,#fff7ef,#fff);border:1px solid #f1c797;border-radius:16px;padding:28px;text-align:center;margin-bottom:18px}.amount-panel>strong{display:block;font-size:44px;color:#d94b24}.charge-label{display:inline-block;margin:8px;padding:5px 12px;background:#d94b24;color:#fff;border-radius:20px}.currency-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;max-width:620px;margin:20px auto}.currency-grid div{display:grid;gap:6px;padding:14px;border:1px solid #eee;border-radius:10px}.currency-grid em{font-size:12px;color:#777}.rate{font-size:13px;color:#666}.cards{display:grid;grid-template-columns:1.5fr 1fr;gap:18px;margin-top:18px}dl{display:grid;grid-template-columns:120px 1fr;gap:12px;margin:0}dt{color:#777}dd{margin:0;overflow-wrap:anywhere}.total{font-weight:700;color:#d94b24;border-top:1px solid #eee;padding-top:12px}footer{position:fixed;bottom:0;left:200px;right:0;background:white;border-top:1px solid #ddd;padding:16px 5%;display:flex;align-items:center;justify-content:space-between;z-index:10}footer div{display:flex;gap:24px}@media(max-width:768px){.payment-page{padding:18px 14px 100px}.cards,.currency-grid{grid-template-columns:1fr}header{align-items:flex-start;gap:10px;flex-direction:column}footer{left:0;padding:12px 16px}.amount-panel>strong{font-size:34px}dl{grid-template-columns:100px 1fr}}
.payment-methods{display:grid;gap:12px}.payment-methods .el-radio{margin-right:0}.payment-methods small{margin-left:8px;color:#909399}.card-safety{font-size:12px;line-height:1.6;color:#606266}
</style>
