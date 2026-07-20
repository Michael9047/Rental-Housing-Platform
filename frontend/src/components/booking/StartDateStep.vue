<template>
  <el-card shadow="never" class="step-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">📅 选择起租日</span>
        <span class="card-subtitle">请选择您希望入住的日期</span>
      </div>
    </template>

    <div class="date-picker-section">
      <div class="picker-wrapper">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="请选择起租日期"
          :disabled-date="disabledDate"
          value-format="YYYY-MM-DD"
          size="large"
          style="width: 100%"
          :clearable="false"
        />
      </div>

      <div class="calendar-display">
        <div class="calendar-header">
          <el-select v-model="viewYear" size="large" class="year-select" @change="updateCalendar">
            <el-option
              v-for="y in yearOptions"
              :key="y"
              :label="y + '年'"
              :value="y"
            />
          </el-select>
          <el-select v-model="viewMonth" size="large" class="month-select" @change="updateCalendar">
            <el-option
              v-for="m in 12"
              :key="m"
              :label="m + '月'"
              :value="m"
            />
          </el-select>
          <div class="header-actions">
            <el-button text @click="prevMonth">上个月</el-button>
            <el-button text @click="goToday">今天</el-button>
            <el-button text @click="nextMonth">下个月</el-button>
          </div>
        </div>

        <div class="calendar-weekdays">
          <div v-for="d in weekdays" :key="d" class="weekday">{{ d }}</div>
        </div>

        <div class="calendar-days">
          <div
            v-for="(day, idx) in calendarDays"
            :key="idx"
            class="day-cell"
            :class="{
              'other-month': !day.currentMonth,
              'is-today': day.isToday,
              'is-selected': day.isSelected,
              'is-disabled': day.isDisabled,
            }"
            @click="selectDay(day)"
          >
            {{ day.date.getDate() }}
          </div>
        </div>
      </div>

      <div class="selected-info" v-if="bookingFlow.start_date">
        <el-tag type="success" effect="plain" size="large" round>
          已选起租日：{{ bookingFlow.start_date }}
        </el-tag>
      </div>
    </div>

    <div class="step-footer">
      <el-button type="primary" size="large" :disabled="!bookingFlow.start_date" @click="handleNext">
        下一步：选择租期 →
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useBookingFlowStore } from '@/stores/bookingFlow'

const emit = defineEmits<{
  (e: 'next'): void
}>()

const bookingFlow = useBookingFlowStore()

const weekdays = ['日', '一', '二', '三', '四', '五', '六']

const today = new Date()
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth() + 1)

const selectedDate = ref<string>(bookingFlow.start_date || '')

const yearOptions = computed(() => {
  const years: number[] = []
  const currentYear = today.getFullYear()
  for (let y = currentYear; y <= currentYear + 5; y++) {
    years.push(y)
  }
  return years
})

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  )
}

function isPastDay(d: Date): boolean {
  const t = new Date()
  t.setHours(0, 0, 0, 0)
  return d < t
}

function disabledDate(d: Date): boolean {
  return isPastDay(d)
}

const calendarDays = computed(() => {
  const year = viewYear.value
  const month = viewMonth.value - 1
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const startWeekday = firstDay.getDay()
  const daysInMonth = lastDay.getDate()

  const days: {
    date: Date
    currentMonth: boolean
    isToday: boolean
    isSelected: boolean
    isDisabled: boolean
  }[] = []

  const prevMonthLastDay = new Date(year, month, 0).getDate()
  for (let i = startWeekday - 1; i >= 0; i--) {
    const d = new Date(year, month - 1, prevMonthLastDay - i)
    days.push({
      date: d,
      currentMonth: false,
      isToday: isSameDay(d, today),
      isSelected: selectedDate.value ? isSameDay(d, new Date(selectedDate.value)) : false,
      isDisabled: isPastDay(d),
    })
  }

  for (let i = 1; i <= daysInMonth; i++) {
    const d = new Date(year, month, i)
    days.push({
      date: d,
      currentMonth: true,
      isToday: isSameDay(d, today),
      isSelected: selectedDate.value ? isSameDay(d, new Date(selectedDate.value)) : false,
      isDisabled: isPastDay(d),
    })
  }

  const remaining = 42 - days.length
  for (let i = 1; i <= remaining; i++) {
    const d = new Date(year, month + 1, i)
    days.push({
      date: d,
      currentMonth: false,
      isToday: isSameDay(d, today),
      isSelected: selectedDate.value ? isSameDay(d, new Date(selectedDate.value)) : false,
      isDisabled: isPastDay(d),
    })
  }

  return days
})

function selectDay(day: { date: Date; isDisabled: boolean }) {
  if (day.isDisabled) return
  const d = day.date
  selectedDate.value = formatDate(d)
  bookingFlow.setStartDate(selectedDate.value)
}

function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function prevMonth() {
  if (viewMonth.value === 1) {
    if (viewYear.value > today.getFullYear()) {
      viewYear.value--
      viewMonth.value = 12
    }
  } else {
    viewMonth.value--
  }
}

function nextMonth() {
  if (viewMonth.value === 12) {
    if (viewYear.value < today.getFullYear() + 5) {
      viewYear.value++
      viewMonth.value = 1
    }
  } else {
    viewMonth.value++
  }
}

function goToday() {
  viewYear.value = today.getFullYear()
  viewMonth.value = today.getMonth() + 1
}

function updateCalendar() {
  // just triggers recompute
}

function handleNext() {
  if (!bookingFlow.start_date) return
  emit('next')
}

onMounted(() => {
  if (bookingFlow.start_date) {
    const d = new Date(bookingFlow.start_date)
    viewYear.value = d.getFullYear()
    viewMonth.value = d.getMonth() + 1
  }
})
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

.date-picker-section {
  margin-bottom: 24px;
}

.picker-wrapper {
  margin-bottom: 16px;
}

.calendar-display {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
}

.calendar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-light);
}

.year-select {
  width: 120px;
}

.month-select {
  width: 100px;
}

.header-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  margin-bottom: 8px;
}

.weekday {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 6px 0;
}

.calendar-days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.day-cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-primary);
}

.day-cell:hover:not(.is-disabled) {
  background: var(--primary-light);
  color: var(--primary);
}

.day-cell.other-month {
  color: var(--border);
}

.day-cell.is-today {
  color: var(--primary);
  font-weight: 600;
}

.day-cell.is-selected {
  background: var(--primary);
  color: #fff;
  font-weight: 700;
}

.day-cell.is-disabled {
  color: var(--border);
  cursor: not-allowed;
  pointer-events: none;
}

.selected-info {
  margin-top: 16px;
  text-align: center;
}

.step-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid var(--border-light);
}
</style>
