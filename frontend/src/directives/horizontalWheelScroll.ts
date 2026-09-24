// 将推荐卡片区域内的垂直鼠标滚轮转换为横向滚动，并在边缘释放页面滚动。
import type { ObjectDirective } from 'vue'

type HorizontalWheelElement = HTMLElement & {
  __horizontalWheelHandler?: (event: WheelEvent) => void
  __horizontalWheelUnlockTimer?: number
}

function wheelDistance(event: WheelEvent, element: HTMLElement): number {
  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 16
  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * element.clientWidth
  return event.deltaY
}

export const vHorizontalWheelScroll: ObjectDirective<HorizontalWheelElement> = {
  mounted(element) {
    const handler = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return

      const distance = wheelDistance(event, element)
      const maxScrollLeft = Math.max(0, element.scrollWidth - element.clientWidth)
      const canScroll = distance < 0
        ? element.scrollLeft > 0
        : element.scrollLeft < maxScrollLeft
      if (!canScroll) return

      event.preventDefault()
      if (element.__horizontalWheelUnlockTimer !== undefined) return

      const firstCard = element.querySelector<HTMLElement>('.rec-card')
      const columnGap = Number.parseFloat(window.getComputedStyle(element).columnGap || '0') || 0
      const cardStep = (firstCard?.getBoundingClientRect().width || element.clientWidth * 0.85) + columnGap
      const direction = distance < 0 ? -1 : 1
      const currentIndex = Math.round(element.scrollLeft / cardStep)
      const target = Math.min(maxScrollLeft, Math.max(0, (currentIndex + direction) * cardStep))

      element.scrollTo({ left: target, behavior: 'smooth' })
      element.__horizontalWheelUnlockTimer = window.setTimeout(() => {
        element.__horizontalWheelUnlockTimer = undefined
      }, 180)
    }

    element.__horizontalWheelHandler = handler
    element.addEventListener('wheel', handler, { passive: false })
  },
  beforeUnmount(element) {
    if (element.__horizontalWheelHandler) {
      element.removeEventListener('wheel', element.__horizontalWheelHandler)
      delete element.__horizontalWheelHandler
    }
    if (element.__horizontalWheelUnlockTimer !== undefined) {
      window.clearTimeout(element.__horizontalWheelUnlockTimer)
    }
  },
}
