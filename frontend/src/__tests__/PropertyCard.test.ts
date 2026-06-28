import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import PropertyCard from '@/components/PropertyCard.vue'
import type { Property } from '@/types/property'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

const mockPush = vi.fn()

const baseProperty: Property = {
  id: 1, landlord_id: 1,
  title: "Sunny Apartment near Metro",
  description: "A beautiful apartment with great natural light.",
  address: "88 University Road, SIP",
  district: "工业园区",
  price_monthly: 5200, area_sqm: 72.5,
  bedrooms: 2, bathrooms: 1,
  property_type: "apartment", status: "available",
  latitude: 31.3157, longitude: 120.7435,
  deposit_amount: 5200, service_fee_rate: 0.5,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  images: [], primary_image_url: null,
}

function createWrapper(overrides: any = {}, props: any = {}) {
  const property = { ...baseProperty, ...overrides }
  return mount(PropertyCard, {
    props: { property, ...props },
    global: {
      plugins: [ElementPlus],
      mocks: { "$router": { push: mockPush } },
    },
  })
}

describe("PropertyCard", () => {
  it("renders property title", () => {
    const wrapper = createWrapper()
    expect(wrapper.find(".card-title").text()).toContain("Sunny Apartment")
  })

  it("renders price", () => {
    const wrapper = createWrapper()
    expect(wrapper.find(".card-price").text()).toContain("5200")
  })

  it("renders district tag", () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain("工业园区")
  })

  it("renders bedroom/bathroom count", () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain("2室1卫")
  })

  it("shows image placeholder when no images", () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain("暂无图片")
  })

  it("shows similarity when enabled", () => {
    const wrapper = createWrapper({ similarity: 0.85 }, { showSimilarity: true })
    expect(wrapper.text()).toContain("85%")
  })

  it("does not show similarity when disabled", () => {
    const wrapper = createWrapper({ similarity: 0.85 })
    expect(wrapper.text()).not.toContain("匹配度")
  })

  it("renders area when available", () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain("72.5")
  })
})