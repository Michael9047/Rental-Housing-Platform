<template>
  <div class="booking-confirm-page">
    <!-- Header -->
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>预约看房</h2>
    </div>

    <el-row :gutter="24">
      <!-- Left: Booking Form -->
      <el-col :span="16">
        <el-card shadow="never" class="step-card">
          <template #header><span class="card-title">📅 预约看房信息</span></template>

          <div class="prefill-info" v-if="prefillDate">
            <el-tag type="success" effect="plain" size="large" round>
              已选：{{ prefillDate }} {{ slotLabel }}
            </el-tag>
          </div>

          <el-form ref="formRef" :model="bookingForm" :rules="rules" label-width="100px" label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="📅 看房日期" prop="scheduled_date">
                  <el-date-picker
                    v-model="bookingForm.scheduled_date"
                    type="date"
                    placeholder="选择日期"
                    value-format="YYYY-MM-DD"
                    :disabled-date="disabledDate"
                    style="width:100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="🕐 时间段" prop="time_slot">
                  <el-select v-model="bookingForm.time_slot" placeholder="选择时间段" style="width:100%">
                    <el-option label="🌅 上午 9:00-12:00" value="morning" />
                    <el-option label="☀️ 下午 14:00-17:00" value="afternoon" />
                    <el-option label="🌙 晚间 19:00-21:00" value="evening" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="👤 姓名" prop="contact_name">
                  <el-input v-model="bookingForm.contact_name" placeholder="请输入姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="📱 手机号" prop="contact_phone">
                  <el-input v-model="bookingForm.contact_phone" placeholder="请输入手机号" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="💬 给房东留言（选填）">
              <el-input
                v-model="bookingForm.message"
                type="textarea"
                :rows="3"
                placeholder="可备注签证咨询、长短租需求、校车接送等"
              />
            </el-form-item>

            <div class="form-footer">
              <el-button @click="$router.back()">取消</el-button>
              <el-button type="primary" size="large" :loading="submitting" @click="submitBooking">
                提交预约
              </el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>

      <!-- Right: Property Summary -->
      <el-col :span="8">
        <el-card shadow="never" class="summary-card">
          <template #header><span class="card-title">🏠 房源信息</span></template>

          <div class="summary-property" v-if="propertyInfo">
            <div class="summary-img" v-if="primaryImage">
              <img :src="primaryImage" :alt="propertyInfo.title" />
            </div>
            <h3 class="summary-title">{{ propertyInfo.title }}</h3>
            <p class="summary-addr">{{ propertyInfo.address }}</p>
            <div class="summary-tags">
              <el-tag size="small">{{ propertyInfo.bedrooms }}室{{ propertyInfo.bathrooms }}卫</el-tag>
              <el-tag size="small" type="info">{{ propertyInfo.property_type }}</el-tag>
              <el-tag size="small">{{ propertyInfo.district }}</el-tag>
            </div>

            <el-divider />
            <div class="mini-fees">
              <div class="mini-row"><span>月租</span><span>¥{{ propertyInfo?.price_monthly || 0 }}</span></div>
              <div class="mini-row"><span>押金</span><span>¥{{ propertyInfo?.deposit_amount || propertyInfo?.price_monthly || 0 }}</span></div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { bookingService } from '@/services/booking'

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()

const submitting = ref(false)
const formRef = ref<FormInstance>()

// Prefill from dialog
const prefillDate = (route.query.date as string) || ''
const prefillSlot = (route.query.slot as string) || ''
const propertyId = Number(route.query.property_id) || 0

const slotLabels: Record<string, string> = {
  morning: '上午 9:00-12:00',
  afternoon: '下午 14:00-17:00',
  evening: '晚间 19:00-21:00',
}
const slotLabel = computed(() => slotLabels[prefillSlot] || '')

// Property info
const propertyInfo = ref<any>(null)
const primaryImage = computed(() => {
  const imgs = propertyInfo.value?.images
  if (!imgs?.length) return null
  const p = imgs.find((i: any) => i.is_primary) || imgs[0]
  return `/api/v1/uploads/${p.filename}`
})

// Disable past dates
function disabledDate(date: Date): boolean {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date < today
}

// Form
const bookingForm = reactive({
  scheduled_date: prefillDate,
  time_slot: prefillSlot,
  contact_name: '',
  contact_phone: '',
  message: '',
})

const rules: FormRules = {
  contact_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  contact_phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
  ],
}

async function submitBooking() {
  if (!formRef.value) return
  if (!propertyId || propertyId <= 0) {
    ElMessage.error('房源信息异常，请从房源详情页重新进入')
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const timeSlotLabel = slotLabels[bookingForm.time_slot] || ''
    const fullMessage = [
      timeSlotLabel ? `【看房时段：${timeSlotLabel}】` : '',
      bookingForm.message || '',
    ].filter(Boolean).join('\n')
    await bookingService.create({
      property_id: propertyId,
      message: fullMessage || undefined,
      scheduled_date: bookingForm.scheduled_date || undefined,
    })
    ElMessage.success('预约已提交成功，可在个人中心「我的预订」查看')
    // 跳转到个人中心预订列表
    setTimeout(() => router.push('/profile?tab=bookings'), 1500)
  } catch (err: any) {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    if (status === 409) {
      ElMessage.warning('您已对该房源发起过预约')
    } else if (status === 403) {
      ElMessage.error('仅租客身份可预约看房，请切换为租客账号')
    } else if (status === 401) {
      ElMessage.error('请先登录后再预约')
    } else if (status === 404) {
      ElMessage.error('房源不存在或已下架')
    } else if (detail && typeof detail === 'string') {
      ElMessage.error(detail)
    } else {
      ElMessage.error('预约提交失败，请重试')
    }
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (propertyId) {
    try {
      propertyInfo.value = await propertyStore.fetchById(propertyId)
    } catch {
      // handle
    }
  }
})
</script>

<style scoped>
.booking-confirm-page {
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  margin: 0;
}

/* ── Step Card ─────────────────────── */

.step-card {
  border-radius: var(--radius) !important;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.prefill-info {
  margin-bottom: 16px;
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

/* ── Summary Card ──────────────────── */

.summary-card {
  border-radius: var(--radius) !important;
  position: sticky;
  top: 80px;
}

.summary-img {
  height: 160px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  margin-bottom: 12px;
}

.summary-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.summary-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.summary-addr {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.summary-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.mini-fees {
  font-size: 14px;
}

.mini-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  color: var(--text-secondary);
}

.mini-row.total {
  font-weight: 700;
  color: var(--text-primary);
}

.mini-total {
  font-size: 18px;
  color: var(--danger);
  font-weight: 700;
}
</style>
