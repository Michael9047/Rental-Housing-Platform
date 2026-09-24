// 同步一轮推荐卡片中的推荐理由高度，按最长内容自适应且不截断文字。
import type { ObjectDirective } from 'vue'

type SyncElement = HTMLElement & {
  __syncMatchReasonFrame?: number
}

function syncMatchReasonHeights(element: SyncElement): void {
  if (element.__syncMatchReasonFrame !== undefined) {
    window.cancelAnimationFrame(element.__syncMatchReasonFrame)
  }

  element.__syncMatchReasonFrame = window.requestAnimationFrame(() => {
    const reasons = Array.from(element.querySelectorAll<HTMLElement>('.match-reason'))
    reasons.forEach((reason) => { reason.style.height = 'auto' })

    const tallest = Math.max(0, ...reasons.map((reason) => reason.scrollHeight))
    if (tallest > 0) {
      reasons.forEach((reason) => { reason.style.height = `${tallest}px` })
    }
    element.__syncMatchReasonFrame = undefined
  })
}

export const vSyncMatchReasonHeights: ObjectDirective<SyncElement> = {
  mounted: syncMatchReasonHeights,
  updated: syncMatchReasonHeights,
  beforeUnmount(element) {
    if (element.__syncMatchReasonFrame !== undefined) {
      window.cancelAnimationFrame(element.__syncMatchReasonFrame)
    }
  },
}
