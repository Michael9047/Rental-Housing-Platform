<template>
  <div class="create-page">
    <h2>{{ isEditMode ? '编辑房源' : '发布房源' }}</h2>

    <el-card shadow="never">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        @submit.prevent="handleCreate"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="例如：园区两室一厅精装修" maxlength="200" show-word-limit />
        </el-form-item>

        <el-form-item label="地址" prop="address">
          <el-input v-model="form.address" placeholder="详细地址" />
          <p class="geocode-hint">
            <span v-if="geocodeStatus === 'loading'">正在自动回填经纬度…</span>
            <span v-else-if="geocodeStatus === 'ready'">已自动回填经纬度</span>
            <span v-else-if="geocodeStatus === 'missing-key'">未配置高德地图 Key，无法自动回填</span>
            <span v-else-if="geocodeStatus === 'error'">自动回填失败，可继续保存后再手动补充</span>
            <span v-else>输入地址后会自动回填经纬度</span>
          </p>
        </el-form-item>

        <el-form-item label="区域" prop="district">
          <el-select v-model="form.district" placeholder="选择区域">
            <el-option v-for="d in districts" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>

        <el-form-item label="月租金" prop="price_monthly">
          <el-input-number v-model="form.price_monthly" :min="0" :precision="2" controls-position="right" style="width: 200px" />
          <span style="margin-left: 8px; color: #909399">元/月</span>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="户型">
              <el-input-number v-model="form.bedrooms" :min="0" controls-position="right" style="width: 100px" />
              <span style="margin-left: 4px">室</span>
              <el-input-number v-model="form.bathrooms" :min="0" controls-position="right" style="width: 100px; margin-left: 8px" />
              <span style="margin-left: 4px">卫</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="面积">
              <el-input-number v-model="form.area_sqm" :min="0" :precision="2" controls-position="right" style="width: 140px" />
              <span style="margin-left: 4px">㎡</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="类型" prop="property_type">
              <el-select v-model="form.property_type">
                <el-option label="公寓" value="apartment" />
                <el-option label="别墅" value="house" />
                <el-option label="单间" value="studio" />
                <el-option label="合租" value="shared" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="5"
            placeholder="描述房源的特色、周边配套等..."
          />
        </el-form-item>

        <el-form-item label="坐标">
          <el-input :model-value="coordinateText" readonly placeholder="输入地址后自动回填" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="submitting">
            {{ isEditMode ? '保存修改' : '发布' }}
          </el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import type { PropertyType } from '@/types/property'
import { propertyService } from '@/services/property'

const router = useRouter()
const route = useRoute()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const geocodeStatus = ref<'idle' | 'loading' | 'ready' | 'missing-key' | 'error'>('idle')
const isHydrating = ref(false)
const geocodeRequestSeq = ref(0)
let geocodeTimer: number | undefined

const districts = ['工业园区', '姑苏区', '高新区', '吴中区', '相城区', '吴江区']

const propertyId = computed(() => Number(route.params.id))
const isEditMode = computed(() => route.name === 'edit-property' && Number.isFinite(propertyId.value) && propertyId.value > 0)

const form = reactive({
  title: '',
  address: '',
  district: '',
  price_monthly: 0,
  bedrooms: 0,
  bathrooms: 0,
  area_sqm: undefined as number | undefined,
  property_type: 'apartment' as PropertyType,
  description: '',
  latitude: null as number | null,
  longitude: null as number | null,
})

const coordinateText = computed(() => {
  if (form.latitude == null || form.longitude == null) {
    return '暂无坐标'
  }
  return `${form.latitude.toFixed(6)}, ${form.longitude.toFixed(6)}`
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  address: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  district: [{ required: true, message: '请选择区域', trigger: 'change' }],
  price_monthly: [{ required: true, message: '请输入月租金', trigger: 'blur' }],
  property_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

function clearGeocodeTimer() {
  if (geocodeTimer !== undefined) {
    window.clearTimeout(geocodeTimer)
    geocodeTimer = undefined
  }
}

function resetCoordinates() {
  form.latitude = null
  form.longitude = null
  geocodeStatus.value = 'idle'
}

async function runGeocode() {
  const address = form.address.trim()
  const district = form.district.trim()

  if (!address) {
    resetCoordinates()
    return
  }

  geocodeStatus.value = 'loading'
  const requestSeq = geocodeRequestSeq.value + 1
  geocodeRequestSeq.value = requestSeq

  try {
    const result = await propertyService.geocodeAddress(address, district || undefined)
    if (requestSeq !== geocodeRequestSeq.value) {
      return
    }
    form.latitude = result.latitude
    form.longitude = result.longitude
    geocodeStatus.value = 'ready'
  } catch (error: any) {
    if (requestSeq !== geocodeRequestSeq.value) {
      return
    }
    if (error?.response?.status === 503) {
      geocodeStatus.value = 'missing-key'
      return
    }
    geocodeStatus.value = 'error'
  }
}

watch(
  () => [form.address, form.district],
  () => {
    if (isHydrating.value) return
    clearGeocodeTimer()
    resetCoordinates()
    geocodeTimer = window.setTimeout(() => {
      void runGeocode()
    }, 500)
  },
)

onMounted(async () => {
  const id = propertyId.value
  if (!isEditMode.value) {
    return
  }

  isHydrating.value = true
  try {
    await propertyStore.fetchById(id)
    const property = propertyStore.currentProperty
    if (!property) {
      ElMessage.error('房源未找到')
      router.push('/property/manage')
      return
    }

    form.title = property.title
    form.address = property.address
    form.district = property.district
    form.price_monthly = property.price_monthly
    form.bedrooms = property.bedrooms
    form.bathrooms = property.bathrooms
    form.area_sqm = property.area_sqm ?? undefined
    form.property_type = property.property_type
    form.description = property.description || ''
    form.latitude = property.latitude
    form.longitude = property.longitude

    if (form.latitude == null || form.longitude == null) {
      geocodeStatus.value = 'idle'
    } else {
      geocodeStatus.value = 'ready'
    }
  } finally {
    isHydrating.value = false
  }
})

onBeforeUnmount(() => {
  clearGeocodeTimer()
})

async function handleCreate() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (!authStore.user) {
    ElMessage.error('请先登录')
    return
  }

  submitting.value = true
  try {
    const createPayload = {
      title: form.title,
      address: form.address,
      district: form.district,
      price_monthly: form.price_monthly,
      property_type: form.property_type,
      landlord_id: authStore.user.id,
      bedrooms: form.bedrooms,
      bathrooms: form.bathrooms,
      area_sqm: form.area_sqm,
      description: form.description || undefined,
      latitude: form.latitude ?? undefined,
      longitude: form.longitude ?? undefined,
    }

    const updatePayload = {
      title: form.title,
      address: form.address,
      district: form.district,
      price_monthly: form.price_monthly,
      property_type: form.property_type,
      bedrooms: form.bedrooms,
      bathrooms: form.bathrooms,
      area_sqm: form.area_sqm,
      description: form.description || undefined,
      latitude: form.latitude ?? undefined,
      longitude: form.longitude ?? undefined,
    }

    if (isEditMode.value) {
      await propertyStore.update(propertyId.value, updatePayload)
      ElMessage.success('房源修改成功')
    } else {
      await propertyStore.create(createPayload)
      ElMessage.success('房源发布成功')
    }

    router.push('/property/manage')
  } catch {
    // handled by interceptor
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.create-page {
  max-width: 800px;
  margin: 0 auto;
}

.create-page h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 20px;
}

.geocode-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
