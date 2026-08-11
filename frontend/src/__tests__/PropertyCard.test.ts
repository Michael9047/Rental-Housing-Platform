import { beforeEach, describe, it, expect, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import PropertyCard from '@/components/PropertyCard.vue'
import { agentService } from '@/services/agent'
import type { Property } from '@/types/property'

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
  useRoute: () => ({ params: {}, query: {}, fullPath: '/search?country=SG' }),
}))

vi.mock('@/router', () => ({
  default: { push: vi.fn() },
}))

const baseProperty = {
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
} as Property

function createWrapper(overrides: any = {}, props: any = {}) {
  const property = { ...baseProperty, ...overrides }
  return mount(PropertyCard, {
    props: { property, entity: 'unit-type', ...props },
    global: {
      plugins: [createPinia(), ElementPlus],
    },
  })
}

describe("PropertyCard", () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    vi.clearAllMocks()
  })

  it("renders property title", () => {
    const wrapper = createWrapper()
    expect(wrapper.find(".card-title").text()).toContain("Sunny Apartment")
  })

  it("renders price", () => {
    const wrapper = createWrapper()
    expect(wrapper.find(".card-price").text()).toContain("5,200")
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

  it("never exposes or calls UnitType cart APIs for a Building card without a representative UnitType", async () => {
    localStorage.setItem('access_token', 'tenant-token')
    localStorage.setItem('user', JSON.stringify({ id: 1, role: 'tenant' }))
    const addSpy = vi.spyOn(agentService, 'addCartItem')
    const removeSpy = vi.spyOn(agentService, 'removeCartItem')
    const wrapper = createWrapper({ id: 7, institute_id: 99 }, { entity: 'building' })

    expect(wrapper.find('.add-cart-btn').exists()).toBe(false)
    await wrapper.trigger('click')
    for (const button of wrapper.findAll('button')) await button.trigger('click')

    expect(addSpy).not.toHaveBeenCalled()
    expect(removeSpy).not.toHaveBeenCalled()
  })

  it("uses the representative UnitType ID when a Building card adds and removes a candidate", async () => {
    localStorage.setItem('access_token', 'tenant-token')
    localStorage.setItem('user', JSON.stringify({ id: 1, role: 'tenant' }))
    const addSpy = vi.spyOn(agentService, 'addCartItem').mockResolvedValue({
      id: 1,
      property_id: 42,
      property: { ...baseProperty, id: 42 },
    } as any)
    const removeSpy = vi.spyOn(agentService, 'removeCartItem').mockResolvedValue()
    const wrapper = createWrapper(
      { id: 7, institute_id: 7, representative_unit_type_id: 42 },
      { entity: 'building' },
    )

    expect(wrapper.find('.add-cart-btn').exists()).toBe(true)
    await wrapper.find('.add-cart-btn').trigger('click')
    await flushPromises()

    expect(addSpy).toHaveBeenCalledOnce()
    expect(addSpy).toHaveBeenCalledWith(42, undefined)
    expect(addSpy).not.toHaveBeenCalledWith(7, undefined)
    expect(wrapper.find('.add-cart-btn').classes()).toContain('is-added')

    await wrapper.find('.add-cart-btn').trigger('click')
    await flushPromises()

    expect(removeSpy).toHaveBeenCalledOnce()
    expect(removeSpy).toHaveBeenCalledWith(42)
  })

  it("shows the Building candidate button to guests and redirects before calling cart APIs", async () => {
    const addSpy = vi.spyOn(agentService, 'addCartItem')
    const removeSpy = vi.spyOn(agentService, 'removeCartItem')
    const wrapper = createWrapper(
      { id: 7, institute_id: 7, representative_unit_type_id: 42 },
      { entity: 'building' },
    )

    expect(wrapper.find('.add-cart-btn').exists()).toBe(true)
    expect(wrapper.find('.add-cart-btn').attributes('aria-label')).toBe('登录后加入候选清单')
    await wrapper.find('.add-cart-btn').trigger('click')
    await flushPromises()

    expect(routerPush).toHaveBeenCalledWith({
      name: 'login',
      query: { redirect: '/search?country=SG' },
    })
    expect(addSpy).not.toHaveBeenCalled()
    expect(removeSpy).not.toHaveBeenCalled()
  })

  it("uses the declared UnitType ID when adding a UnitType card to the cart", async () => {
    localStorage.setItem('access_token', 'tenant-token')
    localStorage.setItem('user', JSON.stringify({ id: 1, role: 'tenant' }))
    const addSpy = vi.spyOn(agentService, 'addCartItem').mockResolvedValue({
      id: 1,
      property_id: 7,
      property: { ...baseProperty, id: 7 },
    } as any)
    const wrapper = createWrapper({ id: 7, institute_id: 99 }, { entity: 'unit-type' })

    await wrapper.find('.add-cart-btn').trigger('click')

    expect(addSpy).toHaveBeenCalledOnce()
    expect(addSpy).toHaveBeenCalledWith(7, undefined)
  })

  it("uses the Building ID for Building detail even when institute_id differs", async () => {
    const wrapper = createWrapper({ id: 7, institute_id: 99 }, { entity: 'building' })

    await wrapper.trigger('click')

    expect(routerPush).toHaveBeenCalledWith({
      name: 'building-detail',
      params: { id: '7' },
      query: {},
    })
  })

  it("uses Institute ID plus UnitType query for UnitType detail", async () => {
    const wrapper = createWrapper({ id: 7, institute_id: 99 }, { entity: 'unit-type' })

    await wrapper.trigger('click')

    expect(routerPush).toHaveBeenCalledWith({
      name: 'building-detail',
      params: { id: '99' },
      query: { unit_type_id: '7' },
    })
  })
})
