// 入住日期页面校验成功后的草稿保存与路由跳转测试。
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MoveInDate from '@/views/booking/MoveInDate.vue'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getAvailability: vi.fn(),
  validateDate: vi.fn(),
  getDraft: vi.fn(),
  saveDraft: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { propertyId: '68' } }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/services/property', () => ({
  propertyService: {
    getBookingDateAvailability: mocks.getAvailability,
    validateBookingDate: mocks.validateDate,
  },
}))

vi.mock('@/services/bookingDraft', () => ({
  bookingDraftService: {
    get: mocks.getDraft,
    save: mocks.saveDraft,
  },
}))

describe('MoveInDate', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mocks.getDraft.mockRejectedValue({ response: { status: 404 } })
    mocks.getAvailability.mockResolvedValue({
      property_id: 68,
      timezone: 'Asia/Shanghai',
      local_today: '2026-07-22',
      available_from: null,
      blocked_dates: [],
    })
    mocks.validateDate.mockResolvedValue({
      available: true,
      property_id: 68,
      start_date: '2026-07-23',
      timezone: 'Asia/Shanghai',
      reason: null,
    })
    mocks.saveDraft.mockResolvedValue({})
  })

  it('校验成功后保存草稿并进入租期页面', async () => {
    const wrapper = mount(MoveInDate, {
      global: {
        directives: { loading: () => undefined },
        stubs: {
          BookingFlowLayout: {
            template: '<section><slot/><button data-testid="next" @click="$emit(\'next\')">下一步</button></section>',
          },
          ElSelect: { template: '<div><slot/></div>' },
          ElOption: true,
          ElAlert: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get('[aria-label="2026-07-23"]').trigger('click')
    await wrapper.get('[data-testid="next"]').trigger('click')
    await flushPromises()

    expect(mocks.validateDate).toHaveBeenCalledWith(68, '2026-07-23')
    expect(mocks.saveDraft).toHaveBeenCalledWith(68, {
      move_in_date: '2026-07-23',
      current_step: 'lease_term',
    })
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'booking-lease-term',
      params: { propertyId: '68' },
    })
  })
})
