// 预订表单控件的实际 DOM、边框责任和提示文字顺序测试。
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { defineComponent, nextTick } from 'vue'
import { describe, expect, it } from 'vitest'

import '@/styles/booking-form-controls.css'

const FormFixture = defineComponent({
  template: `
    <el-form class="booking-form-standard" label-position="top">
      <el-form-item class="date-field birth-date-field" label="出生日期">
        <el-date-picker model-value="2000-07-02" type="date" />
        <div class="help-text">出生日期帮助文字</div>
        <div class="error-text">日期错误</div>
      </el-form-item>
      <el-form-item class="phone-field" label="手机号">
        <div class="phone-row">
          <el-select model-value="+86"><el-option label="中国 +86" value="+86" /></el-select>
          <el-input model-value="13307005844" />
        </div>
        <div class="help-text">手机号帮助文字</div>
        <div class="error-text">手机号错误</div>
      </el-form-item>
    </el-form>
  `,
})

describe('BookingFormControls DOM structure', () => {
  it('日期和手机号 DOM 仅包含组件 wrapper 与内部内容 input', async () => {
    const wrapper = mount(FormFixture, { global: { plugins: [ElementPlus] } })
    await nextTick()

    const dateInner = wrapper.get('.date-field .el-input__inner').element as HTMLElement
    const phoneInner = wrapper.get('.phone-field .el-input__inner').element as HTMLElement
    const phoneRow = wrapper.get('.phone-row').element as HTMLElement

    for (const inner of [dateInner, phoneInner]) {
      expect(inner.classList.contains('el-input__inner')).toBe(true)
      expect(inner.parentElement?.classList.contains('el-input__wrapper')).toBe(true)
    }
    expect(phoneRow.children).toHaveLength(2)
    expect(phoneRow.querySelectorAll('.el-select__wrapper')).toHaveLength(1)
    expect(phoneRow.querySelectorAll('.el-input__wrapper')).toHaveLength(1)
  })

  it('帮助和错误文字位于控件之后并处于正常文档流', async () => {
    const wrapper = mount(FormFixture, { global: { plugins: [ElementPlus] } })
    await nextTick()

    for (const selector of ['.date-field', '.phone-field']) {
      const content = wrapper.get(`${selector} .el-form-item__content`)
      const control = content.element.firstElementChild as HTMLElement
      const helper = content.get('.help-text').element as HTMLElement
      const error = content.get('.error-text').element as HTMLElement
      expect(control.compareDocumentPosition(helper) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(helper.compareDocumentPosition(error) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

      expect(helper.previousElementSibling).not.toBeNull()
      expect(error.previousElementSibling).toBe(helper)
    }
  })

  it('出生日期帮助文字顶部至少位于输入框底部 8px 之后', async () => {
    const wrapper = mount(FormFixture, { global: { plugins: [ElementPlus] } })
    await nextTick()
    const input = wrapper.get('.date-field .el-input__inner').element as HTMLElement
    const helper = wrapper.get('.date-field .help-text').element as HTMLElement
    const inputHeight = Number.parseFloat(getComputedStyle(input).height)
    const helperMarginTop = Number.parseFloat(getComputedStyle(helper).marginTop)
    const inputBottom = inputHeight
    const helperTop = inputHeight + helperMarginTop
    expect(helperTop).toBeGreaterThanOrEqual(inputBottom + 8)
  })
})
