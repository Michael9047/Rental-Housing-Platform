/** 维修系统前端类型定义 */

export type RepairIssueType =
  | 'plumbing'
  | 'appliance'
  | 'carpentry'
  | 'wall_floor'
  | 'plumbing_fixture'
  | 'other'

export type RepairStatus =
  | 'pending'
  | 'assigned'
  | 'in_progress'
  | 'completed'
  | 'rejected'
  | 'cancelled'

export type WorkerStatus = 'available' | 'working' | 'on_leave'

export interface RepairCreate {
  property_id: number
  issue_type: RepairIssueType
  description: string
  images?: string[]
  scheduled_time?: string
}

export interface RepairRead {
  id: number
  property_id: number
  tenant_id: number
  landlord_id: number
  assigned_worker_id: number | null
  issue_type: RepairIssueType
  description: string
  images: string[] | null
  status: RepairStatus
  scheduled_time: string | null
  completed_at: string | null
  work_record: string | null
  work_images: string[] | null
  created_at: string
  updated_at: string
  tenant_name: string | null
  landlord_name: string | null
  worker_name: string | null
  property_title: string | null
}

export interface RepairWorker {
  id: number
  user_id: number
  manager_id: number
  status: WorkerStatus
  skills: string[] | null
  phone: string
  total_jobs: number
  rating: number
  created_at: string
  username: string | null
}

export interface WorkerCreate {
  username: string
  password: string
  phone: string
  skills?: string[]
}

export interface WorkerStatusUpdate {
  status: WorkerStatus
}

export const ISSUE_TYPE_LABELS: Record<RepairIssueType, string> = {
  plumbing: '水电',
  appliance: '家电',
  carpentry: '门窗',
  wall_floor: '墙面地面',
  plumbing_fixture: '管道',
  other: '其他',
}

export const REPAIR_STATUS_LABELS: Record<RepairStatus, string> = {
  pending: '待处理',
  assigned: '已派单',
  in_progress: '维修中',
  completed: '已完成',
  rejected: '已拒绝',
  cancelled: '已取消',
}

export const REPAIR_STATUS_TAGS: Record<RepairStatus, string> = {
  pending: 'danger',
  assigned: 'warning',
  in_progress: '',
  completed: 'success',
  rejected: 'info',
  cancelled: 'info',
}
