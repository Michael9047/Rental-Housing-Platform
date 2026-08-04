import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,  // 60s，导入/上传等耗时操作需要较长超时
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach Authorization header
api.interceptors.request.use(
  (config) => {
    // 登录/注册/刷新 token 等公开接口不附加旧 token
    const path = config.url || ''
    const isPublic = path.includes('/auth/login') || path.includes('/auth/register')
      || path.includes('/auth/refresh') || path.includes('/auth/phone')
      || path.includes('/auth/send-sms') || path.includes('/auth/verify-sms')
    if (!isPublic) {
      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Helper: extract error message from backend's {error:{message:"..."}} format
// or standard {detail:"..."} format (both are used in this project)
export function extractErrorMessage(error: any): string | null {
  const data = error.response?.data

  // Backend format: { error: { message: "..." } }
  const msg = data?.error?.message
  if (msg && typeof msg === 'string') return msg

  // Standard FastAPI format: { detail: "..." }
  const detail = data?.detail
  if (detail && typeof detail === 'string') return detail

  // FastAPI validation errors (array format)
  if (Array.isArray(detail) && detail.length > 0) {
    const locs = detail.map((d: any) => {
      const field = (d.loc || []).filter((l: string) => l !== 'body' && l !== 'path' && l !== 'query').join('.')
      return field ? `${field}: ${d.msg}` : d.msg
    }).filter(Boolean)
    if (locs.length > 0) return locs.join('; ')
  }

  // Raw validation error list (non-array detail, e.g. direct list)
  if (Array.isArray(data) && data.length > 0 && data[0].msg) {
    const locs = data.map((d: any) => {
      const field = (d.loc || []).filter((l: string) => l !== 'body' && l !== 'path' && l !== 'query').join('.')
      return field ? `${field}: ${d.msg}` : d.msg
    }).filter(Boolean)
    if (locs.length > 0) return locs.join('; ')
  }

  // Plain string response
  if (typeof data === 'string' && data) return data

  return null
}

// Response interceptor: handle 401, show errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginPage = window.location.pathname === '/login'
    const hadToken = !!localStorage.getItem('access_token')

    if (error.response?.status === 401) {
      // 仅在用户之前已登录（有过 token）的情况下才跳转登录页
      // 未登录用户浏览公开内容时遇到 401 静默处理，不强制跳转
      if (!isLoginPage && hadToken) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
      const message = extractErrorMessage(error)
      if (message) ElMessage.error(message)
      return Promise.reject(error)
    }
    // 404 不弹全局错误——由调用方自行处理（如草稿不存在属正常流程）
    if (error.response?.status === 404) {
      return Promise.reject(error)
    }
    const message = extractErrorMessage(error)
    if (message) ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default api