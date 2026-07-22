// 信息确认页协议弹窗的内容、关闭与同意状态隔离测试。
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import PolicyDialog from '@/components/booking/PolicyDialog.vue'

const documents = [
  ['booking-authorization', '《订房授权书》'],
  ['cross-border-data', '《个人信息出境授权声明》'],
  ['privacy', '《隐私政策》'],
  ['cancellation', '《公寓退订政策》'],
] as const

function mountDialog(key: string, title: string) {
  return mount(PolicyDialog, {
    attachTo: document.body,
    props: {
      modelValue: true,
      document: { key, title, version: '2026.1', content_hash: 'hash', content: `${title}正文` },
    },
    global: { plugins: [ElementPlus] },
  })
}

describe('PolicyDialog', () => {
  it.each(documents)('显示 %s 对应正文', async (key, title) => {
    const wrapper = mountDialog(key, title)
    await nextTick()
    expect(document.body.textContent).toContain(title)
    expect(document.body.textContent).toContain(`${title}正文`)
    expect(document.body.querySelector('[role="dialog"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('关闭按钮只关闭弹窗，不产生同意事件', async () => {
    const wrapper = mountDialog(...documents[0])
    await nextTick()
    const closeButton = [...document.body.querySelectorAll('button')].find((button) => button.textContent?.trim() === '关闭') as HTMLButtonElement
    closeButton.click()
    await nextTick()
    const updates = wrapper.emitted('update:modelValue') || []
    expect(updates[updates.length - 1]).toEqual([false])
    expect(wrapper.emitted('accepted')).toBeUndefined()
    wrapper.unmount()
  })

  it('Esc 可以关闭且正文区域可独立滚动', async () => {
    const wrapper = mountDialog(...documents[1])
    await nextTick()
    const content = document.body.querySelector('.policy-content') as HTMLElement
    expect(getComputedStyle(content).overflowY).toBe('auto')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }))
    await nextTick()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    wrapper.unmount()
  })
})
