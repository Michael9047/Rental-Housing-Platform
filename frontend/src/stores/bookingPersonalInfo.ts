/** 预订流程个人信息 Store — 跨步骤保持表单状态。 */
import { defineStore } from 'pinia'
import { reactive } from 'vue'
import type { PersonalInfoForm } from '@/utils/personalInfoValidation'

function createEmptyForm(): PersonalInfoForm {
  return {
    chinese_name: '',
    given_name_pinyin: '',
    surname_pinyin: '',
    birth_date: '',
    gender: '',
    phone: '',
    phone_country_code: '+86',
    email: '',
    nationality: '中国大陆',
    school_name: '',
    enrollment_grade: '',
    major_english: '',
    region: '',
    address_detail: '',
    postal_code: '',
    address_line: '',
  }
}

export const useBookingPersonalInfoStore = defineStore('bookingPersonalInfo', () => {
  const form = reactive<PersonalInfoForm>(createEmptyForm())

  function reset() {
    Object.assign(form, createEmptyForm())
  }

  return { form, reset }
})
