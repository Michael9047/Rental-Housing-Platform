import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePropertyStore } from '@/stores/property'

const mockList = vi.fn()
const mockSearch = vi.fn()
const mockGetById = vi.fn()
const mockCreate = vi.fn()
const mockUpdate = vi.fn()
const mockDelete = vi.fn()
const mockListImages = vi.fn()
const mockUploadImages = vi.fn()
const mockDeleteImage = vi.fn()
const mockSetPrimaryImage = vi.fn()

vi.mock('@/services/property', () => ({
  propertyService: {
    list: (...args: any[]) => mockList(...args),
    search: (...args: any[]) => mockSearch(...args),
    getById: (...args: any[]) => mockGetById(...args),
    create: (...args: any[]) => mockCreate(...args),
    update: (...args: any[]) => mockUpdate(...args),
    delete: (...args: any[]) => mockDelete(...args),
    listImages: (...args: any[]) => mockListImages(...args),
    uploadImages: (...args: any[]) => mockUploadImages(...args),
    deleteImage: (...args: any[]) => mockDeleteImage(...args),
    setPrimaryImage: (...args: any[]) => mockSetPrimaryImage(...args),
  },
}))

const sampleProperty = {
  id: 1, landlord_id: 1,
  title: 'Test Property', description: 'Test desc',
  address: '123 Test St', district: '工业园区',
  price_monthly: 3000, area_sqm: 50,
  bedrooms: 2, bathrooms: 1,
  property_type: 'apartment' as const, status: 'available' as const,
  latitude: null, longitude: null,
  deposit_amount: 3000, service_fee_rate: 0.5,
  created_at: '', updated_at: '',
}

describe('usePropertyStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initializes with empty state', () => {
    const store = usePropertyStore()
    expect(store.properties).toEqual([])
    expect(store.currentProperty).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('fetchList populates properties', async () => {
    mockList.mockResolvedValue([sampleProperty])
    const store = usePropertyStore()
    await store.fetchList()
    expect(store.properties).toHaveLength(1)
    expect(store.properties[0].title).toBe('Test Property')
  })

  it('fetchById sets currentProperty', async () => {
    mockGetById.mockResolvedValue(sampleProperty)
    const store = usePropertyStore()
    await store.fetchById(1)
    expect(store.currentProperty?.title).toBe('Test Property')
    expect(mockGetById).toHaveBeenCalledWith(1)
  })

  it('fetchSearch populates searchResults', async () => {
    mockSearch.mockResolvedValue([{ ...sampleProperty, similarity: 0.9 }])
    const store = usePropertyStore()
    await store.fetchSearch({ q: 'test' })
    expect(store.searchResults).toHaveLength(1)
    expect(store.lastSearchParams).toEqual({ q: 'test' })
  })

  it('create returns new property', async () => {
    mockCreate.mockResolvedValue(sampleProperty)
    const store = usePropertyStore()
    const result = await store.create({ title: 'New', address: 'Addr', district: 'SIP', price_monthly: 2000, landlord_id: 1 })
    expect(result.title).toBe('Test Property')
  })

  it('update refreshes currentProperty if same id', async () => {
    const updated = { ...sampleProperty, title: 'Updated Title' }
    mockUpdate.mockResolvedValue(updated)
    const store = usePropertyStore()
    store.$patch({ currentProperty: sampleProperty })
    const result = await store.update(1, { title: 'Updated Title' })
    expect(store.currentProperty?.title).toBe('Updated Title')
  })

  it('remove filters from arrays', async () => {
    mockDelete.mockResolvedValue(undefined)
    const store = usePropertyStore()
    store.$patch({ properties: [sampleProperty], searchResults: [{ ...sampleProperty, similarity: 0.8 }] })
    await store.remove(1)
    expect(store.properties).toHaveLength(0)
    expect(store.searchResults).toHaveLength(0)
  })

  it('deleteImage removes from local array', async () => {
    mockDeleteImage.mockResolvedValue(undefined)
    const store = usePropertyStore()
    const img1 = { id: 1, property_id: 1, filename: 'a.jpg', original_name: 'a.jpg', mime_type: 'image/jpeg', file_size: 100, sort_order: 0, is_primary: true, created_at: '' }
    const img2 = { id: 2, property_id: 1, filename: 'b.jpg', original_name: 'b.jpg', mime_type: 'image/jpeg', file_size: 100, sort_order: 1, is_primary: false, created_at: '' }
    store.$patch({ propertyImages: [img1, img2] })
    await store.deleteImage(1, 1)
    expect(store.propertyImages).toHaveLength(1)
    expect(store.propertyImages[0].id).toBe(2)
  })

  it('setPrimaryImage updates is_primary flags', async () => {
    mockSetPrimaryImage.mockResolvedValue(undefined)
    const store = usePropertyStore()
    const img1 = { id: 1, property_id: 1, filename: 'a.jpg', original_name: 'a.jpg', mime_type: 'image/jpeg', file_size: 100, sort_order: 0, is_primary: true, created_at: '' }
    const img2 = { id: 2, property_id: 1, filename: 'b.jpg', original_name: 'b.jpg', mime_type: 'image/jpeg', file_size: 100, sort_order: 1, is_primary: false, created_at: '' }
    store.$patch({ propertyImages: [img1, img2] })
    await store.setPrimaryImage(1, 2)
    expect(store.propertyImages[0].is_primary).toBe(false)
    expect(store.propertyImages[1].is_primary).toBe(true)
  })
})