// 推荐卡片横向滚轮指令的滚动与边缘释放回归测试。
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { vHorizontalWheelScroll } from '@/directives/horizontalWheelScroll'

function createScrollableRow() {
  const wrapper = mount(defineComponent({
    directives: { HorizontalWheelScroll: vHorizontalWheelScroll },
    template: '<div v-horizontal-wheel-scroll class="row"><article class="rec-card" /></div>',
  }))
  const row = wrapper.get('.row').element as HTMLElement
  Object.defineProperty(row, 'scrollWidth', { configurable: true, value: 900 })
  Object.defineProperty(row, 'clientWidth', { configurable: true, value: 300 })
  const card = row.querySelector('.rec-card') as HTMLElement
  vi.spyOn(card, 'getBoundingClientRect').mockReturnValue({ width: 240 } as DOMRect)
  const scrollTo = vi.fn(({ left }: ScrollToOptions) => { row.scrollLeft = Number(left) })
  row.scrollTo = scrollTo
  return { wrapper, row, scrollTo }
}

describe('vHorizontalWheelScroll', () => {
  afterEach(() => vi.useRealTimers())

  it('一次垂直滚轮翻阅一张完整卡片', () => {
    const { wrapper, row, scrollTo } = createScrollableRow()
    const event = new WheelEvent('wheel', { deltaY: 120, cancelable: true })

    row.dispatchEvent(event)

    expect(scrollTo).toHaveBeenCalledWith({ left: 240, behavior: 'smooth' })
    expect(row.scrollLeft).toBe(240)
    expect(event.defaultPrevented).toBe(true)
    wrapper.unmount()
  })

  it('同一次滚轮手势期间不会连续跳过多张卡片', () => {
    vi.useFakeTimers()
    const { wrapper, row, scrollTo } = createScrollableRow()

    row.dispatchEvent(new WheelEvent('wheel', { deltaY: 120, cancelable: true }))
    row.dispatchEvent(new WheelEvent('wheel', { deltaY: 120, cancelable: true }))
    expect(scrollTo).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(180)
    row.dispatchEvent(new WheelEvent('wheel', { deltaY: 120, cancelable: true }))
    expect(scrollTo).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('到达滚动边缘后不阻止页面继续滚动', () => {
    const { wrapper, row } = createScrollableRow()
    row.scrollLeft = 600
    const event = new WheelEvent('wheel', { deltaY: 120, cancelable: true })

    row.dispatchEvent(event)

    expect(row.scrollLeft).toBe(600)
    expect(event.defaultPrevented).toBe(false)
    wrapper.unmount()
  })

  it('保留触控板原生横向滚动事件', () => {
    const { wrapper, row } = createScrollableRow()
    const event = new WheelEvent('wheel', { deltaX: 120, deltaY: 20, cancelable: true })

    row.dispatchEvent(event)

    expect(row.scrollLeft).toBe(0)
    expect(event.defaultPrevented).toBe(false)
    wrapper.unmount()
  })
})
