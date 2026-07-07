/** 维修工单 Pinia Store */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { repairService, workerService } from '@/services/repair'
import type { RepairRead, RepairWorker, RepairCreate, WorkerStatusUpdate } from '@/types/repair'

export const useRepairStore = defineStore('repair', () => {
  // ── 报修工单 ──
  const repairs = ref<RepairRead[]>([])
  const currentRepair = ref<RepairRead | null>(null)
  const loadingRepairs = ref(false)

  // ── 维修师傅 ──
  const workers = ref<RepairWorker[]>([])
  const loadingWorkers = ref(false)

  // ── 报修 CRUD ──
  async function createRepair(data: RepairCreate): Promise<RepairRead> {
    const repair = await repairService.create(data)
    repairs.value.unshift(repair)
    return repair
  }

  async function fetchMyRepairs(status?: string): Promise<void> {
    loadingRepairs.value = true
    try {
      repairs.value = await repairService.list({ status, limit: 200 })
    } finally {
      loadingRepairs.value = false
    }
  }

  async function fetchRepairDetail(id: number): Promise<void> {
    currentRepair.value = await repairService.get(id)
  }

  async function cancelRepair(id: number): Promise<void> {
    await repairService.cancel(id)
    const idx = repairs.value.findIndex(r => r.id === id)
    if (idx >= 0) repairs.value[idx].status = 'cancelled'
  }

  // ── 房东操作 ──
  async function approveRepair(id: number): Promise<RepairRead> {
    return await repairService.updateStatus(id, 'approved')
  }

  async function rejectRepair(id: number): Promise<RepairRead> {
    return await repairService.updateStatus(id, 'rejected')
  }

  async function assignWorker(id: number, workerId: number): Promise<RepairRead> {
    return await repairService.assignWorker(id, workerId)
  }

  // ── 维修师傅操作 ──
  async function startWork(id: number): Promise<RepairRead> {
    return await repairService.startWork(id)
  }

  async function completeWork(id: number, record: string): Promise<RepairRead> {
    return await repairService.completeWork(id, record)
  }

  // ── 维修师傅管理 ──
  async function fetchWorkers(): Promise<void> {
    loadingWorkers.value = true
    try {
      workers.value = await workerService.list()
    } finally {
      loadingWorkers.value = false
    }
  }

  async function createWorker(data: { username: string; password: string; phone: string; skills?: string[] }): Promise<RepairWorker> {
    const w = await workerService.create(data)
    workers.value.push(w)
    return w
  }

  async function updateWorkerStatus(workerId: number, status: WorkerStatusUpdate): Promise<RepairWorker> {
    return await workerService.updateStatus(workerId, status)
  }

  return {
    repairs, currentRepair, loadingRepairs,
    workers, loadingWorkers,
    createRepair, fetchMyRepairs, fetchRepairDetail, cancelRepair,
    approveRepair, rejectRepair, assignWorker,
    startWork, completeWork,
    fetchWorkers, createWorker, updateWorkerStatus,
  }
})
