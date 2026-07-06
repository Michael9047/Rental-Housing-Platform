import api from './api'
import type { AdminStats, AuditLog, EmbeddingStats, ImportResult, ImportTask, ImportTaskDetail } from '@/types/admin'
import type { User } from '@/types/user'

export const adminService = {
  getStats(): Promise<AdminStats> {
    return api.get('/admin/stats').then((r) => r.data)
  },

  getLogs(params?: {
    skip?: number
    limit?: number
    action?: string
    user_id?: number
  }): Promise<AuditLog[]> {
    return api.get('/admin/logs', { params }).then((r) => r.data)
  },

  moderateProperty(propertyId: number, new_status: string): Promise<void> {
    return api.patch(`/admin/properties/${propertyId}/status`, null, {
      params: { new_status },
    })
  },

  updateUserRole(userId: number, new_role: string): Promise<User> {
    return api.patch(`/admin/users/${userId}/role`, null, {
      params: { new_role },
    }).then((r) => r.data)
  },

  getEmbeddingStats(): Promise<EmbeddingStats> {
    return api.get('/admin/embeddings/stats').then((r) => r.data)
  },

  triggerReindex(propertyId?: number): Promise<void> {
    return api.post('/admin/embeddings/reindex', null, {
      params: propertyId ? { property_id: propertyId } : {},
    })
  },

  // ---- Import ----
  uploadImport(file: File, instituteId?: number): Promise<ImportResult> {
    const formData = new FormData()
    formData.append('file', file)
    const params = instituteId ? { institute_id: instituteId } : {}
    return api.post('/import/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    }).then((r) => r.data)
  },

  /** 下载 Excel 导入模板 */
  downloadTemplate(): Promise<Blob> {
    return api.get('/import/template', { responseType: 'blob' }).then((r) => r.data)
  },

  /** 下载错误行 Excel */
  downloadErrorTable(taskId: number): Promise<Blob> {
    return api.get(`/import/tasks/${taskId}/errors/download`, { responseType: 'blob' }).then((r) => r.data)
  },

  getImportTasks(params?: {
    skip?: number
    limit?: number
    status?: string
  }): Promise<ImportTask[]> {
    return api.get('/import/tasks', { params }).then((r) => r.data)
  },

  getImportTaskDetail(taskId: number): Promise<ImportTaskDetail> {
    return api.get(`/import/tasks/${taskId}`).then((r) => r.data)
  },

  retryImportTask(taskId: number): Promise<ImportResult> {
    return api.post(`/import/tasks/${taskId}/retry`).then((r) => r.data)
  },
}
