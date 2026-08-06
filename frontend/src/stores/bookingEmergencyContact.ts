/** 预订流程紧急联系人 Store — 跨步骤保持表单状态，支持从个人信息复制地址。 */
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import type { EmergencyContactForm } from '@/utils/emergencyContactValidation'
import { useBookingPersonalInfoStore } from '@/stores/bookingPersonalInfo'

function createEmptyForm(): EmergencyContactForm {
  return {
    chinese_name: '',
    given_name_pinyin: '',
    surname_pinyin: '',
    relationship: '',
    birth_date: '',
    phone: '',
    phone_country_code: '+86',
    email: '',
    gender: '',
    region: '',
    address_line: '',
    postal_code: '',
    consultant_id: '',
    country_code: '',
    country_name: '',
    level1_code: '',
    level1_name: '',
    city_code: '',
    city_name: '',
    district_code: '',
    district_name: '',
    address_detail: '',
  }
}

export const useBookingEmergencyContactStore = defineStore('bookingEmergencyContact', () => {
  const form = reactive<EmergencyContactForm>(createEmptyForm())
  const sameAsApplicant = ref(false)

  function reset() {
    Object.assign(form, createEmptyForm())
    sameAsApplicant.value = false
  }

  /** 将地址字段切换为与申请人相同或清空。 */
  function toggleSameAddress(enabled: boolean) {
    sameAsApplicant.value = enabled
    if (enabled) {
      const applicant = useBookingPersonalInfoStore()
      copyApplicantAddress(applicant.form)
    }
  }

  function copyApplicantAddress(applicantForm: Record<string, any>) {
    const addressFields = [
      'country_code', 'country_name', 'level1_code', 'level1_name',
      'city_code', 'city_name', 'district_code', 'district_name', 'region',
      'postal_code',
    ] as const
    addressFields.forEach((field) => { form[field] = applicantForm[field] || '' })
    form.address_line = applicantForm.address_line || applicantForm.address_detail || ''
    form.address_detail = form.address_line
  }

  /** 别名，兼容旧 API：从申请人数据复制地址字段。 */
  function setSameAsApplicant(enabled: boolean, applicantForm?: Record<string, any>) {
    sameAsApplicant.value = enabled
    if (enabled && applicantForm) {
      copyApplicantAddress(applicantForm)
    }
  }

  return { form, sameAsApplicant, reset, toggleSameAddress, setSameAsApplicant }
})
