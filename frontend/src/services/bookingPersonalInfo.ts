/** 个人信息校验服务 —— 对应后端 POST /bookings/personal-info/validate */
import api from './api'

export interface PersonalInfoValidationResult {
  valid: boolean
}

export const bookingPersonalInfoService = {
  /** 提交个人信息进行服务端校验。 */
  validate(data: Record<string, any>): Promise<PersonalInfoValidationResult> {
    return api.post('/bookings/personal-info/validate', data).then((r) => r.data)
  },
}
