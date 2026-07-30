// Stub — PR #30 合入后替换
import { ref } from 'vue'
export function useProfileTab() { const tab = ref('orders'); return { tab } }
export function clearStaleProfileSelections(): void {}
