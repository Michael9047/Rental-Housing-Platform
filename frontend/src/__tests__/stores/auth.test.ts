import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/services/auth', () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
  },
}))

vi.mock('@/router', () => ({
  default: { push: vi.fn() },
}))

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('initializes with not logged in state', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
  })

  it('loads auth from localStorage', () => {
    localStorage.setItem('access_token', 'test-token')
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'test', role: 'tenant' }))
    const store = useAuthStore()
    store.loadFromStorage()
    expect(store.token).toBe('test-token')
    expect(store.user?.username).toBe('test')
    expect(store.isLoggedIn).toBe(true)
  })

  it('clears auth on logout', () => {
    localStorage.setItem('access_token', 'test-token')
    const store = useAuthStore()
    store.loadFromStorage()
    store.logout()
    expect(store.isLoggedIn).toBe(false)
    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
  })

  it('isLandlord returns true for landlord role', () => {
    const store = useAuthStore()
    store.$patch({ token: 't', user: { id: 1, username: 'l', role: 'landlord' } } as any)
    expect(store.isLandlord).toBe(true)
  })

  it('isAdmin returns true for admin role', () => {
    const store = useAuthStore()
    store.$patch({ token: 't', user: { id: 1, username: 'a', role: 'admin' } } as any)
    expect(store.isAdmin).toBe(true)
  })

  it('isLandlord is false for tenant', () => {
    const store = useAuthStore()
    store.$patch({ token: 't', user: { id: 1, username: 't', role: 'tenant' } } as any)
    expect(store.isLandlord).toBe(false)
  })

  it('handles corrupt localStorage gracefully', () => {
    localStorage.setItem('access_token', 'ok')
    localStorage.setItem('user', '{invalid json')
    const store = useAuthStore()
    store.loadFromStorage()
    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
  })

  it('setAuth updates state and localStorage', () => {
    const store = useAuthStore()
    const user = { id: 2, username: 'new', email: 'new@test.com', role: 'tenant' as const, status: 'active' as const, phone: null, created_at: '', updated_at: '' }
    store.setAuth('new-token', user)
    expect(store.token).toBe('new-token')
    expect(store.user?.username).toBe('new')
    expect(localStorage.getItem('access_token')).toBe('new-token')
  })
})