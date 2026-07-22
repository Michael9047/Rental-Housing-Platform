import { defineStore } from 'pinia'
import { ref } from 'vue'
import { propertyService } from '@/services/property'
import type { Property, PropertyCreate, PropertyUpdate, PropertySearchResult, PropertySearchParams, PropertyImage } from '@/types/property'

export const usePropertyStore = defineStore('property', () => {
  const properties = ref<Property[]>([])
  const searchResults = ref<PropertySearchResult[]>([])
  const currentProperty = ref<Property | null>(null)
  const loading = ref(false)

  // 分页状态
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const totalPages = ref(1)

  // Cached search conditions
  const lastSearchParams = ref<PropertySearchParams>({})
  const propertyImages = ref<PropertyImage[]>([])
  const imagesLoading = ref(false)

  async function fetchList(params?: { page?: number; page_size?: number; district?: string; status?: string; landlord_id?: number; keyword?: string; property_type?: string; price_min?: number; price_max?: number }) {
    loading.value = true
    try {
      const res = await propertyService.list(params)
      properties.value = res.items
      total.value = res.total
      page.value = res.page
      pageSize.value = res.page_size
      totalPages.value = res.total_pages
    } finally {
      loading.value = false
    }
  }

  async function fetchRecycleBin(params?: { page?: number; page_size?: number; landlord_id?: number }) {
    loading.value = true
    try {
      const res = await propertyService.listRecycleBin(params)
      properties.value = res.items
      total.value = res.total
      return res
    } finally {
      loading.value = false
    }
  }

  async function fetchSearch(params: PropertySearchParams) {
    loading.value = true
    lastSearchParams.value = params
    try {
      searchResults.value = await propertyService.search(params)
    } finally {
      loading.value = false
    }
  }

  async function fetchById(id: number) {
    loading.value = true
    try {
      currentProperty.value = await propertyService.getById(id)
    } catch {
      currentProperty.value = null
      throw new Error('Failed to load property')
    } finally {
      loading.value = false
    }
  }

  async function create(data: PropertyCreate): Promise<Property> {
    loading.value = true
    try {
      const created = await propertyService.create(data)
      return created
    } finally {
      loading.value = false
    }
  }

  async function update(id: number, data: PropertyUpdate): Promise<Property> {
    loading.value = true
    try {
      const updated = await propertyService.update(id, data)
      if (currentProperty.value?.id === id) {
        currentProperty.value = updated
      }
      return updated
    } finally {
      loading.value = false
    }
  }

  async function restoreProperty(id: number): Promise<Property> {
    loading.value = true
    try {
      return await propertyService.restore(id)
    } finally {
      loading.value = false
    }
  }

  async function batchUpdateStatus(ids: number[], status: string) {
    loading.value = true
    try {
      return await propertyService.batchUpdateStatus(ids, status)
    } finally {
      loading.value = false
    }
  }

  async function batchDelete(ids: number[]) {
    loading.value = true
    try {
      return await propertyService.batchDelete(ids)
    } finally {
      loading.value = false
    }
  }

  async function hardDeleteProperty(id: number) {
    loading.value = true
    try {
      await propertyService.hardDelete(id)
      properties.value = properties.value.filter((p) => p.id !== id)
    } finally {
      loading.value = false
    }
  }

  async function batchRestore(ids: number[]) {
    loading.value = true
    try {
      return await propertyService.batchRestore(ids)
    } finally {
      loading.value = false
    }
  }

  async function batchHardDelete(ids: number[]) {
    loading.value = true
    try {
      return await propertyService.batchHardDelete(ids)
    } finally {
      loading.value = false
    }
  }

  async function fetchImages(propertyId: number) {
    imagesLoading.value = true
    try {
      propertyImages.value = await propertyService.listImages(propertyId)
    } finally {
      imagesLoading.value = false
    }
  }

  async function fetchImagesRef(propertyId: number): Promise<PropertyImage[]> {
    return await propertyService.listImages(propertyId)
  }

  async function uploadImages(propertyId: number, files: File[]): Promise<PropertyImage[]> {
    imagesLoading.value = true
    try {
      const images = await propertyService.uploadImages(propertyId, files)
      propertyImages.value = await propertyService.listImages(propertyId)
      return images
    } finally {
      imagesLoading.value = false
    }
  }

  async function deleteImage(propertyId: number, imageId: number) {
    await propertyService.deleteImage(propertyId, imageId)
    propertyImages.value = propertyImages.value.filter((img) => img.id !== imageId)
  }

  async function setPrimaryImage(propertyId: number, imageId: number) {
    await propertyService.setPrimaryImage(propertyId, imageId)
    propertyImages.value = propertyImages.value.map((img) => ({
      ...img,
      is_primary: img.id === imageId,
    }))
  }

  async function remove(id: number) {
    loading.value = true
    try {
      await propertyService.delete(id)
      properties.value = properties.value.filter((p) => p.id !== id)
      searchResults.value = searchResults.value.filter((p) => p.id !== id)
    } finally {
      loading.value = false
    }
  }

  /** 直接注入预加载结果（来自 Agent 推荐），跳过后端 API 搜索 */
  function setSearchResults(results: PropertySearchResult[]) {
    searchResults.value = results
    loading.value = false
  }

  return {
    properties, searchResults, currentProperty, loading,
    total, page, pageSize, totalPages,
    lastSearchParams, propertyImages, imagesLoading,
    fetchList, fetchRecycleBin, fetchSearch, fetchById,
    create, update, restoreProperty,
    batchUpdateStatus, batchDelete,
    hardDeleteProperty, batchRestore, batchHardDelete,
    remove,
    setSearchResults,
    fetchImages, fetchImagesRef, uploadImages, deleteImage, setPrimaryImage,
  }
})
