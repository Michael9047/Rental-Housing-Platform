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
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Helper: extract error message from backend's {error:{message:"..."}} format
// or standard {detail:"..."} format (both are used in this project)
export function extractErrorMessage(error: any): string | null {
  // Backend format: { error: { message: "..." } }
  const msg = error.response?.data?.error?.message
  if (msg && typeof msg === 'string') return msg
  // Standard FastAPI format: { detail: "..." }
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'string') return detail
  // Array of validation errors
  if (Array.isArray(detail)) {
    return detail.map((d: any) => d.msg || '').filter(Boolean).join('; ')
  }
  return null
}

// Response interceptor: handle 401, show errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginPage = window.location.pathname === '/login'

    if (error.response?.status === 401) {
      // Don't redirect during login attempt - just show the error
      if (!isLoginPage) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
      const message = extractErrorMessage(error)
      if (message) ElMessage.error(message)
      return Promise.reject(error)
    }
    const message = extractErrorMessage(error)
    if (message) ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default api