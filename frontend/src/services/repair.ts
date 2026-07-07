/** 维修系统 API 客户端 */
import api from './api'
import type { RepairCreate, RepairRead, RepairWorker, WorkerCreate, WorkerStatusUpdate } from '@/types/repair'

export const repairService = {
  /** 租客创建报修 */
  create(data: RepairCreate): Promise<RepairRead> {
    return api.post('/repairs', data).then((r) => r.data)
  },

  /** 获取工单列表（按角色自动过滤） */
  list(params?: { status?: string; skip?: number; limit?: number }): Promise<RepairRead[]> {
    return api.get('/repairs', { params }).then((r) => r.data)
  },

  /** 获取单个工单详情 */
  get(id: number): Promise<RepairRead> {
    return api.get(`/repairs/${id}`).then((r) => r.data)
  },

  /** 房东审批/拒绝工单 */
  updateStatus(id: number, newStatus: string): Promise<RepairRead> {
    return api.patch(`/repairs/${id}/status`, null, { params: { new_status: newStatus } }).then((r) => r.data)
  },

  /** 房东指派维修师傅 */
  assignWorker(id: number, workerId: number): Promise<RepairRead> {
    return api.patch(`/repairs/${id}/assign`, null, { params: { worker_id: workerId } }).then((r) => r.data)
  },

  /** 维修师傅开始工作 */
  startWork(id: number): Promise<RepairRead> {
    return api.patch(`/repairs/${id}/start`).then((r) => r.data)
  },

  /** 维修师傅完成工单 */
  completeWork(id: number, workRecord: string): Promise<RepairRead> {
    return api.patch(`/repairs/${id}/complete`, null, { params: { work_record: workRecord } }).then((r) => r.data)
  },

  /** 租客取消报修 */
  cancel(id: number): Promise<RepairRead> {
    return api.patch(`/repairs/${id}/cancel`).then((r) => r.data)
  },
}

export const workerService = {
  /** 房东创建维修师傅 */
  create(data: WorkerCreate): Promise<RepairWorker> {
    return api.post('/repair-workers', data).then((r) => r.data)
  },

  /** 获取维修师傅列表 */
  list(): Promise<RepairWorker[]> {
    return api.get('/repair-workers').then((r) => r.data)
  },

  /** 获取单个维修师傅详情 */
  get(id: number): Promise<RepairWorker> {
    return api.get(`/repair-workers/${id}`).then((r) => r.data)
  },

  /** 编辑维修师傅 */
  update(id: number, data: { phone?: string; skills?: string[] }): Promise<RepairWorker> {
    return api.patch(`/repair-workers/${id}`, data).then((r) => r.data)
  },

  /** 调整维修师傅状态（包括休假） */
  updateStatus(id: number, status: WorkerStatusUpdate): Promise<RepairWorker> {
    return api.patch(`/repair-workers/${id}/status`, status).then((r) => r.data)
  },
}
