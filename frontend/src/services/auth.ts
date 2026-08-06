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
  WeChatQrUrlResponse,
  WeChatQrLoginRequest,
  WeChatQrStatusResponse,
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

  /** 已登录用户修改密码 */
  changePassword(data: { old_password: string; new_password: string }): Promise<{ detail: string }> {
    return api.post('/auth/change-password', data).then((r) => r.data)
  },

  /** 已登录用户更换手机号（需短信验证） */
  changePhone(data: { new_phone: string; sms_code: string }): Promise<{ detail: string }> {
    return api.post('/auth/change-phone', data).then((r) => r.data)
  },

  /** 微信扫码登录 — 获取二维码 URL */
  getWeChatQrUrl(): Promise<WeChatQrUrlResponse> {
    return api.get('/auth/wechat/qr-url').then((r) => r.data)
  },

  /** 微信扫码登录 — 用 code+state 换取 JWT */
  wechatQrLogin(data: WeChatQrLoginRequest): Promise<TokenResponse> {
    return api.post('/auth/wechat/qr-login', data).then((r) => r.data)
  },

  /** 微信扫码登录 — 轮询扫码状态 */
  getWeChatQrStatus(state: string): Promise<WeChatQrStatusResponse> {
    return api.get(`/auth/wechat/qr-status/${state}`).then((r) => r.data)
  },
}