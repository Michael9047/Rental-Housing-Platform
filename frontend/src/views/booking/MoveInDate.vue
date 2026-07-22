<!-- 预订流程第一步：按房源所在地时区选择有效入住日期。 -->
<template>
  <BookingFlowLayout
    title="选择入住日期"
    :current-step="0"
    next-route="booking-lease-term"
    :next-disabled="!isSelectionValid"
    :manual-next="true"
    @next="handleNext"
  >
    <div v-loading="loading" class="date-page">
      <div class="date-toolbar">
        <el-select v-model="viewYear" aria-label="选择年份" @change="handleMonthChange">
          <el-option v-for="year in yearOptions" :key="year" :label="`${year} 年`" :value="year" />
        </el-select>
        <el-select v-model="viewMonth" aria-label="选择月份" @change="handleMonthChange">
          <el-option v-for="month in 12" :key="month" :label="`${month} 月`" :value="month" />
        </el-select>
      </div>

      <el-alert
        :title="`日期按房源所在地时区 ${timezone} 计算`"
        type="info"
        :closable="false"
        show-icon
      />

      <div class="calendar">
        <div v-for="weekday in weekdays" :key="weekday" class="weekday">{{ weekday }}</div>
        <button
          v-for="day in calendarDays"
          :key="day.key"
          type="button"
          class="day"
          :class="{ outside: !day.inMonth, selected: day.iso === selectedDate }"
          :disabled="day.disabled"
          :aria-label="day.iso"
          @click="selectDate(day.iso)"
        >
          {{ day.day }}
        </button>
      </div>

      <div class="legend">
        <span><i class="legend-dot unavailable" />不可入住</span>
        <span><i class="legend-dot selected-dot" />已选择</span>
      </div>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" />

      <div class="selected-date">
        <span>选中的入住日期</span>
        <strong>{{ selectedDate || '尚未选择' }}</strong>
      </div>
    </div>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import { propertyService, type BookingDateAvailability } from '@/services/property'
import { bookingDraftService } from '@/services/bookingDraft'
import { extractErrorMessage } from '@/services/api'

const route = useRoute()
const router = useRouter()
const propertyId = computed(() => Number(route.params.propertyId))
const weekdays = ['日', '一', '二', '三', '四', '五', '六']
const loading = ref(false)
const timezone = ref('UTC')
const localToday = ref('')
const availableFrom = ref<string | null>(null)
const blockedDates = ref(new Set<string>())
const selectedDate = ref('')
const isSelectionValid = ref(false)
const errorMessage = ref('')

const initialDate = new Date()
const viewYear = ref(initialDate.getUTCFullYear())
const viewMonth = ref(initialDate.getUTCMonth() + 1)
const yearOptions = computed(() => Array.from({ length: 6 }, (_, index) => Number(localToday.value.slice(0, 4) || viewYear.value) + index))

const calendarDays = computed(() => {
  const firstWeekday = new Date(Date.UTC(viewYear.value, viewMonth.value - 1, 1)).getUTCDay()
  const daysInMonth = new Date(Date.UTC(viewYear.value, viewMonth.value, 0)).getUTCDate()
  const cells: Array<{ key: string; day: number | string; iso: string; inMonth: boolean; disabled: boolean }> = []
  for (let index = 0; index < firstWeekday; index += 1) {
    cells.push({ key: `empty-${index}`, day: '', iso: '', inMonth: false, disabled: true })
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const iso = `${viewYear.value}-${String(viewMonth.value).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const disabled = !localToday.value || iso < localToday.value || Boolean(availableFrom.value && iso < availableFrom.value) || blockedDates.value.has(iso)
    cells.push({ key: iso, day, iso, inMonth: true, disabled })
  }
  return cells
})

function draftKey() {
  return `booking_draft_${propertyId.value}`
}

function saveDraft() {
  localStorage.setItem(draftKey(), JSON.stringify({
    property_id: propertyId.value,
    move_in_date: selectedDate.value,
    timezone: timezone.value,
  }))
}

function loadDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey()) || '{}')
    if (draft.property_id === propertyId.value && typeof draft.move_in_date === 'string') {
      selectedDate.value = draft.move_in_date
      const [year, month] = draft.move_in_date.split('-').map(Number)
      if (year && month) {
        viewYear.value = year
        viewMonth.value = month
      }
    }
  } catch {
    localStorage.removeItem(draftKey())
  }
}

async function loadAvailability() {
  if (!propertyId.value) {
    errorMessage.value = '房源信息无效'
    return
  }
  loading.value = true
  errorMessage.value = ''
  isSelectionValid.value = false
  try {
    const result: BookingDateAvailability = await propertyService.getBookingDateAvailability(propertyId.value, viewYear.value, viewMonth.value)
    timezone.value = result.timezone
    localToday.value = result.local_today
    availableFrom.value = result.available_from
    blockedDates.value = new Set(result.blocked_dates)
    if (selectedDate.value) await validateSelection(selectedDate.value)
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || '无法加载房源可入住日期'
  } finally {
    loading.value = false
  }
}

async function validateSelection(iso: string) {
  isSelectionValid.value = false
  errorMessage.value = ''
  if (!iso || iso < localToday.value || Boolean(availableFrom.value && iso < availableFrom.value) || blockedDates.value.has(iso)) {
    errorMessage.value = '请选择有效且可入住的日期'
    return
  }
  try {
    const result = await propertyService.validateBookingDate(propertyId.value, iso)
    isSelectionValid.value = result.available
    if (!result.available) errorMessage.value = result.reason || '该日期不可入住'
    return result.available
  } catch (error: any) {
    if (!error?.response) {
      errorMessage.value = '暂时无法连接服务器，请稍后重试'
    } else if (error.response.status === 401) {
      errorMessage.value = '登录状态已失效，请重新登录后再试'
    } else {
      errorMessage.value = extractErrorMessage(error) || '日期校验暂时失败，请稍后重试'
    }
    return false
  }
}

function selectDate(iso: string) {
  selectedDate.value = iso
  errorMessage.value = ''
  isSelectionValid.value = true
}

async function handleNext() {
  if (loading.value || !selectedDate.value) return
  loading.value = true
  try {
    if (!await validateSelection(selectedDate.value)) return
    try {
      await bookingDraftService.save(propertyId.value, {
        move_in_date: selectedDate.value,
        current_step: 'lease_term',
      })
    } catch (error: any) {
      if (!error?.response) {
        errorMessage.value = '暂时无法连接服务器，请稍后重试'
      } else if (error.response.status === 401) {
        errorMessage.value = '登录状态已失效，请重新登录后再试'
      } else {
        errorMessage.value = extractErrorMessage(error) || '入住日期草稿保存失败，请稍后重试'
      }
      return
    }
    saveDraft()
    await router.push({
      name: 'booking-lease-term',
      params: { propertyId: String(propertyId.value) },
    })
  } finally {
    loading.value = false
  }
}

function handleMonthChange() {
  selectedDate.value = ''
  isSelectionValid.value = false
  loadAvailability()
}

onMounted(async () => {
  loadDraft()
  if (!selectedDate.value) {
    try {
      const serverDraft = await bookingDraftService.get(propertyId.value)
      if (serverDraft.move_in_date) {
        selectedDate.value = serverDraft.move_in_date
        const [year, month] = serverDraft.move_in_date.split('-').map(Number)
        viewYear.value = year
        viewMonth.value = month
      }
    } catch { /* 尚未创建服务端草稿 */ }
  }
  await loadAvailability()
})
</script>

<style scoped>
.date-page { display: grid; gap: 20px; }
.date-toolbar { display: flex; gap: 12px; }
.date-toolbar :deep(.el-select) { width: 160px; }
.calendar { display: grid; grid-template-columns: repeat(7, minmax(42px, 1fr)); gap: 8px; }
.weekday { padding: 8px; text-align: center; color: var(--text-muted); font-size: 13px; }
.day { min-height: 48px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: #fff; cursor: pointer; }
.day:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.day:disabled { background: #f2f3f5; color: #b7bbc2; cursor: not-allowed; text-decoration: line-through; }
.day.outside { visibility: hidden; }
.day.selected { border-color: var(--primary); background: var(--primary); color: #fff; font-weight: 700; }
.legend { display: flex; gap: 20px; color: var(--text-muted); font-size: 13px; }
.legend span { display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.unavailable { background: #dcdfe6; }
.selected-dot { background: var(--primary); }
.selected-date { display: flex; justify-content: space-between; padding: 16px 20px; border-radius: var(--radius); background: #fff; }
.selected-date strong { color: var(--primary); }
@media (max-width: 600px) {
  .date-toolbar { flex-direction: column; }
  .date-toolbar :deep(.el-select) { width: 100%; }
  .calendar { gap: 4px; }
  .day { min-height: 40px; }
}
</style>
