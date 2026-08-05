import api from './api'
import type {
  AdminOverview,
  AdminStats,
  AuditLog,
  EmbeddingStats,
  ImportResult,
  ImportTask,
  ImportTaskDetail,
  NotificationOutboxItem,
  RowResult,
  SystemAlert,
  SystemAlertProcessRecord,
} from '@/types/admin'
import type { Property } from '@/types/property'
import type { User } from '@/types/user'

export const adminService = {
  getOverview(): Promise<AdminOverview> {
    return api.get('/admin/overview').then((r) => r.data)
  },

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

  /** 获取待审核房源列表 */
  getPendingProperties(): Promise<Property[]> {
    return api.get('/admin/properties/pending').then((r) => r.data)
  },

  updateUserRole(userId: number, new_role: string): Promise<User> {
    return api.patch(`/admin/users/${userId}/role`, null, {
      params: { new_role },
    }).then((r) => r.data)
  },

  getFailedNotifications(): Promise<NotificationOutboxItem[]> {
    return api.get('/notifications/admin/outbox').then((r) => r.data)
  },

  getSystemAlerts(): Promise<SystemAlert[]> {
    return api.get('/admin/system-alerts').then((r) => r.data)
  },

  getSystemAlertRecords(params?: {
    alert_key?: string
    keyword?: string
    category?: string
    action_type?: string
    source?: string
    source_id?: string
    limit?: number
  }): Promise<SystemAlertProcessRecord[]> {
    return api.get('/admin/system-alerts/records', { params }).then((r) => r.data)
  },

  retryNotification(outboxId: string): Promise<{ id: string; status: string }> {
    return api.post(`/notifications/admin/outbox/${outboxId}/retry`).then((r) => r.data)
  },

  triggerPmsSync(connectionId: number): Promise<Record<string, unknown>> {
    return api.post(`/pms/connections/${connectionId}/sync`).then((r) => r.data)
  },

  resolveSystemAlert(alertId: number, note?: string): Promise<{ id: number; status: string }> {
    return api.patch(`/admin/system-alerts/${alertId}/resolve`, { note }).then((r) => r.data)
  },

  resolveGeneratedSystemAlert(alert: SystemAlert, note?: string): Promise<{ id: number; alert_key: string; status: string }> {
    return api.patch('/admin/system-alerts/generated/resolve', {
      alert_key: alert.id,
      category: alert.category,
      severity: alert.severity,
      title: alert.title,
      source: alert.source,
      source_id: alert.source_id,
      status: alert.status,
      detail: alert.detail,
      note,
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
  /** 预览：解析文件 + 校验 + IQR/孤立森林，不入库 */
  previewImport(file: File, instituteId?: number): Promise<{preview_id: number; total_records: number; rows: RowResult[]}> {
    const fd = new FormData(); fd.append('file', file)
    const params: Record<string, any> = {}
    if (instituteId) params.institute_id = instituteId
    return api.post('/import/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' }, params }).then(r => r.data)
  },

  /** 确认导入：传入预览 ID + 忽略行号列表 */
  confirmImport(previewId: number, skipRows: number[]): Promise<ImportResult> {
    return api.post(`/import/confirm/${previewId}`, { skip_rows: skipRows }).then(r => r.data)
  },

  uploadImport(file: File, instituteId?: number, mode?: string): Promise<ImportResult> {
    const formData = new FormData()
    formData.append('file', file)
    const params: Record<string, any> = {}
    if (instituteId) params.institute_id = instituteId
    if (mode) params.mode = mode
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
