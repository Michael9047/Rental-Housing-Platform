/** 紧急联系人校验服务 —— 对应后端 POST /bookings/emergency-contact/validate */
import api from './api'

export interface EmergencyContactValidationResult {
  valid: boolean
}

export const bookingEmergencyContactService = {
  /** 提交紧急联系人信息进行服务端校验。 */
  validate(data: Record<string, any>): Promise<EmergencyContactValidationResult> {
    return api.post('/bookings/emergency-contact/validate', data).then((r) => r.data)
  },
}
