<template>
  <div class="emergency-form">
    <h3 class="form-section-title">
      紧急联系人
      <el-checkbox v-model="sameAsGuarantor" class="same-checkbox" @change="onSameAsGuarantorChange">
        与"担保人信息"相同？
      </el-checkbox>
    </h3>
    <el-form :model="form" label-position="top" class="info-form">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="中文姓名" prop="chinese_name">
            <el-input v-model="form.chinese_name" placeholder="一般为承租人的父母、法定监护人或近亲" :disabled="sameAsGuarantor" @blur="validateField('chinese_name')" />
            <div v-if="errors.chinese_name" class="error-text">{{ errors.chinese_name }}</div>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="名（拼音）" prop="given_name_pinyin">
            <el-input v-model="form.given_name_pinyin" placeholder="输入名的大写拼音，如&quot;MING&quot;" :disabled="sameAsGuarantor" @blur="validateField('given_name_pinyin')" />
            <div v-if="errors.given_name_pinyin" class="error-text">{{ errors.given_name_pinyin }}</div>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="姓（拼音）" prop="surname_pinyin">
            <el-input v-model="form.surname_pinyin" placeholder="输入姓的大写拼音，如&quot;LI&quot;" :disabled="sameAsGuarantor" @blur="validateField('surname_pinyin')" />
            <div v-if="errors.surname_pinyin" class="error-text">{{ errors.surname_pinyin }}</div>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="与你的关系" prop="relation">
            <el-select v-model="form.relation" placeholder="与你的关系" style="width: 100%" :disabled="sameAsGuarantor" @change="validateField('relation')">
              <el-option label="父亲" value="父亲" />
              <el-option label="母亲" value="母亲" />
              <el-option label="配偶" value="配偶" />
              <el-option label="子女" value="子女" />
              <el-option label="兄弟姐妹" value="兄弟姐妹" />
              <el-option label="其他亲属" value="其他亲属" />
              <el-option label="朋友" value="朋友" />
            </el-select>
            <div v-if="errors.relation" class="error-text">{{ errors.relation }}</div>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="出生日期" prop="birth_date">
            <el-date-picker
              v-model="form.birth_date"
              type="date"
              placeholder="请选择出生日期"
              value-format="YYYY-MM-DD"
              style="width: 100%"
              :disabled="sameAsGuarantor"
              @change="validateField('birth_date')"
            />
            <div class="hint-text">暂不支持16岁以下客户</div>
            <div v-if="errors.birth_date" class="error-text">{{ errors.birth_date }}</div>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="手机号" prop="phone">
            <el-input v-model="form.phone" placeholder="手机号码" :disabled="sameAsGuarantor" @blur="validateField('phone')">
              <template #prepend>+86</template>
            </el-input>
            <div v-if="errors.phone" class="error-text">{{ errors.phone }}</div>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="form.email" placeholder="请不要与个人邮箱重复！！" :disabled="sameAsGuarantor" @blur="validateField('email')" />
            <div class="hint-text">紧急联系人邮箱需真实有效，且不能与个人邮箱一致（否则会影响预订）</div>
            <div v-if="errors.email" class="error-text">{{ errors.email }}</div>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="性别" prop="gender">
            <el-radio-group v-model="form.gender" :disabled="sameAsGuarantor" @change="validateField('gender')">
              <el-radio value="male">男</el-radio>
              <el-radio value="female">女</el-radio>
            </el-radio-group>
            <div v-if="errors.gender" class="error-text">{{ errors.gender }}</div>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <h3 class="form-section-title">紧急联系人地址</h3>
    <el-form :model="form" label-position="top" class="info-form">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="所在地区" prop="region">
            <el-select
              v-model="selectedCountry"
              placeholder="请选择国家/地区"
              style="width: 100%; margin-bottom: 8px"
              :disabled="sameAsGuarantor"
              @change="onCountryChange"
            >
              <el-option v-for="c in countries" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select
              v-model="selectedProvince"
              placeholder="请选择省份"
              style="width: 100%; margin-bottom: 8px"
              :disabled="sameAsGuarantor || !selectedCountry || !showProvince"
              @change="onProvinceChange"
            >
              <el-option v-for="p in provinceOptions" :key="p.name" :label="p.name" :value="p.name" />
            </el-select>
            <el-select
              v-model="selectedCity"
              placeholder="请选择城市"
              style="width: 100%; margin-bottom: 8px"
              :disabled="sameAsGuarantor || !selectedCountry || (showProvince && !selectedProvince)"
              @change="onCityChange"
            >
              <el-option v-for="c in cityOptions" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select
              v-model="selectedDistrict"
              placeholder="请选择区/县"
              style="width: 100%"
              :disabled="sameAsGuarantor || !selectedCity || !showDistrict"
              @change="onDistrictChange"
            >
              <el-option v-for="d in districtOptions" :key="d" :label="d" :value="d" />
            </el-select>
            <div v-if="errors.region" class="error-text">{{ errors.region }}</div>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="联系地址" prop="address_detail">
            <el-input v-model="form.address_detail" placeholder="请填写包括城区、街道、小区在内的详细地址" :disabled="sameAsGuarantor" @blur="validateField('address_detail')" />
            <div v-if="errors.address_detail" class="error-text">{{ errors.address_detail }}</div>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="邮政编码" prop="postal_code">
            <el-input v-model="form.postal_code" placeholder="请填写邮编，如&quot;100001&quot;" :disabled="sameAsGuarantor" @blur="validateField('postal_code')" />
            <div v-if="errors.postal_code" class="error-text">{{ errors.postal_code }}</div>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <h3 class="form-section-title">更多信息</h3>
    <el-form label-position="top" class="info-form">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="顾问工号（选填）">
            <el-input v-model="form.consultant_id" placeholder="请输入顾问工号" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useBookingFlowStore } from '@/stores/bookingFlow'
import { getCountries, getCities, getProvinces, getDistricts, hasProvinces } from '@/data/regions'
import type { FormRules } from 'element-plus'

defineExpose({
  validate: () => validateAll(),
})

const bookingFlow = useBookingFlowStore()

const countries = getCountries()

const form = computed({
  get: () => bookingFlow.emergency,
  set: (val) => {
    Object.assign(bookingFlow.emergency, val)
    bookingFlow.saveToStorage()
  },
})

const sameAsGuarantor = ref(false)

const selectedCountry = ref('')
const selectedProvince = ref('')
const selectedCity = ref('')
const selectedDistrict = ref('')

const showProvince = computed(() => {
  return hasProvinces(selectedCountry.value)
})

const showDistrict = computed(() => {
  return hasProvinces(selectedCountry.value)
})

const provinceOptions = computed(() => {
  if (!selectedCountry.value) return []
  return getProvinces(selectedCountry.value)
})

const cityOptions = computed(() => {
  if (!selectedCountry.value) return []
  if (showProvince.value && !selectedProvince.value) return []
  return getCities(selectedCountry.value, showProvince.value ? selectedProvince.value : undefined)
})

const districtOptions = computed(() => {
  if (!showDistrict.value || !selectedCountry.value || !selectedProvince.value || !selectedCity.value) return []
  return getDistricts(selectedCountry.value, selectedProvince.value, selectedCity.value)
})

const errors = reactive<Record<string, string>>({})

const rules: FormRules = {
  chinese_name: [{ required: true, message: '请填写中文姓名', trigger: 'blur' }],
  given_name_pinyin: [{ required: true, message: '请填写名的拼音', trigger: 'blur' }],
  surname_pinyin: [{ required: true, message: '请填写姓的拼音', trigger: 'blur' }],
  relation: [{ required: true, message: '请选择与申请人的关系', trigger: 'change' }],
  birth_date: [{ required: true, message: '请选择出生日期', trigger: 'change' }],
  phone: [
    { required: true, message: '请填写手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请填写邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  region: [{ required: true, message: '请选择所在地区', trigger: 'change' }],
  address_detail: [{ required: true, message: '请填写联系地址', trigger: 'blur' }],
  postal_code: [{ required: true, message: '请填写邮政编码', trigger: 'blur' }],
}

function validateField(field: string) {
  if (sameAsGuarantor.value) {
    errors[field] = ''
    return true
  }

  const value = (form.value as any)[field]
  const fieldRules = (rules as any)[field]
  if (!fieldRules) return true

  errors[field] = ''

  for (const rule of fieldRules) {
    if (rule.required && (!value || value === '')) {
      errors[field] = rule.message
      return false
    }
    if (rule.pattern && value && !rule.pattern.test(value)) {
      errors[field] = rule.message
      return false
    }
    if (rule.type === 'email' && value) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailRegex.test(value)) {
        errors[field] = rule.message
        return false
      }
    }
  }
  return true
}

function validateAll(): boolean {
  if (sameAsGuarantor.value) {
    Object.keys(errors).forEach((k) => (errors[k] = ''))
    return true
  }

  let valid = true
  const fields = [
    'chinese_name',
    'given_name_pinyin',
    'surname_pinyin',
    'relation',
    'birth_date',
    'phone',
    'email',
    'gender',
    'region',
    'address_detail',
    'postal_code',
  ]
  for (const f of fields) {
    if (!validateField(f)) {
      valid = false
    }
  }
  return valid
}

function onSameAsGuarantorChange(val: boolean) {
  if (val) {
    const guarantor = bookingFlow.guarantor
    form.value.chinese_name = guarantor.chinese_name
    form.value.given_name_pinyin = guarantor.given_name_pinyin
    form.value.surname_pinyin = guarantor.surname_pinyin
    form.value.relation = guarantor.relation
    form.value.birth_date = guarantor.birth_date
    form.value.phone = guarantor.phone
    form.value.email = guarantor.email
    form.value.gender = guarantor.gender
    form.value.region = guarantor.region
    form.value.address_detail = guarantor.address_detail
    form.value.postal_code = guarantor.postal_code
    form.value.same_as_guarantor = true

    const { country, province, city, district } = parseRegion(guarantor.region)
    selectedCountry.value = country
    selectedProvince.value = province
    selectedCity.value = city
    selectedDistrict.value = district

    Object.keys(errors).forEach((k) => (errors[k] = ''))
  } else {
    form.value.same_as_guarantor = false
  }
}

function onCountryChange(val: string) {
  selectedProvince.value = ''
  selectedCity.value = ''
  selectedDistrict.value = ''
  validateField('region')
}

function onProvinceChange(val: string) {
  selectedCity.value = ''
  selectedDistrict.value = ''
  validateField('region')
}

function onCityChange(val: string) {
  selectedDistrict.value = ''
  validateField('region')
}

function onDistrictChange(val: string) {
  validateField('region')
}

function buildRegion(): string {
  const parts: string[] = [selectedCountry.value]
  if (selectedProvince.value) parts.push(selectedProvince.value)
  if (selectedCity.value) parts.push(selectedCity.value)
  if (selectedDistrict.value) parts.push(selectedDistrict.value)
  return parts.join(' / ')
}

function parseRegion(region: string) {
  if (!region) return { country: '', province: '', city: '', district: '' }
  const parts = region.split(' / ')
  return {
    country: parts[0] || '',
    province: parts[1] || '',
    city: parts[2] || '',
    district: parts[3] || '',
  }
}

onMounted(() => {
  if (form.value.region) {
    const { country, province, city, district } = parseRegion(form.value.region)
    selectedCountry.value = country
    selectedProvince.value = province
    selectedCity.value = city
    selectedDistrict.value = district
  }
  if (form.value.same_as_guarantor) {
    sameAsGuarantor.value = true
  }
})

watch(
  [selectedCountry, selectedProvince, selectedCity, selectedDistrict],
  () => {
    if (!sameAsGuarantor.value) {
      form.value.region = buildRegion()
      validateField('region')
    }
  }
)
</script>

<style scoped>
.emergency-form {
  padding: 0 4px;
}

.form-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.same-checkbox {
  font-weight: normal;
  font-size: 13px;
}

.info-form {
  margin-bottom: 24px;
}

.hint-text {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 4px;
  line-height: 1.4;
}

.error-text {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
