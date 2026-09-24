// 验证租客合同详情只预览已签署 PDF，不再渲染旧合同模板正文。
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MyContractDetail from '@/views/MyContractDetail.vue'

const mocks = vi.hoisted(() => ({
  getMine: vi.fn(),
  getSignedDownloadLink: vi.fn(),
  push: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'agreement-1' } }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/services/contract', () => ({
  contractService: {
    getMine: mocks.getMine,
    getSignedDownloadLink: mocks.getSignedDownloadLink,
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'tenant' } }),
}))

const contract = {
  agreement_id: 'agreement-1', agreement_number: 'A-1', agreement_version: 1,
  agreement_content_hash: 'hash', order_id: 'ORDER-1', booking_id: 1, property_id: 586,
  tenant_user_id: 7, signed_at: '2026-08-12T08:00:00Z', lease_start_date: '2026-08-12',
  lease_end_date: '2026-11-12', lease_months: 3, property_timezone: 'Asia/Singapore',
  property_name: 'studio A', property_address: '新加坡', property_image_url: null,
  payment_status: 'paid', booking_status: 'confirmed', reservation_status: 'contract_signed',
  agreement_status: 'signed', category: 'effective', category_label: '已生效', status_labels: ['已支付'],
  invalid_reason: null, settlement_currency: 'CNY', settlement_amount_minor: 200000,
  payment_expires_at: null, remaining_payment_seconds: null, remaining_contract_days: 90,
  can_pay: false, waiting_for_move_in: false, signed_pdf_available: true,
  content: '合同主体与平台角色', snapshot: { sections: [{ number: 1, title_zh: '合同主体与平台角色' }] },
  signature_url: '/signature.svg',
}

describe('MyContractDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getMine.mockResolvedValue(contract)
    mocks.getSignedDownloadLink.mockResolvedValue({ url: '/api/v1/contracts/signed-download/token' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['pdf'], { type: 'application/pdf' })) }))
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:signed-contract'), revokeObjectURL: vi.fn() })
  })

  it('使用下载文件来源内嵌预览已签署 PDF', async () => {
    const wrapper = mount(MyContractDetail, {
      global: {
        directives: { loading: () => undefined },
        stubs: { 'el-card': { template: '<div><slot /></div>' }, 'el-button': { template: '<button><slot /></button>' }, 'el-tag': { template: '<span><slot /></span>' }, 'el-alert': true, 'el-result': true, 'router-link': { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(mocks.getSignedDownloadLink).toHaveBeenCalledWith('agreement-1')
    expect(fetch).toHaveBeenCalledWith('/api/v1/contracts/signed-download/token', { credentials: 'same-origin' })
    expect(wrapper.find('iframe').attributes('src')).toBe('blob:signed-contract')
    expect(wrapper.text()).toContain('预订成功')
    expect(wrapper.text()).not.toContain('合同主体与平台角色')
    wrapper.unmount()
  })
})
