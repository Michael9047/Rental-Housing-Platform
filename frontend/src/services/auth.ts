import api from './api'
import type {
  RegisterRequest,
  LoginRequest,
  TokenResponse,
  PhoneLoginRequest,
  PhoneLoginResponse,
  PhoneRegisterRequest,
  SendSmsCodeRequest,
  VerifySmsCodeRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
} from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  register(data: RegisterRequest): Promise<User> {
    return api.post('/auth/register', data).then((r) => r.data)
  },

  login(data: LoginRequest): Promise<TokenResponse> {
    return api
      .post('/auth/login', {
        username_or_email: data.username_or_email || data.username || data.email || '',
        password: data.password,
      })
      .then((r) => r.data)
  },

  getMe(): Promise<User> {
    return api.get('/auth/me').then((r) => r.data)
  },

  /** 发送短信验证码 */
  sendSmsCode(data: SendSmsCodeRequest): Promise<{ detail: string }> {
    return api.post('/auth/send-sms-code', data).then((r) => r.data)
  },

  /** 验证短信验证码 */
  verifySmsCode(data: VerifySmsCodeRequest): Promise<{ verified: boolean }> {
    return api.post('/auth/verify-sms-code', data).then((r) => r.data)
  },

  /** 手机号 + 短信验证码登录 */
  phoneLogin(data: PhoneLoginRequest): Promise<PhoneLoginResponse> {
    return api.post('/auth/phone-login', data).then((r) => r.data)
  },

  /** 新用户手机号注册（验证码验证后设置用户名密码） */
  phoneRegister(data: PhoneRegisterRequest): Promise<TokenResponse> {
    return api.post('/auth/phone-register', data).then((r) => r.data)
  },

  /** 忘记密码 - 发送重置链接到邮箱 */
  forgotPassword(data: ForgotPasswordRequest): Promise<{ detail: string }> {
    return api.post('/auth/forgot-password', data).then((r) => r.data)
  },

  /** 重置密码 */
  resetPassword(data: ResetPasswordRequest): Promise<{ detail: string }> {
    return api.post('/auth/reset-password', data).then((r) => r.data)
  },
}