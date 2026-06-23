<template>
  <div class="search-page">
    <h2>搜索房源</h2>

    <!-- Filter Bar -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="关键词">
          <el-input v-model="filters.q" placeholder="描述、小区、配套..." clearable style="width: 240px" />
        </el-form-item>
        <el-form-item>
          <el-tooltip content="开启后使用语义匹配，理解自然语言描述；关闭则仅用精确筛选" placement="top">
            <el-switch
              v-model="semanticMode"
              active-text="语义"
              inactive-text="精确"
              :disabled="!filters.q"
            />
          </el-tooltip>
        </el-form-item>
        <el-form-item label="区域">
          <el-select v-model="filters.district" placeholder="全部区域" clearable>
            <el-option
              v-for="d in districts"
              :key="d"
              :label="d"
              :value="d"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="价格">
          <el-input-number v-model="filters.price_min" :min="0" placeholder="最低" controls-position="right" style="width: 120px" />
          <span style="margin: 0 8px; color: #909399">-</span>
          <el-input-number v-model="filters.price_max" :min="0" placeholder="最高" controls-position="right" style="width: 120px" />
        </el-form-item>
        <el-form-item label="户型">
          <el-select v-model="filters.bedrooms" placeholder="不限" clearable style="width: 100px">
            <el-option label="1室" :value="1" />
            <el-option label="2室" :value="2" />
            <el-option label="3室" :value="3" />
            <el-option label="4室+" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.property_type" placeholder="全部类型" clearable style="width: 120px">
            <el-option label="公寓" value="apartment" />
            <el-option label="别墅" value="house" />
            <el-option label="单间" value="studio" />
            <el-option label="合租" value="shared" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="SearchIcon" @click="doSearch">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Results -->
    <div class="results-header">
      <span>
        共找到 <strong>{{ searchResults.length }}</strong> 套房源
        <el-tag v-if="semanticMode && filters.q" type="success" size="small" style="margin-left: 8px">语义匹配</el-tag>
      </span>
    </div>

    <div v-loading="loading">
      <el-empty v-if="!loading && searchResults.length === 0" description="暂无匹配房源" />
      <el-row v-else :gutter="20">
        <el-col v-for="p in searchResults" :key="p.id" :span="8" style="margin-bottom: 20px">
          <PropertyCard :property="p" :show-similarity="semanticMode && !!filters.q" />
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Search as SearchIcon } from '@element-plus/icons-vue'
import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import type { PropertySearchParams, PropertyType } from '@/types/property'

const route = useRoute()
const propertyStore = usePropertyStore()
const { searchResults, loading } = storeToRefs(propertyStore)

const districts = ['工业园区', '姑苏区', '高新区', '吴中区', '相城区', '吴江区']
const semanticMode = ref(true)

const filters = reactive<PropertySearchParams>({
  q: (route.query.q as string) || '',
  district: (route.query.district as string) || undefined,
  price_min: undefined,
  price_max: undefined,
  bedrooms: undefined,
  property_type: undefined,
  limit: 30,
})

function doSearch() {
  const params: PropertySearchParams = {}
  if (semanticMode.value && filters.q) {
    params.q = filters.q
  }
  if (filters.district) params.district = filters.district
  if (filters.price_min != null) params.price_min = filters.price_min
  if (filters.price_max != null) params.price_max = filters.price_max
  if (filters.bedrooms != null) params.bedrooms = filters.bedrooms
  if (filters.property_type) params.property_type = filters.property_type as PropertyType
  params.limit = 30
  propertyStore.fetchSearch(params)
}

function resetFilters() {
  filters.q = ''
  filters.district = undefined
  filters.price_min = undefined
  filters.price_max = undefined
  filters.bedrooms = undefined
  filters.property_type = undefined
  doSearch()
}

onMounted(() => {
  doSearch()
})
</script>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
}

.search-page h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 20px;
}

.filter-card {
  margin-bottom: 24px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.results-header {
  margin-bottom: 16px;
  color: #606266;
  font-size: 14px;
}
</style>
