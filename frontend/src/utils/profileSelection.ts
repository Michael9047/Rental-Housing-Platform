// 清理个人中心中已失效的本地选择状态。
const PROFILE_SELECTION_KEYS = [
  'profile_selected_booking',
  'profile_selected_contract',
  'profile_selected_order',
]

export function clearStaleProfileSelections(): void {
  PROFILE_SELECTION_KEYS.forEach((key) => localStorage.removeItem(key))
}
