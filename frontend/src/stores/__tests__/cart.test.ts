import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCartStore } from '@/stores/cart'
import type { Cart, CartItem } from '@/types/agent'

const agentServiceMocks = vi.hoisted(() => ({
  getCart: vi.fn(),
  addCartItem: vi.fn(),
  removeCartItem: vi.fn(),
}))

vi.mock('@/services/agent', () => ({
  agentService: agentServiceMocks,
}))

function cartItem(propertyId: number): CartItem {
  return {
    id: propertyId + 1000,
    property_id: propertyId,
    reason: null,
    created_at: '2026-08-09T00:00:00Z',
    property: {
      id: propertyId,
      institute_id: propertyId + 100,
      title: `UnitType ${propertyId}`,
      name: `UnitType ${propertyId}`,
    } as CartItem['property'],
  }
}

function cart(items: CartItem[]): Cart {
  return { id: 1, session_id: null, items }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('useCartStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    agentServiceMocks.getCart.mockReset()
    agentServiceMocks.addCartItem.mockReset()
    agentServiceMocks.removeCartItem.mockReset()
  })

  it('ignores an old account fetch that resolves after clear and a new account fetch', async () => {
    const oldFetch = deferred<Cart>()
    const newItem = cartItem(202)
    agentServiceMocks.getCart
      .mockReturnValueOnce(oldFetch.promise)
      .mockResolvedValueOnce(cart([newItem]))
    const store = useCartStore()

    const oldRequest = store.fetch()
    store.clear()
    await store.fetch()
    oldFetch.resolve(cart([cartItem(101)]))
    await oldRequest

    expect(store.loaded).toBe(true)
    expect(store.items.map((item) => item.property_id)).toEqual([202])
  })

  it('does not append an old account add response after clear', async () => {
    const oldAdd = deferred<CartItem>()
    const newItem = cartItem(202)
    agentServiceMocks.addCartItem.mockReturnValueOnce(oldAdd.promise)
    agentServiceMocks.getCart.mockResolvedValueOnce(cart([newItem]))
    const store = useCartStore()

    const oldRequest = store.add(101)
    store.clear()
    await store.fetch()
    oldAdd.resolve(cartItem(101))

    await expect(oldRequest).resolves.toBe(false)
    expect(store.items.map((item) => item.property_id)).toEqual([202])
  })

  it('does not remove a colliding UnitType from a new account when an old remove resolves', async () => {
    const oldRemove = deferred<void>()
    const sharedItem = cartItem(101)
    const newItem = cartItem(202)
    agentServiceMocks.getCart
      .mockResolvedValueOnce(cart([sharedItem]))
      .mockResolvedValueOnce(cart([sharedItem, newItem]))
    agentServiceMocks.removeCartItem.mockReturnValueOnce(oldRemove.promise)
    const store = useCartStore()

    await store.fetch()
    const oldRequest = store.remove(101)
    store.clear()
    await store.fetch()
    oldRemove.resolve()
    await oldRequest

    expect(store.items.map((item) => item.property_id)).toEqual([101, 202])
  })
})
