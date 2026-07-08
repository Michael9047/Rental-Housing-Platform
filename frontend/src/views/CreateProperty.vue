<template>
  <div class="create-page">
    <!-- 智能文本输入（仅创建模式） -->
    <el-card v-if="!isEdit" shadow="never" class="smart-card">
      <template #header>
        <span>📝 快速发布 — 粘贴房源描述，自动识别信息</span>
      </template>
      <el-input
        v-model="rawText"
        type="textarea"
        :rows="5"
        placeholder="例如：工业园区独墅湖高教区仁爱路199号翰林缘单身公寓，月租2200元，押金2200元，服务费10%，38平米，独立卫浴，适合白领和学生。楼下便利店、餐厅齐全。"
      />
      <div class="smart-actions">
        <el-button type="primary" :loading="parsing" @click="smartParse" :disabled="!rawText.trim()">
          🔍 智能识别
        </el-button>
        <el-button @click="rawText = ''" :disabled="!rawText.trim()">清空</el-button>
      </div>
      <div v-if="parseResult" class="parse-result">
        <el-alert
          v-if="parseResult.unrecognized.length"
          :title="'未识别内容: ' + parseResult.unrecognized.join('；')"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <el-alert
          v-else
          title="已全部识别，请检查后提交"
          type="success"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
      </div>
    </el-card>

    <!-- 表单编辑 -->
    <el-card shadow="never">
      <template #header>
        <span>{{ isEdit ? '编辑房源信息' : '房源信息' }}</span>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        @submit.prevent="handleSubmit"
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

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="月租金" prop="price_monthly">
              <el-input-number v-model="form.price_monthly" :min="0" :precision="2" controls-position="right" style="width: 200px" />
              <span style="margin-left: 8px; color: #909399">元/月</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="押金">
              <el-input-number v-model="form.deposit_amount" :min="0" :precision="0" controls-position="right" style="width: 180px" />
              <span style="margin-left: 8px; color: #909399">元</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="户型">
              <el-input-number v-model="form.bedrooms" :min="0" controls-position="right" style="width: 80px" />
              <span style="margin: 0 4px">室</span>
              <el-input-number v-model="form.bathrooms" :min="0" controls-position="right" style="width: 80px" />
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

        <el-form-item label="服务费率">
          <el-input-number v-model="form.service_fee_rate" :min="0" :max="1" :precision="2" :step="0.01" controls-position="right" style="width: 140px" />
          <span style="margin-left: 8px; color: #909399">{{ ((form.service_fee_rate || 0) * 100).toFixed(0) }}%</span>
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="5"
            placeholder="描述房源的特色、周边配套等..."
          />
        </el-form-item>

        <el-form-item label="经纬度">
          <el-col :span="11">
            <el-input v-model="form.latitude" placeholder="纬度 (如 31.315)" />
          </el-col>
          <el-col :span="2" style="text-align: center">—</el-col>
          <el-col :span="11">
            <el-input v-model="form.longitude" placeholder="经度 (如 120.715)" />
          </el-col>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="submitting">
            {{ isEdit ? '保存修改' : '发布' }}
          </el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import type { PropertyType } from '@/types/property'

const router = useRouter()
const route = useRoute()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()

const isEdit = computed(() => route.name === 'edit-property')
const editId = computed(() => (isEdit.value ? Number(route.params.id) : null))

const formRef = ref<FormInstance>()
const submitting = ref(false)

// --- 智能识别 ---
const rawText = ref('')
const parsing = ref(false)
const parseResult = ref<{ unrecognized: string[] } | null>(null)

// ??/????????????
const countries = [
  { value: 'CN', label: '???? ?????????' },
  { value: 'OT', label: '?? ???????? + ???' },
]

const districtsCN = ['????', '???', '???', '???', '???', '???']
const districts = ref<string[]>([...districtsCN])

// ????
const currencyLabel = computed(() => form.country === 'CN' ? '?' : '????')

// ????
function onCountryChange() {
  if (form.country === 'CN') {
    districts.value = [...districtsCN]
    if (!districtsCN.includes(form.district)) {
      form.district = ''
    }
  } else {
    districts.value = []
    form.district = ''
  }
}

const form = reactive({
  title: '',
  address: '',
  district: '',
  country: 'CN',
  price_monthly: 0 as number | undefined,
  deposit_amount: undefined as number | undefined,
  bedrooms: 0,
  bathrooms: 0,
  area_sqm: undefined as number | undefined,
  property_type: 'apartment' as PropertyType,
  service_fee_rate: undefined as number | undefined,
  description: '',
  latitude: '' as string | undefined,
  longitude: '' as string | undefined,
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  address: [{ required: true, message: '请输入地址', trigger: 'blur' }],
  district: [{ required: true, message: '请选择区域', trigger: 'change' }],
  price_monthly: [{ required: true, message: '请输入月租金', trigger: 'blur' }],
  property_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

// --- 智能解析引擎 ---
const cnNumMap: Record<string, number> = { 一:1,二:2,两:2,三:3,四:4,五:5,六:6,七:7,八:8,九:9,十:10 }

function parseChineseNumber(s: string): number {
  return cnNumMap[s] ?? parseInt(s)
}

function smartParse() {
  parsing.value = true
  parseResult.value = null
  const text = rawText.value
  const unrecognized: string[] = []

  // 1. 户型 — 卧室+卫生间
  const roomPatterns = [
    /(\d+)室(\d+)厅(\d+)卫/,
    /(\d+)室(\d+)厅/,
    /(\d+)室(\d+)卫/,
    /([一二两三四五六七八九十])室([一二两三四五六七八九十])厅([一二两三四五六七八九十])卫/,
    /([一二两三四五六七八九十])室([一二两三四五六七八九十])厅/,
    /([一二两三四五六七八九十])室([一二两三四五六七八九十])卫/,
    /(\d+)房(\d+)厅(\d+)卫/,
    /(\d+)房(\d+)厅/,
  ]
  let bedrooms = -1, bathrooms = -1
  for (const p of roomPatterns) {
    const m = text.match(p)
    if (m) {
      bedrooms = parseChineseNumber(m[1])
      bathrooms = p.source.includes('卫') ? parseChineseNumber(m[p.source.includes('厅') ? (p.source.match(/卫/g)?.length === 1 ? 3 : 3) : 2]) : (p.source.includes('卫') && m[3] ? parseChineseNumber(m[3]) : -1)
      break
    }
  }
  // 单独匹配 室/卫
  if (bedrooms === -1) {
    const m = text.match(/(\d+)\s*室/) || text.match(/([一二两三四五六七八九十])\s*室/)
    if (m) bedrooms = parseChineseNumber(m[1])
  }
  if (bathrooms === -1) {
    const m = text.match(/(\d+)\s*卫/) || text.match(/([一二两三四五六七八九十])\s*卫/)
    if (m) bathrooms = parseChineseNumber(m[1])
  }
  // 独立卫浴
  if (bathrooms === -1 && /独立卫浴|独卫/.test(text)) bathrooms = 1

  // 2. 面积
  const areaM = text.match(/(\d+(?:\.\d+)?)\s*(?:平米|平方米|㎡|平)/)
  const area = areaM ? parseFloat(areaM[1]) : undefined

  // 3. 月租
  const rentPatterns = [
    /月租\s*(\d+(?:\.\d+)?)/,
    /(\d+(?:\.\d+)?)\s*元?\s*[\/每]\s*月/,
    /租金\s*(\d+(?:\.\d+)?)/,
    /(\d+(?:\.\d+)?)\s*元?\s*(?:每月|一个月)/,
  ]
  let rent: number | undefined
  for (const p of rentPatterns) {
    const m = text.match(p)
    if (m) { rent = parseFloat(m[1]); break }
  }

  // 4. 押金
  const depositM = text.match(/押金\s*(\d+(?:\.\d+)?)/) || text.match(/押[一1]付[三3]/)
  const deposit = depositM ? (depositM[1] ? parseFloat(depositM[1]) : (rent ?? 0)) : undefined

  // 5. 服务费
  const feeM = text.match(/服务费\s*(\d+(?:\.\d+)?)\s*%/)
  const fee = feeM ? parseFloat(feeM[1]) / 100 : undefined

  // 6. 类型
  let ptype: PropertyType | undefined
  if (/别墅/.test(text)) ptype = 'house'
  else if (/单间|单[身人]公[寓寓]/.test(text)) ptype = 'studio'
  else if (/合租|合[住宿]/.test(text)) ptype = 'shared'
  else if (/公寓/.test(text)) ptype = 'apartment'

  // 7. 区域
  let district = ''
  for (const d of districts.value) {
    if (text.includes(d)) { district = d; break }
  }

  // 8. 地址 — 提取具体路段信息
  let address = ''
  const addrM = text.match(/([^，,。.！!；;]+?(?:路|街|道|巷|弄|号|小区|花园|苑|城|湾|岸|郡|府|广场)[^，,。.！!；;]*)/)
  if (addrM) address = addrM[1].trim()

  // 9. 标题 — 用区域+类型自动生成
  let title = ''
  if (district) title += district
  if (address) title += address.replace(/^\S+区/, '').slice(0, 8)
  if (ptype) title += ({ apartment: '公寓', house: '别墅', studio: '单间', shared: '合租' })[ptype]

  // 10. 未识别内容
  let remaining = text
    .replace(/[，,。.！!；;、\s]+/g, ' ').trim()
  const consumed: string[] = []
  if (address) consumed.push(address)
  if (district) consumed.push(district)
  for (const c of consumed) remaining = remaining.replace(c, '')
  remaining = remaining.replace(/\s+/g, ' ').trim()
  if (remaining.length > 0 && remaining.length < text.length * 0.5) {
    unrecognized.push(remaining.slice(0, 60))
  }

  // Apply to form
  if (title) form.title = title
  if (address) form.address = address
  if (district) form.district = district
  if (rent) form.price_monthly = rent
  if (deposit) form.deposit_amount = deposit
  if (fee !== undefined) form.service_fee_rate = fee
  if (bedrooms > 0) form.bedrooms = bedrooms
  if (bathrooms > 0) form.bathrooms = bathrooms
  if (area) form.area_sqm = area
  if (ptype) form.property_type = ptype
  form.description = text

  parseResult.value = { unrecognized }
  parsing.value = false
  if (!unrecognized.length) ElMessage.success('智能识别完成，请确认后提交')
  else ElMessage.info('部分内容已识别，请补充未识别部分')
}

// --- 提交 ---
async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (!authStore.user) {
    ElMessage.error('请先登录')
    return
  }

  submitting.value = true
  try {
    if (isEdit.value && editId.value) {
      await propertyStore.update(editId.value, {
        title: form.title,
        address: form.address,
        district: form.district,
        price_monthly: form.price_monthly,
        property_type: form.property_type,
        bedrooms: form.bedrooms,
        bathrooms: form.bathrooms,
        area_sqm: form.area_sqm,
        description: form.description || undefined,
        latitude: form.latitude ? Number(form.latitude) : undefined,
        longitude: form.longitude ? Number(form.longitude) : undefined,
      })
      ElMessage.success('房源信息已更新')
      router.push('/property/manage')
    } else {
      await propertyStore.create({
        title: form.title,
        address: form.address,
        district: form.district,
        price_monthly: form.price_monthly!,
        property_type: form.property_type,
        landlord_id: authStore.user.id,
        bedrooms: form.bedrooms,
        bathrooms: form.bathrooms,
        area_sqm: form.area_sqm,
        description: form.description || undefined,
        latitude: form.latitude ? Number(form.latitude) : undefined,
        longitude: form.longitude ? Number(form.longitude) : undefined,
      })
      ElMessage.success('房源发布成功')
      router.push('/property/manage')
    }
  } catch {
    // handled by interceptor
  } finally {
    submitting.value = false
  }
}

// --- 编辑模式：加载已有数据 ---
onMounted(async () => {
  if (isEdit.value && editId.value) {
    await propertyStore.fetchById(editId.value)
    const p = propertyStore.currentProperty
    if (p) {
      form.title = p.title
      form.address = p.address
      form.district = p.district
      form.country = (p as any).country || 'CN'
      if (form.country !== 'CN') districts.value = []
      form.price_monthly = p.price_monthly
      form.deposit_amount = p.deposit_amount
      form.bedrooms = p.bedrooms
      form.bathrooms = p.bathrooms
      form.area_sqm = p.area_sqm ?? undefined
      form.property_type = p.property_type
      form.service_fee_rate = p.service_fee_rate ?? undefined
      form.description = p.description
      if (p.latitude) form.latitude = String(p.latitude)
      if (p.longitude) form.longitude = String(p.longitude)
    }
  }
})
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

.smart-card {
  margin-bottom: 20px;
  border: 2px dashed #c0c4cc;
}

.smart-actions {
  margin-top: 12px;
  display: flex;
  gap: 12px;
}

.parse-result {
  margin-top: 12px;
}
</style>
