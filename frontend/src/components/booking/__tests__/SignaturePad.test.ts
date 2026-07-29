// Pointer Events 手写签名、触控防滚动、撤销和清除测试。
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SignaturePad from '@/components/booking/SignaturePad.vue'

const context = { setTransform: vi.fn(), clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(), lineCap: '', lineJoin: '', strokeStyle: '', lineWidth: 0 }
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as any)
  vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 600, height: 220, right: 600, bottom: 220, x: 0, y: 0, toJSON() {} })
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  HTMLCanvasElement.prototype.setPointerCapture = vi.fn(); HTMLCanvasElement.prototype.releasePointerCapture = vi.fn(); HTMLCanvasElement.prototype.hasPointerCapture = vi.fn(() => true)
})

function pointer(type: string, x: number, y: number, pointerType = 'mouse') {
  const event = new Event(type, { bubbles: true, cancelable: true }) as any
  Object.assign(event, { clientX: x, clientY: y, pointerId: 1, pointerType, button: 0, pressure: .5 })
  return event
}

describe('SignaturePad', () => {
  it.each(['mouse', 'touch', 'pen'])('支持 %s Pointer Events 笔迹', async (pointerType) => {
    const wrapper = mount(SignaturePad, { global: { plugins: [ElementPlus] } }); const canvas = wrapper.find('canvas')
    await canvas.element.dispatchEvent(pointer('pointerdown', 20, 30, pointerType)); await canvas.element.dispatchEvent(pointer('pointermove', 180, 90, pointerType)); await canvas.element.dispatchEvent(pointer('pointerup', 240, 120, pointerType))
    expect(wrapper.emitted('change')?.[0]?.[0]).toHaveLength(1); wrapper.unmount()
  })

  it('触控绘制会阻止页面滚动，且支持撤销和清除', async () => {
    const wrapper = mount(SignaturePad, { global: { plugins: [ElementPlus] } }); const canvas = wrapper.find('canvas'); const down = pointer('pointerdown', 10, 10, 'touch')
    canvas.element.dispatchEvent(down); canvas.element.dispatchEvent(pointer('pointermove', 200, 100, 'touch')); canvas.element.dispatchEvent(pointer('pointerup', 220, 120, 'touch'))
    expect(down.defaultPrevented).toBe(true); (wrapper.vm as any).undo(); (wrapper.vm as any).clear(); const changes = wrapper.emitted('change') || []; expect(changes[changes.length - 1]?.[0]).toEqual([]); wrapper.unmount()
  })
})
