// Matches backend: app/schemas/auth.py RegisterRequest / LoginRequest / TokenResponse
import type { UserRole } from './user'

export interface RegisterRequest {
  username: string
  password: string
  phone?: string
  sms_code?: string
  email?: string
  role?: UserRole
}

export interface LoginRequest {
  username_or_email?: string
  username?: string
  email?: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

/** 手机号 + 短信验证码登录请求 */
export interface PhoneLoginRequest {
  phone: string
  sms_code: string
}

/** 手机号登录响应 */
export interface PhoneLoginResponse {
  access_token: string | null
  token_type: string
  is_new_user: boolean
  phone: string
}

/** 新用户手机号注册（phone-login 验证通过后设置用户名密码，无需再次提交验证码） */
export interface PhoneRegisterRequest {
  phone: string
  username: string
  password: string
  role?: UserRole
}

/** 发送短信验证码请求 */
export interface SendSmsCodeRequest {
  phone: string
}

/** 验证短信验证码请求 */
export interface VerifySmsCodeRequest {
  phone: string
  code: string
}

/** 忘记密码 - 发送重置链接 */
export interface ForgotPasswordRequest {
  email: string
}

/** 重置密码 */
export interface ResetPasswordRequest {
  token: string
  new_password: string
}
