// 公寓与户型生命周期状态的统一展示和操作规则。
export type ListingKind = 'building' | 'unitType'

const labels: Record<ListingKind, Record<string, string>> = {
  building: { pending: '待完善', active: '已上架', offline: '已下架', suspended: '回收站' },
  unitType: { available: '可租', offline: '已下架', maintenance: '维护中', rented: '已租' },
}

export function listingStatusLabel(kind: ListingKind, status?: string): string {
  return labels[kind][status || ''] || status || '未知'
}

export function listingStatusTag(status?: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'active' || status === 'available') return 'success'
  if (status === 'offline') return 'warning'
  if (status === 'suspended') return 'danger'
  return 'info'
}

export function listingPrimaryAction(status?: string): 'offline' | 'publish' | null {
  if (status === 'active' || status === 'available') return 'offline'
  if (status === 'offline' || status === 'pending' || status === 'maintenance') return 'publish'
  return null
}

export function parentVisibilityHint(buildingStatus?: string): string {
  return buildingStatus === 'active' ? '' : '公寓已下架，前台不可见'
}
