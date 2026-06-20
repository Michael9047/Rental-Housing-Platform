import { defineStore } from 'pinia'
import { ref } from 'vue'
import { propertyService } from '@/services/property'
import type { Property, PropertyCreate, PropertyUpdate, PropertySearchResult, PropertySearchParams } from '@/types/property'

export const usePropertyStore = defineStore('property', () => {
  const properties = ref<Property[]>([])
  const searchResults = ref<PropertySearchResult[]>([])
  const currentProperty = ref<Property | null>(null)
  const loading = ref(false)

  // Cached search conditions
  const lastSearchParams = ref<PropertySearchParams>({})

  async function fetchList(params?: { skip?: number; limit?: number; district?: string; status?: string }) {
    loading.value = true
    try {
      properties.value = await propertyService.list(params)
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

  return {
    properties,
    searchResults,
    currentProperty,
    loading,
    lastSearchParams,
    fetchList,
    fetchSearch,
    fetchById,
    create,
    update,
    remove,
  }
})
