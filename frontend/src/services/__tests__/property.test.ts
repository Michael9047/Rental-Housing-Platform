import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  default: { get: getMock },
}))

import { propertyService } from '@/services/property'

describe('propertyService.search', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockResolvedValue({ data: [] })
  })

  it('把精确公寓和设施条件传给 Building 搜索接口', async () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(123456)

    await propertyService.search({
      institute_id: 37,
      price_min: 2000,
      price_max: 3000,
      property_type: 'studio',
      amenities: ['WiFi', '空调'],
    })

    expect(getMock).toHaveBeenCalledWith('/buildings/public/search', {
      params: {
        institute_id: 37,
        price_min: 2000,
        price_max: 3000,
        property_type: 'studio',
        amenities: ['WiFi', '空调'],
        _t: 123456,
      },
      paramsSerializer: { indexes: null },
    })

    now.mockRestore()
  })
})
