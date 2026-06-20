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
      config.headers.Authorization = Bearer 
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor: handle 401, show errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
      return Promise.reject(error)
    }
    const detail = error.response?.data?.detail
    if (detail) {
      if (Array.isArray(detail)) {
        detail.forEach((d: { msg: string }) => ElMessage.error(d.msg))
      } else {
        ElMessage.error(detail)
      }
    }
    return Promise.reject(error)
  },
)

export default api
