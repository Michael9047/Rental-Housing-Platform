<template>
  <el-dialog
    v-model="visible"
    title="📅 预约看房"
    width="460px"
    :close-on-click-modal="false"
    class="booking-date-dialog"
  >
    <div class="dialog-body">
      <!-- Property Summary -->
      <div class="property-summary" v-if="propertyTitle">
        <span class="summary-label">房源：</span>
        <span class="summary-value">{{ propertyTitle }}</span>
        <span class="summary-price" v-if="propertyPrice">¥{{ propertyPrice }}/月</span>
      </div>

      <!-- Date Picker -->
      <div class="form-section">
        <label class="form-label">📅 选择看房日期</label>
        <el-calendar v-model="selectedDate" class="booking-calendar">
          <template #date-cell="{ data }">
            <div
              class="calendar-day"
              :class="{
                selected: isSameDay(data.date, selectedDate),
                past: isPastDay(data.date),
              }"
              @click="onDayClick(data.date)"
            >
              {{ data.date.getDate() }}
            </div>
          </template>
        </el-calendar>
      </div>

      <!-- Time Slot -->
      <div class="form-section">
        <label class="form-label">🕐 选择时间段</label>
        <div class="time-slots">
          <div
            v-for="slot in timeSlots"
            :key="slot.value"
            class="time-slot"
            :class="{ active: selectedSlot === slot.value }"
            @click="selectedSlot = slot.value"
          >
            <span class="slot-icon">{{ slot.icon }}</span>
            <span class="slot-text">{{ slot.label }}</span>
            <span class="slot-time">{{ slot.time }}</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel" :disabled="submitting">取消</el-button>
        <el-button
          type="primary"
          @click="handleConfirm"
          :loading="submitting"
          :disabled="!canConfirm"
        >
          下一步：填写预订信息 →
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  propertyId: number
  propertyTitle?: string
  propertyPrice?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm', data: { propertyId: number; date: string; slot: string }): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const _selectedDate = ref(new Date())
const selectedSlot = ref('')
const submitting = ref(false)

// 用 computed 拦截：区分「月份切换」和「日期选中」
// 月份切换 → 允许（即使那天在过去）；同一月份内选日期 → 拦截过去
const selectedDate = computed({
  get: () => _selectedDate.value,
  set: (val: Date) => {
    const old = _selectedDate.value
    const monthChanged = val.getFullYear() !== old.getFullYear() || val.getMonth() !== old.getMonth()
    if (monthChanged) {
      // 切换月份：允许，把选中日期设为该月1号，避免触发过去日期拦截
      if (isPastDay(val)) {
        // 如果切换到的月份里的日期是过去，设为该月1号（只是显示月份，不选中具体日）
        _selectedDate.value = new Date(val.getFullYear(), val.getMonth(), 1)
      } else {
        _selectedDate.value = val
      }
    } else {
      // 同一月份内选具体日期：只允许今天及未来
      if (!isPastDay(val)) {
        _selectedDate.value = val
      }
    }
  },
})

const timeSlots = [
  { value: 'morning', label: '上午', time: '9:00 - 12:00', icon: '🌅' },
  { value: 'afternoon', label: '下午', time: '14:00 - 17:00', icon: '☀️' },
  { value: 'evening', label: '晚间', time: '19:00 - 21:00', icon: '🌙' },
]

const canConfirm = computed(() => selectedDate.value && selectedSlot.value)

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  )
}

function isPastDay(d: Date): boolean {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return d < today
}

function onDayClick(date: Date) {
  if (isPastDay(date)) return
  selectedDate.value = date
}

function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function handleConfirm() {
  if (!canConfirm.value) return
  if (isPastDay(selectedDate.value)) return
  submitting.value = true
  // Simulate brief loading for UX
  await new Promise((r) => setTimeout(r, 300))
  emit('confirm', {
    propertyId: props.propertyId,
    date: formatDate(selectedDate.value),
    slot: selectedSlot.value,
  })
  submitting.value = false
}

function handleCancel() {
  visible.value = false
}

// Reset on open
watch(visible, (v) => {
  if (v) {
    _selectedDate.value = new Date()
    selectedSlot.value = ''
  }
})
</script>

<style scoped>
.property-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--primary-light);
  border-radius: var(--radius-sm);
  margin-bottom: 20px;
  font-size: 14px;
}

.summary-label {
  color: var(--text-secondary);
}

.summary-value {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.summary-price {
  color: var(--danger);
  font-weight: 700;
  font-size: 15px;
}

.form-section {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.booking-calendar {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.calendar-day {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.calendar-day:hover {
  background: var(--primary-light);
  color: var(--primary);
}

.calendar-day.selected {
  background: var(--primary);
  color: #fff;
  font-weight: 700;
}

.calendar-day.past {
  color: var(--border);
  cursor: not-allowed;
  pointer-events: none;
}

.time-slots {
  display: flex;
  gap: 12px;
}

.time-slot {
  flex: 1;
  padding: 14px 12px;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.time-slot:hover {
  border-color: var(--primary);
  background: var(--primary-light);
}

.time-slot.active {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.15);
}

.slot-icon {
  font-size: 22px;
}

.slot-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.slot-time {
  font-size: 12px;
  color: var(--text-muted);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
