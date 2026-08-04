<template>
  <main class="order-detail" v-loading="loading">
    <el-result v-if="error" icon="error" title="无法查看订单" :sub-title="error">
      <template #extra><el-button @click="router.push('/profile?tab=bills')">返回我的订单</el-button></template>
    </el-result>
    <template v-else-if="order">
      <header><div><h1>订单详情</h1><p>{{ order.order_id }}</p></div><el-tag size="large">{{ order.status_label }}</el-tag></header>
      <el-alert v-if="order.failure_reason" type="warning" :closable="false" :title="order.failure_reason" />
      <el-card shadow="never">
        <template #header><b>申请人信息</b></template>
        <dl><dt>姓名</dt><dd>{{ order.applicant_name }}</dd><dt>手机号</dt><dd>{{ order.applicant_phone_masked || '未提供' }}</dd><dt>邮箱</dt><dd>{{ order.applicant_email_masked || '未提供' }}</dd></dl>
      </el-card>
      <el-card shadow="never">
        <template #header><b>房源信息</b></template>
        <div class="property-grid">
          <img v-if="order.property_image_url" :src="order.property_image_url" :alt="order.property_name" />
          <div v-else class="image-placeholder">暂无图片</div>
          <dl>
            <dt>房源名称</dt><dd>{{ order.property_name }}</dd><dt>房源编号</dt><dd>{{ order.property_id }}</dd>
            <dt>类型</dt><dd>{{ propertyType }}</dd><dt>城市 / 国家地区</dt><dd>{{ order.property_city }} / {{ order.property_country }}</dd>
            <dt>地址</dt><dd>{{ order.property_address }}</dd><dt>月租</dt><dd>{{ money(order.monthly_rent_minor, order.property_currency) }}</dd>
            <dt>入住日期</dt><dd>{{ order.lease_start_date || '—' }}</dd><dt>结束日期</dt><dd>{{ order.lease_end_date || '—' }}</dd>
            <dt>租期</dt><dd>{{ order.lease_months || '—' }}个月</dd><dt>简介</dt><dd>{{ order.property_description || '暂无简介' }}</dd>
          </dl>
        </div>
        <el-button @click="router.push(`/property/${order.property_id}`)">查看房源详情</el-button>
      </el-card>
      <el-card shadow="never">
        <template #header><b>订单与支付</b></template>
        <dl>
          <dt>订单编号</dt><dd>{{ order.order_id }}</dd><dt>合同编号</dt><dd>{{ order.agreement_number }}</dd>
          <dt>订单状态</dt><dd>{{ order.order_status }}</dd><dt>支付状态</dt><dd>{{ order.status_label }}</dd>
          <dt>预订状态</dt><dd>{{ order.booking_status === 'confirmed' ? '预订成功' : '预订未成功' }}</dd>
          <dt>押金</dt><dd>{{ money(order.deposit_amount_minor, order.property_currency) }}</dd><dt>服务费</dt><dd>{{ money(order.service_fee_amount_minor, order.property_currency) }}</dd>
          <dt>税费</dt><dd>{{ money(order.tax_amount_minor, order.property_currency) }}</dd><dt>当前总计</dt><dd>{{ money(order.settlement_amount_minor, order.settlement_currency) }}</dd>
          <dt>实际扣款币种</dt><dd>{{ order.settlement_currency }}</dd><dt>人民币金额</dt><dd>{{ money(order.cny_reference_amount_minor, 'CNY') }}</dd>
          <dt>当地货币金额</dt><dd>{{ money(order.property_amount_minor, order.property_currency) }}</dd><dt>汇率</dt><dd>{{ order.exchange_rate }}（{{ order.exchange_rate_source }}）</dd>
          <dt>汇率时间</dt><dd>{{ dateTime(order.exchange_rate_timestamp) }}</dd><dt>创建时间</dt><dd>{{ dateTime(order.created_at) }}</dd>
          <dt>支付截止</dt><dd>{{ dateTime(order.expires_at) }}</dd><dt>状态更新时间</dt><dd>{{ dateTime(order.status_updated_at) }}</dd>
          <dt>支付成功时间</dt><dd>{{ order.paid_at ? dateTime(order.paid_at) : '—' }}</dd><dt>支付流水号</dt><dd>{{ order.transaction_id_masked || '—' }}</dd>
        </dl>
        <p v-if="remaining > 0 && order.booking_status !== 'confirmed'" class="countdown">剩余支付时间：{{ duration(remaining) }}</p>
      </el-card>
      <footer>
        <el-button @click="router.push(`/my-contracts/${order.agreement_id}`)">查看合同</el-button>
        <el-button :disabled="!order.agreement_id" @click="downloadContract">下载合同</el-button>
        <el-button @click="router.push(`/property/${order.property_id}`)">查看房源</el-button>
        <el-button v-if="order.booking_status !== 'confirmed'" :loading="refreshing" @click="load">刷新支付状态</el-button>
        <el-button v-if="['payment_expired','cancelled'].includes(order.payment_status)" @click="router.push(`/booking/${order.property_id}/move-in-date`)">重新预订该房源</el-button>
        <el-button v-if="order.can_pay" type="primary" :loading="validating" @click="enterPayment">{{ order.payment_action_label }}</el-button>
        <el-button @click="router.push('/customer-service')">联系客服</el-button>
      </footer>
    </template>
  </main>
</template>

<script setup lang="ts">
// 订单详情只展示服务端脱敏及验证后的数据，不读取本地临时申请资料。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { contractService } from '@/services/contract'
import { paymentService, type TenantOrderDetail } from '@/services/payment'
import { remainingPaymentSeconds } from '@/utils/orderPresentation'

const route=useRoute(),router=useRouter();const order=ref<TenantOrderDetail>();const loading=ref(true),refreshing=ref(false),validating=ref(false),error=ref(''),now=ref(Date.now());let timer=0
const remaining=computed(()=>remainingPaymentSeconds(order.value?.expires_at||'',now.value))
const propertyType=computed(()=>({apartment:'公寓',house:'独立屋',studio:'单间',shared:'合租'} as Record<string,string>)[order.value?.property_type||'']||order.value?.property_type)
const money=(minor:number,currency:string)=>new Intl.NumberFormat('zh-CN',{style:'currency',currency}).format(minor/100)
const dateTime=(value:string)=>new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'medium'}).format(new Date(value))
const duration=(seconds:number)=>`${String(Math.floor(seconds/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`
async function load(){refreshing.value=true;try{order.value=await paymentService.getMyOrder(Number(route.params.id));error.value=''}catch(e:any){error.value=e?.response?.status===404?'订单不存在或您无权查看。':'订单暂时无法加载，请稍后重试。'}finally{loading.value=false;refreshing.value=false}}
async function enterPayment(){if(!order.value)return;validating.value=true;try{const result=await paymentService.validatePayment(order.value.booking_id);if(!result.can_pay){ElMessage.warning(result.reason||'当前订单暂不能支付');await load();return}await router.push(`/booking/payment/${order.value.booking_id}/deposit`)}catch(e:any){ElMessage.error(e?.response?.data?.detail||'支付资格校验失败')}finally{validating.value=false}}
async function downloadContract(){if(!order.value)return;try{const link=await contractService.getSignedDownloadLink(order.value.agreement_id);if(!link.url){ElMessage.info(link.message||'签署版 PDF 正在生成');return}window.location.assign(link.url)}catch{ElMessage.error('合同下载失败，请稍后重试')}}
onMounted(()=>{load();timer=window.setInterval(()=>now.value=Date.now(),1000)});onBeforeUnmount(()=>window.clearInterval(timer))
</script>

<style scoped>
.order-detail{width:min(1050px,calc(100% - 32px));margin:28px auto 70px}.order-detail>header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px}.order-detail h1{margin:0}.order-detail header p{color:var(--text-muted)}.el-card{margin-top:18px}dl{display:grid;grid-template-columns:145px minmax(0,1fr) 145px minmax(0,1fr);gap:14px 20px;margin:0}dt{color:var(--text-muted)}dd{margin:0;overflow-wrap:anywhere}.property-grid{display:grid;grid-template-columns:240px 1fr;gap:22px;margin-bottom:16px}.property-grid img,.image-placeholder{width:240px;height:180px;object-fit:cover;border-radius:10px;background:#f3f5f7}.image-placeholder{display:grid;place-items:center;color:#999}.countdown{padding:14px;background:#fff7e8;color:#a85b00;border-radius:8px}footer{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;margin-top:22px}@media(max-width:768px){.order-detail{width:min(100% - 20px,1050px)}dl{grid-template-columns:110px 1fr}.property-grid{grid-template-columns:1fr}.property-grid img,.image-placeholder{width:100%;height:210px}footer{justify-content:flex-start}}
</style>
