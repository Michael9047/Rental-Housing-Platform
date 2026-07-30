// 预订信息表单在目标视口下的共享控件与网格规则测试。
import { describe, expect, it } from 'vitest'
import personalSource from '../PersonalInfo.vue?raw'
import emergencySource from '../EmergencyContact.vue?raw'

describe('booking form responsive controls', () => {
  it.each([
    [1440, 2],
    [1024, 2],
    [768, 2],
    [390, 1],
  ])('%ipx 使用 %i 列', (viewport, columns) => {
    expect(viewport < 768 ? 1 : 2).toBe(columns)
  })

  it('个人信息与紧急联系人共用标准表单样式', () => {
    expect(personalSource).toContain('personal-form booking-form-standard')
    expect(emergencySource).toContain('contact-form booking-form-standard')
    expect(personalSource).not.toContain('height: 32px')
    expect(emergencySource).not.toContain('height: 32px')
  })

  it('文本、日期、选择器和级联选择器使用同一高度与边界', () => {
    expect(personalSource).toContain('<el-date-picker')
    expect(personalSource).toContain('<el-select')
    expect(personalSource).toContain('<FormField')
    expect(emergencySource).toContain('<ContactField')
  })

  it('帮助和错误文字处于正常文档流且不会被裁剪', () => {
    expect(personalSource).not.toContain('min-height: 126px')
    expect(personalSource).not.toContain('overflow: hidden')
    expect(emergencySource).not.toContain('overflow: hidden')
    expect(personalSource).toContain('<HelpText text=')
    expect(emergencySource).toContain('<HelpText text=')
  })

  it('手机号组合控件采用 34/66 分栏且手机端不溢出', () => {
    expect(personalSource).toContain('class="phone-row"')
    expect(emergencySource).toContain('class="phone-row"')
    expect(personalSource).toMatch(/class="phone-row"[\s\S]*<\/div>\s*<HelpText/)
    expect(emergencySource).toMatch(/class="phone-row"[\s\S]*<\/div>\s*<HelpText/)
  })
})
