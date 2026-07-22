<!-- 预订流程第三步：填写并校验个人信息与住址信息。 -->
<template>
  <BookingFlowLayout
    title="填写个人信息"
    :current-step="2"
    previous-route="booking-lease-term"
    next-route="booking-emergency-contact"
    :next-disabled="submitting"
    manual-next
    @next="submitForm"
  >
    <el-form label-position="top" class="personal-form booking-form-standard" @submit.prevent>
      <div class="section-heading">
        <div><h2>个人信息</h2><p>请确保姓名和证件信息真实一致。</p></div>
        <el-button @click="fillFromAccount">从账户资料填充</el-button>
      </div>

      <div class="form-grid">
        <FormField label="中文姓名" field="chinese_name" help="请填写与证件一致的中文姓名。" />
        <FormField label="名的英文大写拼音" field="given_name_pinyin" help="请按护照顺序填写名的拼音。" pinyin />
        <FormField label="姓的英文大写拼音" field="surname_pinyin" help="仅支持英文字母、空格和连字符，将自动转为大写。" pinyin />
        <div class="field-cell">
          <el-form-item class="birth-date-field" label="出生日期" :error="visibleError('birth_date')">
            <el-date-picker v-model="form.birth_date" value-format="YYYY-MM-DD" type="date" :disabled-date="disableBirthDate" style="width:100%" @blur="touch('birth_date')" @change="change('birth_date')" />
            <HelpText text="申请人须年满 18 周岁，且年龄不能超过 100 周岁。" />
          </el-form-item>
        </div>
        <div class="field-cell">
          <el-form-item label="性别" :error="visibleError('gender')">
            <el-radio-group v-model="form.gender" @change="change('gender')">
              <el-radio value="male">男</el-radio><el-radio value="female">女</el-radio><el-radio value="other">其他</el-radio>
            </el-radio-group>
            <HelpText text="请选择证件所示性别。" />
          </el-form-item>
        </div>
        <div class="field-cell">
          <el-form-item label="手机国家区号和手机号" :error="phoneError">
            <div class="phone-row">
              <el-select v-model="form.phone_country_code" @change="change('phone_country_code')">
                <el-option v-for="item in phoneCodes" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <el-input v-model="form.phone" inputmode="numeric" maxlength="15" @blur="touch('phone')" @input="phoneInput" />
            </div>
            <HelpText text="用于接收预订进度通知，请填写可正常联系的号码。" />
          </el-form-item>
        </div>
        <FormField label="邮箱" field="email" help="用于接收申请文件和预订结果。" />
        <div class="field-cell">
          <el-form-item label="护照国籍/地区" :error="visibleError('nationality')">
            <el-select v-model="form.nationality" filterable style="width:100%" @blur="touch('nationality')" @change="change('nationality')">
              <el-option v-for="country in countries" :key="country" :label="country" :value="country" />
            </el-select>
            <HelpText text="请按护照签发信息选择国籍或地区。" />
          </el-form-item>
        </div>
      </div>

      <h2 class="subheading">学习信息</h2>
      <div class="form-grid">
        <FormField label="学校" field="school_name" help="请填写当前或即将入读的学校全称。" />
        <div class="field-cell">
          <el-form-item label="入学年级" :error="visibleError('enrollment_grade')">
            <el-select v-model="form.enrollment_grade" style="width:100%" @blur="touch('enrollment_grade')" @change="change('enrollment_grade')">
              <el-option v-for="grade in grades" :key="grade" :label="grade" :value="grade" />
            </el-select>
            <HelpText text="请选择预订入住时对应的入学年级。" />
          </el-form-item>
        </div>
        <FormField label="专业英文名称" field="major_english" help="请填写学校录取材料中的专业英文名称。" />
      </div>

      <h2 class="subheading">住址信息</h2>
      <div class="form-grid">
        <AddressSelector :model-value="form" />
        <FormField label="详细联系地址" field="address_line" help="请填写街道、门牌号和房间号等详细信息。" />
        <FormField label="邮政编码" field="postal_code" help="支持字母、数字、空格和连字符。" />
      </div>

      <el-alert v-if="submitError" :title="submitError" type="error" :closable="false" />
    </el-form>
  </BookingFlowLayout>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BookingFlowLayout from '@/components/booking/BookingFlowLayout.vue'
import AddressSelector from '@/components/booking/AddressSelector.vue'
import { useBookingPersonalInfoStore } from '@/stores/bookingPersonalInfo'
import { useAuthStore } from '@/stores/auth'
import { bookingPersonalInfoService } from '@/services/bookingPersonalInfo'
import { bookingDraftService } from '@/services/bookingDraft'
import { normalizePinyin, requiredFields, validatePersonalInfo, validatePersonalInfoField, type PersonalInfoField } from '@/utils/personalInfoValidation'
import { restoreLegacyAddress } from '@/types/address'

const router = useRouter()
const route = useRoute()
const personalStore = useBookingPersonalInfoStore()
const authStore = useAuthStore()
const form = personalStore.form
const touched = reactive(new Set<PersonalInfoField>())
const submitted = ref(false)
const submitting = ref(false)
const submitError = ref('')
const errors = reactive(validatePersonalInfo(form))
const countries = ['中国大陆', '中国香港', '中国澳门', '中国台湾', '英国', '美国', '加拿大', '澳大利亚', '新加坡', '日本', '韩国', '德国', '法国', '其他']
const grades = ['本科一年级', '本科二年级', '本科三年级', '本科四年级', '硕士', '博士', '语言课程', '其他']
const phoneCodes = [{ label: '中国 +86', value: '+86' }, { label: '英国 +44', value: '+44' }, { label: '美国/加拿大 +1', value: '+1' }, { label: '澳大利亚 +61', value: '+61' }, { label: '新加坡 +65', value: '+65' }, { label: '日本 +81', value: '+81' }, { label: '韩国 +82', value: '+82' }]

function revalidate(field: PersonalInfoField) { errors[field] = validatePersonalInfoField(field, form[field]) }
function touch(field: PersonalInfoField) { touched.add(field); revalidate(field) }
function change(field: PersonalInfoField) { if (touched.has(field) || errors[field]) revalidate(field) }
function visibleError(field: PersonalInfoField) { return submitted.value || touched.has(field) ? errors[field] : '' }
const phoneError = computed(() => visibleError('phone_country_code') || visibleError('phone'))
function phoneInput(value: string) { form.phone = value.replace(/\D/g, ''); change('phone') }
function disableBirthDate(date: Date) { return date > new Date() }

function fillFromAccount() {
  const user = authStore.user
  if (!user) return
  if (!form.chinese_name) form.chinese_name = user.username || ''
  if (!form.phone) form.phone = user.phone?.replace(/\D/g, '') || ''
  if (!form.email) form.email = user.email || ''
  ElMessage.success('已从账户资料填充可用信息')
}

async function submitForm() {
  submitted.value = true
  Object.assign(errors, validatePersonalInfo(form))
  requiredFields.forEach((field) => touched.add(field))
  if (requiredFields.some((field) => errors[field])) return
  submitting.value = true
  submitError.value = ''
  try {
    await bookingPersonalInfoService.validate({ ...form })
    await bookingDraftService.save(Number(route.params.propertyId), {
      personal_info: { ...form },
      current_step: 'emergency_contact',
    })
    router.push({ name: 'booking-emergency-contact', params: { propertyId: String(route.params.propertyId) } })
  } catch (error: any) {
    submitError.value = error?.response?.data?.detail?.[0]?.msg || error?.response?.data?.detail || '个人信息校验失败，请检查后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const draft = await bookingDraftService.get(Number(route.params.propertyId))
    if (!draft.move_in_date || !draft.lease_months) {
      router.replace({ name: 'booking-lease-term', params: { propertyId: String(route.params.propertyId) } })
      return
    }
    if (draft.personal_info) {
      Object.assign(form, draft.personal_info)
      restoreLegacyAddress(form)
    }
  } catch {
    router.replace({ name: 'booking-move-in-date', params: { propertyId: String(route.params.propertyId) } })
  }
})

const HelpText = defineComponent({ props: { text: { type: String, required: true } }, setup: (props) => () => h('div', { class: 'help-text' }, props.text) })
const FormField = defineComponent({
  props: { label: { type: String, required: true }, field: { type: String, required: true }, help: { type: String, required: true }, pinyin: Boolean },
  setup(props) {
    const field = props.field as PersonalInfoField
    return () => h('div', { class: 'field-wrap' }, [
      h('label', { class: 'field-label' }, props.label),
      h('input', {
        class: ['native-input', visibleError(field) ? 'is-error' : ''], value: form[field],
        onInput: (event: Event) => { const input = event.target as HTMLInputElement; const value = props.pinyin ? normalizePinyin(input.value) : input.value; form[field] = value as never; input.value = value; change(field) },
        onBlur: () => touch(field),
      }),
      h('div', { class: 'help-text' }, props.help),
      visibleError(field) ? h('div', { class: 'error-text' }, visibleError(field)) : null,
    ])
  },
})
</script>

<style scoped>
.personal-form {
  display: grid;
  width: min(100%, 1040px);
  margin: 0 auto;
  gap: 28px;
}
.section-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.section-heading h2, .subheading { margin: 0; font-size: 18px; }
.section-heading p { margin: 6px 0 0; color: var(--text-muted); font-size: 13px; }
.subheading { padding-top: 24px; border-top: 1px solid var(--border-light); }
.form-grid {
  align-items: start;
}

@media (max-width: 767px) {
  .personal-form { gap: 24px; }
  .section-heading { flex-direction: column; }
}
</style>
