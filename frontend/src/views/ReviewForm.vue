<template>
  <div class="review-form-page" v-loading="loading">
    <div class="form-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h1>写评价</h1>
    </div>

    <el-card v-if="property" shadow="never" class="property-info-card">
      <div class="property-summary">
        <h3>{{ property.title }}</h3>
        <p>{{ property.district }} · {{ property.address }}</p>
        <el-tag v-if="property.institute_id" type="info">公寓机构</el-tag>
        <el-tag v-else type="warning">个人房东</el-tag>
      </div>
    </el-card>

    <!-- 表单 -->
    <el-card shadow="never" class="form-card">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        label-position="top"
      >
        <!-- 选择 Booking -->
        <el-form-item label="关联租赁" prop="booking_id">
          <el-select v-model="form.booking_id" placeholder="选择已确认的租赁记录" style="width: 100%">
            <el-option
              v-for="b in availableBookings"
              :key="b.id"
              :label="`#${b.id} — ${b.property_title || '房源' + b.property_id}`"
              :value="b.id"
            />
          </el-select>
          <span v-if="availableBookings.length === 0" class="no-data-hint">
            暂无可用于评价的租赁记录（需要已确认或已完成的 booking）
          </span>
        </el-form-item>

        <!-- 房源评分 -->
        <el-divider content-position="left">🏠 房源评价</el-divider>

        <el-form-item label="房源评分" prop="property_rating">
          <el-rate v-model="form.property_rating" show-score />
        </el-form-item>

        <el-form-item label="文字评价" prop="property_comment">
          <el-input
            v-model="form.property_comment"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="描述一下房子的实际情况、优缺点等..."
          />
        </el-form-item>

        <!-- 房东评分（仅个人房东时显示） -->
        <template v-if="!isInstitute">
          <el-divider content-position="left">👤 房东评价</el-divider>

          <el-form-item label="房东评分" prop="landlord_rating">
            <el-rate v-model="form.landlord_rating" show-score />
          </el-form-item>

          <el-form-item label="文字评价" prop="landlord_comment">
            <el-input
              v-model="form.landlord_comment"
              type="textarea"
              :rows="3"
              maxlength="2000"
              show-word-limit
              placeholder="评价房东的服务态度、响应速度等..."
            />
          </el-form-item>
        </template>

        <el-form-item>
          <el-button type="primary" size="large" :loading="submitting" @click="submit">
            提交评价
          </el-button>
          <el-button size="large" @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { reviewService } from '@/services/review'
import { propertyService } from '@/services/property'
import { bookingService } from '@/services/booking'
import type { Property } from '@/types/property'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)

const propertyId = computed(() => Number(route.query.property_id) || 0)
const property = ref<Property | null>(null)
const availableBookings = ref<any[]>([])

const isInstitute = computed(() => !!property.value?.institute_id)

const form = ref({
  booking_id: null as number | null,
  property_rating: 0,
  property_comment: '',
  landlord_rating: null as number | null,
  landlord_comment: '',
})

const rules = computed(() => {
  const base: any = {
    booking_id: [{ required: true, message: '请选择关联租赁', trigger: 'change' }],
    property_rating: [
      { required: true, message: '请给房源评分', trigger: 'change' },
      { type: 'number', min: 1, max: 5, message: '评分需在 1-5 之间', trigger: 'change' },
    ],
  }
  if (!isInstitute.value) {
    base.landlord_rating = [
      { required: true, message: '个人房东需要评分', trigger: 'change' },
      { type: 'number', min: 1, max: 5, message: '评分需在 1-5 之间', trigger: 'change' },
    ]
  }
  return base
})

onMounted(async () => {
  if (!propertyId.value) {
    ElMessage.error('缺少房源信息')
    router.back()
    return
  }
  loading.value = true
  try {
    const [prop, bookings] = await Promise.all([
      propertyService.getProperty(propertyId.value),
      bookingService.list().catch(() => []),
    ])
    property.value = prop
    // 筛选该房源的已确认/已完成 booking
    availableBookings.value = (bookings || [])
      .filter((b: any) => b.property_id === propertyId.value)
      .filter((b: any) => b.status === 'approved' || b.status === 'completed')
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
})

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await reviewService.create({
      booking_id: form.value.booking_id!,
      property_rating: form.value.property_rating,
      property_comment: form.value.property_comment || undefined,
      landlord_rating: isInstitute.value ? null : form.value.landlord_rating,
      landlord_comment: isInstitute.value ? undefined : (form.value.landlord_comment || undefined),
    })
    ElMessage.success('评价提交成功，等待审核')
    router.back()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.review-form-page {
  max-width: 720px;
  margin: 0 auto;
  padding-bottom: 60px;
}

.form-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.form-header h1 {
  font-size: 22px;
  font-weight: 700;
  color: #222;
}

.property-info-card {
  margin-bottom: 16px;
}

.property-summary h3 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #222;
}

.property-summary p {
  margin: 0 0 8px;
  font-size: 13px;
  color: #999;
}

.form-card {
  margin-bottom: 16px;
}

.no-data-hint {
  font-size: 12px;
  color: #999;
  display: block;
  margin-top: 6px;
}
</style>
