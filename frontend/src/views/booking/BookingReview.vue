<!-- 预订流程第五步：核对摘要并记录四份政策同意。 -->
<template>
  <BookingFlowLayout
    title="信息确认与授权"
    :current-step="4"
    previous-route="booking-emergency-contact"
    next-route="booking-contract-placeholder"
    previous-label="上一步"
    next-label="我已阅读并同意上述内容"
    :next-disabled="!allAccepted || loading || submitting || !summaryReady"
    manual-next
    @next="confirmAndContinue"
  >
    <div v-loading="loading" class="review-page">
      <div class="intro">
        <h2>请仔细阅读下方内容</h2>
        <p>请核对订单摘要，并分别阅读和同意四份政策文件。</p>
      </div>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />

      <template v-if="property && pricing && selectedOption">
        <section class="summary-card property-summary">
          <div><span>房源名称</span><strong>{{ property.title }}</strong></div>
          <div><span>国家/地区</span><strong>{{ countryLabel }}</strong></div>
          <div><span>城市</span><strong>{{ property.district }}</strong></div>
          <div><span>入住日期</span><strong>{{ pricing.move_in_date }}</strong></div>
          <div><span>租期</span><strong>{{ selectedOption.months }} 个月（至 {{ selectedOption.end_date }}）</strong></div>
          <div><span>学校</span><strong>{{ personal.form.school_name || '未填写' }}</strong></div>
        </section>

        <section class="summary-card price-summary">
          <h3>费用摘要</h3>
          <div v-for="row in priceRows" :key="row.label" :class="{ due: row.due }">
            <span>{{ row.label }}</span>
            <strong>{{ money(row.value.cny) }}<small v-if="row.value.local.currency !== 'CNY'"> / {{ money(row.value.local) }}</small></strong>
          </div>
          <p>汇率仅供参考，以最终付款页面为准。</p>
        </section>

        <section class="people-grid">
          <el-card shadow="never">
            <template #header><strong>申请人信息（已脱敏）</strong></template>
            <p>姓名：{{ maskName(personal.form.chinese_name) }}</p>
            <p>手机：{{ maskPhone(personal.form.phone_country_code, personal.form.phone) }}</p>
            <p>邮箱：{{ maskEmail(personal.form.email) }}</p>
            <p>地址：{{ maskAddress(personal.form.region, personal.form.address_detail) }}</p>
          </el-card>
          <el-card shadow="never">
            <template #header><strong>紧急联系人（已脱敏）</strong></template>
            <p>姓名：{{ maskName(emergency.form.chinese_name) }}</p>
            <p>关系：{{ emergency.form.relationship || '未填写' }}</p>
            <p>手机：{{ maskPhone(emergency.form.phone_country_code, emergency.form.phone) }}</p>
            <p>邮箱：{{ maskEmail(emergency.form.email) }}</p>
            <p v-if="emergency.form.consultant_id">顾问工号：{{ emergency.form.consultant_id }}</p>
          </el-card>
        </section>

        <section class="policy-section">
          <el-alert title="以下政策正文均为待法务审核的业务模板" type="warning" :closable="false" show-icon />
          <p class="refund-notice">退订条件因国家或地区、房源、房型及价格方案而异，不承诺无条件退款或统一冷静期。</p>
          <el-checkbox v-model="selectAll" class="select-all">全选</el-checkbox>
          <el-checkbox v-for="policy in policies" :key="policy.key" v-model="accepted[policy.key]" class="policy-check">
            我已阅读并同意
            <button
              :ref="(element) => setPolicyTrigger(policy.key, element)"
              type="button"
              class="policy-link"
              :aria-haspopup="'dialog'"
              @click.stop.prevent="openPolicy(policy.key)"
            >{{ policy.title }}</button>
            <small v-if="policyDocuments[policy.key]">（版本 {{ policyDocuments[policy.key].version }}）</small>
          </el-checkbox>
        </section>
      </template>

      <PolicyDialog v-model="dialogVisible" :document="activePolicyDocument" @closed="restorePolicyFocus" />
    </div>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, type ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import PolicyDialog from '@/components/booking/PolicyDialog.vue'
import { propertyService, type LeaseOption, type LeasePricing, type MoneyAmount } from '@/services/property'
import { policyService, type PolicyDocument } from '@/services/policy'
import { useBookingPersonalInfoStore } from '@/stores/bookingPersonalInfo'
import { useBookingEmergencyContactStore } from '@/stores/bookingEmergencyContact'
import { bookingDraftService } from '@/services/bookingDraft'
import type { Property } from '@/types/property'
import { areAllPoliciesAccepted } from '@/utils/policyAcceptance'

const route = useRoute()
const router = useRouter()
const personal = useBookingPersonalInfoStore()
const emergency = useBookingEmergencyContactStore()
const propertyId = computed(() => Number(route.params.propertyId))
const property = ref<Property | null>(null)
const pricing = ref<LeasePricing | null>(null)
const selectedMonths = ref(0)
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const policies = [
  { key: 'booking-authorization', title: '《订房授权书》', path: '/booking-policies/booking-authorization' },
  { key: 'cross-border-data', title: '《个人信息出境授权声明》', path: '/booking-policies/cross-border-data' },
  { key: 'privacy', title: '《隐私政策》', path: '/booking-policies/privacy' },
  { key: 'cancellation', title: '《公寓退订政策》', path: '/booking-policies/cancellation' },
]
const accepted = reactive<Record<string, boolean>>(Object.fromEntries(policies.map((policy) => [policy.key, false])))
const policyDocuments = reactive<Record<string, PolicyDocument>>({})
const activePolicyKey = ref('')
const dialogVisible = ref(false)
const policyTriggers = new Map<string, HTMLButtonElement>()
const activePolicyDocument = computed(() => policyDocuments[activePolicyKey.value] || null)
const allAccepted = computed(() => areAllPoliciesAccepted(policies.map((policy) => policy.key), accepted))
const selectAll = computed({ get: () => allAccepted.value, set: (value: boolean) => policies.forEach((policy) => { accepted[policy.key] = value }) })
const selectedOption = computed<LeaseOption | null>(() => pricing.value?.options.find((option) => option.months === selectedMonths.value) || null)
const summaryReady = computed(() => Boolean(
  property.value && selectedOption.value && personal.form.chinese_name && emergency.form.chinese_name
  && policies.every((policy) => policyDocuments[policy.key]),
))
const countryLabels: Record<string, string> = { CN: '中国', GB: '英国', US: '美国', AU: '澳大利亚', CA: '加拿大', SG: '新加坡', JP: '日本', KR: '韩国', DE: '德国', FR: '法国' }
const countryLabel = computed(() => countryLabels[property.value?.country || ''] || property.value?.country || '未设置')
const priceRows = computed(() => selectedOption.value ? [
  { label: '月租', value: selectedOption.value.prices.monthly_rent },
  { label: '租金总额', value: selectedOption.value.prices.rent_total },
  { label: '押金', value: selectedOption.value.prices.deposit },
  { label: '服务费', value: selectedOption.value.prices.service_fee },
  { label: '当前应付金额', value: selectedOption.value.prices.amount_due_now, due: true },
] : [])

function readDraft() { try { return JSON.parse(localStorage.getItem(`booking_draft_${propertyId.value}`) || '{}') } catch { return {} } }
function money(value: MoneyAmount) { return `${value.currency} ${value.decimal}` }
function maskName(value: string) { return value ? `${value.slice(0, 1)}${'*'.repeat(Math.max(1, value.length - 1))}` : '未填写' }
function maskPhone(code: string, value: string) { return value.length >= 7 ? `${code} ${value.slice(0, 3)}****${value.slice(-4)}` : '未填写' }
function maskEmail(value: string) { const [name, domain] = value.split('@'); return name && domain ? `${name.slice(0, 1)}***@${domain}` : '未填写' }
function maskAddress(region: string, address: string) { return region && address ? `${region} ${address.slice(0, 2)}***` : '未填写' }
function setPolicyTrigger(key: string, element: Element | ComponentPublicInstance | null) {
  if (element instanceof HTMLButtonElement) policyTriggers.set(key, element)
}
function openPolicy(key: string) {
  if (!policyDocuments[key]) return
  activePolicyKey.value = key
  dialogVisible.value = true
}
async function restorePolicyFocus() {
  await nextTick()
  policyTriggers.get(activePolicyKey.value)?.focus()
}

async function confirmAndContinue() {
  if (!allAccepted.value || !pricing.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await policyService.confirmBooking({
      property_id: propertyId.value,
      move_in_date: pricing.value.move_in_date,
      lease_months: selectedMonths.value,
      policy_acceptances: policies.map((policy) => ({
        key: policy.key,
        version: policyDocuments[policy.key].version,
        content_hash: policyDocuments[policy.key].content_hash,
      })),
    })
    const draft = readDraft()
    localStorage.setItem(`booking_draft_${propertyId.value}`, JSON.stringify({ ...draft, booking_id: result.booking_id }))
    router.push({ name: 'booking-contract-placeholder', params: { propertyId: String(propertyId.value) }, query: { booking_id: String(result.booking_id) } })
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || '订单确认失败，请检查信息后重试'
  } finally { submitting.value = false }
}

onMounted(async () => {
  loading.value = true
  try {
    const serverDraft = await bookingDraftService.get(propertyId.value)
    if (!serverDraft.move_in_date || !serverDraft.lease_months || !serverDraft.personal_info || !serverDraft.emergency_contact || serverDraft.current_step !== 'review') {
      router.replace({ name: 'booking-emergency-contact', params: { propertyId: String(propertyId.value) } })
      return
    }
    Object.assign(personal.form, serverDraft.personal_info)
    Object.assign(emergency.form, serverDraft.emergency_contact)
    const [propertyResult, pricingResult, ...documents] = await Promise.all([
      propertyService.getById(propertyId.value),
      propertyService.getLeasePricing(propertyId.value, serverDraft.move_in_date),
      ...policies.map((policy) => policyService.get(policy.key)),
    ])
    property.value = propertyResult
    pricing.value = pricingResult
    documents.forEach((document) => { policyDocuments[document.key] = document })
    selectedMonths.value = Number(serverDraft.lease_months)
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || '无法加载订单摘要'
  } finally { loading.value = false }
})
</script>

<style scoped>
.review-page { display: grid; gap: 18px; }
.intro h2 { margin: 0 0 6px; font-size: 24px; }.intro p { margin: 0; color: var(--text-muted); }
.summary-card { padding: 22px 28px; border-radius: var(--radius); }.property-summary { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px 28px; background: #f6f7fa; }
.summary-card div { display: flex; justify-content: space-between; gap: 12px; }.summary-card span { color: var(--text-muted); }
.price-summary { display: grid; gap: 12px; background: #edf8fa; }.price-summary h3 { margin: 0 0 6px; }.price-summary small { color: var(--text-muted); }.price-summary .due { padding-top: 12px; border-top: 1px solid #cfe3e7; font-size: 17px; }.price-summary p { margin: 0; color: var(--text-muted); font-size: 12px; }
.people-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }.people-grid p { color: var(--text-secondary); }
.policy-section { display: grid; gap: 12px; padding-top: 8px; }.refund-notice { margin: 0; padding: 14px; border-radius: var(--radius-sm); background: #f6f7fa; line-height: 1.6; }.select-all { padding-bottom: 10px; border-bottom: 1px solid var(--border-light); font-weight: 700; }.policy-check { margin-right: 0; }.policy-link { padding: 0; border: 0; background: none; color: var(--primary); font: inherit; cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }.policy-link:focus-visible { outline: 2px solid var(--primary); outline-offset: 3px; border-radius: 2px; }
@media (max-width: 700px) { .property-summary, .people-grid { grid-template-columns: 1fr; } }
</style>
