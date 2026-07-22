<!-- 预订流程第二步：展示服务端生成的租期选项和价格试算。 -->
<template>
  <BookingFlowLayout
    title="选择租期"
    :current-step="1"
    previous-route="booking-move-in-date"
    next-route="booking-personal-info"
    :next-disabled="!selectedOption"
  >
    <div v-loading="loading" class="lease-page">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />

      <template v-if="pricing">
        <div class="date-summary">
          <span>入住日期</span>
          <strong>{{ pricing.move_in_date }}</strong>
        </div>

        <div class="lease-options">
          <button
            v-for="option in pricing.options"
            :key="option.months"
            type="button"
            class="lease-option"
            :class="{ selected: selectedMonths === option.months }"
            @click="selectOption(option)"
          >
            <strong>{{ option.months }} 个月</strong>
            <span>至 {{ option.end_date }}</span>
          </button>
        </div>

        <el-empty v-if="pricing.options.length === 0" description="当前入住日期没有可选租期" />

        <el-card v-if="selectedOption" shadow="never" class="price-card">
          <template #header><strong>价格明细</strong></template>
          <div v-for="row in priceRows" :key="row.label" class="price-row" :class="{ total: row.total }">
            <span>{{ row.label }}</span>
            <div class="amounts">
              <strong>{{ money(row.value.cny) }}</strong>
              <span v-if="row.value.local.currency !== 'CNY'">{{ money(row.value.local) }}</span>
            </div>
          </div>
        </el-card>

        <el-alert
          :title="`参考汇率：1 ${pricing.local_currency} = ${pricing.exchange_rate_to_cny} CNY`"
          :description="`${pricing.exchange_rate_source} · ${formatRateTime(pricing.exchange_rate_at)}。汇率仅供参考，以最终付款页面为准。`"
          type="warning"
          :closable="false"
          show-icon
        />
      </template>
    </div>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import { propertyService, type LeaseOption, type LeasePricing, type MoneyAmount } from '@/services/property'
import { bookingDraftService } from '@/services/bookingDraft'

const route = useRoute()
const propertyId = computed(() => Number(route.params.propertyId))
const loading = ref(false)
const errorMessage = ref('')
const pricing = ref<LeasePricing | null>(null)
const selectedMonths = ref<number | null>(null)
const selectedOption = computed(() => pricing.value?.options.find((option) => option.months === selectedMonths.value) || null)
const priceRows = computed(() => selectedOption.value ? [
  { label: '月租', value: selectedOption.value.prices.monthly_rent },
  { label: '租金总额', value: selectedOption.value.prices.rent_total },
  { label: '押金', value: selectedOption.value.prices.deposit },
  { label: '服务费', value: selectedOption.value.prices.service_fee },
  { label: '当前应付金额', value: selectedOption.value.prices.amount_due_now, total: true },
] : [])

function draftKey() {
  return `booking_draft_${propertyId.value}`
}

function readDraft(): Record<string, any> {
  try {
    return JSON.parse(localStorage.getItem(draftKey()) || '{}')
  } catch {
    return {}
  }
}

async function selectOption(option: LeaseOption) {
  if (!pricing.value) return
  try {
    await bookingDraftService.save(propertyId.value, {
      move_in_date: pricing.value.move_in_date,
      lease_months: option.months,
      current_step: 'personal_info',
    })
    selectedMonths.value = option.months
    const draft = readDraft()
    localStorage.setItem(draftKey(), JSON.stringify({
      property_id: propertyId.value,
      move_in_date: pricing.value.move_in_date,
      timezone: draft.timezone,
      lease_months: option.months,
      lease_end_date: option.end_date,
      exchange_rate_to_cny: pricing.value.exchange_rate_to_cny,
      exchange_rate_at: pricing.value.exchange_rate_at,
      exchange_rate_source: pricing.value.exchange_rate_source,
      local_currency: pricing.value.local_currency,
    }))
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || '无法保存租期草稿'
  }
}

function money(value: MoneyAmount) {
  return `${value.currency} ${value.decimal}`
}

function formatRateTime(value: string) {
  return new Date(value).toLocaleString('zh-CN')
}

onMounted(async () => {
  let draft = readDraft()
  try {
    const serverDraft = await bookingDraftService.get(propertyId.value)
    draft = { ...draft, move_in_date: serverDraft.move_in_date, lease_months: serverDraft.lease_months }
  } catch { /* 使用非敏感本地草稿回退 */ }
  if (!draft.move_in_date) {
    errorMessage.value = '请先选择有效的入住日期'
    return
  }
  try {
    const dateValidation = await propertyService.validateBookingDate(propertyId.value, draft.move_in_date)
    if (!dateValidation.available) {
      errorMessage.value = dateValidation.reason || '入住日期已失效，请重新选择'
      return
    }
  } catch {
    errorMessage.value = '入住日期已失效，请重新选择'
    return
  }
  loading.value = true
  try {
    pricing.value = await propertyService.getLeasePricing(propertyId.value, draft.move_in_date)
    if (pricing.value.options.some((option) => option.months === draft.lease_months)) {
      selectedMonths.value = draft.lease_months
    }
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || '无法加载租期和价格'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.lease-page { display: grid; gap: 20px; }
.date-summary { display: flex; justify-content: space-between; padding: 14px 18px; background: #fff; border-radius: var(--radius); }
.lease-options { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.lease-option { display: grid; gap: 8px; padding: 20px; border: 2px solid var(--border); border-radius: var(--radius); background: #fff; cursor: pointer; text-align: left; }
.lease-option span { color: var(--text-muted); font-size: 13px; }
.lease-option:hover, .lease-option.selected { border-color: var(--primary); }
.lease-option.selected { background: var(--primary-light); }
.price-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border-light); }
.price-row:last-child { border-bottom: 0; }
.amounts { display: grid; justify-items: end; gap: 3px; }
.amounts span { color: var(--text-muted); font-size: 13px; }
.price-row.total { color: var(--primary); font-size: 17px; }
</style>
