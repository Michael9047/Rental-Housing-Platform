<template>
  <div class="create-page">
    <h2>发布房源</h2>

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

        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="submitting">
            发布
          </el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import type { PropertyType } from '@/types/property'

const router = useRouter()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const districts = ['工业园区', '姑苏区', '高新区', '吴中区', '相城区', '吴江区']

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
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  address: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  district: [{ required: true, message: '请选择区域', trigger: 'change' }],
  price_monthly: [{ required: true, message: '请输入月租金', trigger: 'blur' }],
  property_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

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
    const _created = await propertyStore.create({
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
    })
    ElMessage.success('房源发布成功')
    router.push('/property/')
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
</style>
