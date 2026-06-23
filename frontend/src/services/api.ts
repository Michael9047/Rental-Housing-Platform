import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
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
      // Still show the error message
      const detail = error.response?.data?.detail
      if (detail && typeof detail === 'string') {
        ElMessage.error(detail)
      }
      return Promise.reject(error)
    }
    const detail = error.response?.data?.detail
    if (detail) {
      if (Array.isArray(detail)) {
        detail.forEach((d: { msg: string }) => ElMessage.error(d.msg))
      } else if (typeof detail === 'string') {
        ElMessage.error(detail)
      }
    }
    return Promise.reject(error)
  },
)

export default api