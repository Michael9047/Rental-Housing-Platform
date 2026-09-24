// 验证个人中心采用精简平铺布局，同时保留现有详情页路由入口。
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const profileSource = readFileSync('src/views/Profile.vue', 'utf8')

describe('个人中心精简布局', () => {
  it('合同和订单全部平铺，不再显示分类筛选及重复状态行', () => {
    expect(profileSource).toContain('label="💳 我的订单"')
    expect(profileSource).not.toContain('我的账单 / 订单')
    expect(profileSource).toContain('v-for="row in contracts"')
    expect(profileSource).toContain('v-for="order in orders"')
    expect(profileSource).not.toContain('contractFilter')
    expect(profileSource).not.toContain('billTab')
    expect(profileSource).not.toContain('contract-tags')
    expect(profileSource).not.toContain('order-tags')
  })

  it('订单卡片进入现有详情页，卡片内操作阻止重复跳转', () => {
    expect(profileSource).toContain('@click="router.push(`/my-orders/${order.booking_id}`)"')
    expect(profileSource).toContain('class="contract-actions" @click.stop @keydown.stop')
    expect(profileSource).toContain('router.push(`/my-contracts/${row.agreement_id}`)')
  })

  it('我的信息字段与七步流程的申请人和紧急联系人保持一致', () => {
    for (const field of ['phone_country_code', 'region', 'address_detail', 'postal_code']) {
      expect(profileSource).toContain(`tenantForm.${field}`)
    }
    for (const field of ['emergency_chinese_name', 'emergency_relation', 'emergency_phone_country_code', 'emergency_address_detail', 'emergency_consultant_id']) {
      expect(profileSource).toContain(`tenantForm.${field}`)
    }
    expect(profileSource).not.toContain('tenantForm.visa_type')
  })
})
