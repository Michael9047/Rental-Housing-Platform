<template>
  <div class="search-page">
    <!-- Header -->
    <div class="search-header">
    </div>

    <!-- Filter Card -->
    <el-card shadow="never" class="filter-card">
      <!-- AI Search Bar -->
      <div class="ai-search-bar">
        <el-input
          v-model="filters.q"
          size="large"
          placeholder="AI语义搜索：输入需求描述，如「近地铁两居室」「新加坡留学生公寓」"
          :prefix-icon="Search"
          clearable
          class="ai-input"
          @keyup.enter="doSearch"
        />
        <div class="mode-switch">
          <span class="mode-label">搜索模式</span>
          <el-switch
            v-model="semanticMode"
            active-text="语义匹配"
            inactive-text="精确检索"
            size="large"
          />
        </div>
      </div>

      <!-- Filters Row -->
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="国家/地区">
          <el-select
            v-model="filters.country"
            placeholder="全部"
            clearable
            filterable
            allow-create
            default-first-option
            @change="onCountryChange"
            style="width:130px"
          >
            <el-option label="🏠 国内" value="china" />
            <el-option label="🇭🇰 香港" value="hongkong" />
            <el-option label="🇸🇬 新加坡" value="singapore" />
            <el-option label="🇬🇧 EN" value="uk" />
            <el-option label="🇺🇸 美国" value="usa" />
            <el-option label="🇦🇺 澳洲" value="australia" />
            <el-option label="🌸 日韩" value="japan_korea" />
            <el-option label="🇪🇺 欧洲" value="europe" />
          </el-select>
        </el-form-item>

        <el-form-item label="城市/地区" v-if="filters.country === 'china' || !filters.country">
          <el-select
            v-model="filters.district"
            placeholder="全部"
            clearable
            filterable
            allow-create
            default-first-option
            style="width:130px"
          >
            <el-option label="北京" value="北京" />
            <el-option label="上海" value="上海" />
            <el-option label="广州" value="广州" />
            <el-option label="深圳" value="深圳" />
            <el-option label="苏州" value="苏州" />
            <el-option label="杭州" value="杭州" />
            <el-option label="南京" value="南京" />
            <el-option label="成都" value="成都" />
            <el-option label="武汉" value="武汉" />
          </el-select>
        </el-form-item>

        <el-form-item label="海外地区" v-if="filters.country && filters.country !== 'china'">
          <el-select
            v-model="filters.overseas_area"
            placeholder="全部"
            clearable
            filterable
            allow-create
            default-first-option
            style="width:150px"
          >
            <!-- 新加坡 -->
            <el-option v-if="filters.country==='singapore'" label="国立大学周边" value="国立大学" />
            <el-option v-if="filters.country==='singapore'" label="市中心" value="市中心" />
            <el-option v-if="filters.country==='singapore'" label="滨海湾" value="滨海湾" />
            <el-option v-if="filters.country==='singapore'" label="乌节路" value="乌节路" />
            <!-- 香港 -->
            <el-option v-if="filters.country==='hongkong'" label="港大周边" value="港大周边" />
            <el-option v-if="filters.country==='hongkong'" label="中环" value="中环" />
            <el-option v-if="filters.country==='hongkong'" label="旺角" value="旺角" />
            <el-option v-if="filters.country==='hongkong'" label="尖沙咀" value="尖沙咀" />
            <!-- 英国 -->
            <el-option v-if="filters.country==='uk'" label="伦敦" value="伦敦" />
            <el-option v-if="filters.country==='uk'" label="曼彻斯特" value="曼彻斯特" />
            <el-option v-if="filters.country==='uk'" label="爱丁堡" value="爱丁堡" />
            <el-option v-if="filters.country==='uk'" label="剑桥" value="剑桥" />
            <el-option v-if="filters.country==='uk'" label="牛津" value="牛津" />
            <!-- 美国 -->
            <el-option v-if="filters.country==='usa'" label="纽约" value="纽约" />
            <el-option v-if="filters.country==='usa'" label="洛杉矶" value="洛杉矶" />
            <el-option v-if="filters.country==='usa'" label="旧金山" value="旧金山" />
            <el-option v-if="filters.country==='usa'" label="波士顿" value="波士顿" />
            <el-option v-if="filters.country==='usa'" label="芝加哥" value="芝加哥" />
            <!-- 澳洲 -->
            <el-option v-if="filters.country==='australia'" label="悉尼" value="悉尼" />
            <el-option v-if="filters.country==='australia'" label="墨尔本" value="墨尔本" />
            <el-option v-if="filters.country==='australia'" label="布里斯班" value="布里斯班" />
            <el-option v-if="filters.country==='australia'" label="堪培拉" value="堪培拉" />
            <!-- 日韩 -->
            <el-option v-if="filters.country==='japan_korea'" label="东京" value="东京" />
            <el-option v-if="filters.country==='japan_korea'" label="大阪" value="大阪" />
            <el-option v-if="filters.country==='japan_korea'" label="京都" value="京都" />
            <el-option v-if="filters.country==='japan_korea'" label="首尔" value="首尔" />
            <el-option v-if="filters.country==='japan_korea'" label="釜山" value="釜山" />
            <!-- 欧洲 -->
            <el-option v-if="filters.country==='europe'" label="法国" value="法国" />
            <el-option v-if="filters.country==='europe'" label="德国" value="德国" />
            <el-option v-if="filters.country==='europe'" label="俄罗斯" value="俄罗斯" />
            <el-option v-if="filters.country==='europe'" label="意大利" value="意大利" />
            <el-option v-if="filters.country==='europe'" label="瑞士" value="瑞士" />
            <el-option v-if="filters.country==='europe'" label="西班牙" value="西班牙" />
            <el-option v-if="filters.country==='europe'" label="荷兰" value="荷兰" />
            <el-option v-if="filters.country==='europe'" label="比利时" value="比利时" />
            <el-option v-if="filters.country==='europe'" label="瑞典" value="瑞典" />
            <el-option v-if="filters.country==='europe'" label="挪威" value="挪威" />
            <el-option v-if="filters.country==='europe'" label="丹麦" value="丹麦" />
            <el-option v-if="filters.country==='europe'" label="奥地利" value="奥地利" />
            <el-option v-if="filters.country==='europe'" label="希腊" value="希腊" />
            <el-option v-if="filters.country==='europe'" label="葡萄牙" value="葡萄牙" />
            <el-option v-if="filters.country==='europe'" label="芬兰" value="芬兰" />
          </el-select>
        </el-form-item>

        <el-form-item label="价格">
          <el-input-number v-model="filters.price_min" :min="0" placeholder="最低" controls-position="right" style="width:110px" />
          <span style="margin:0 8px;color:#909399">-</span>
          <el-input-number v-model="filters.price_max" :min="0" placeholder="最高" controls-position="right" style="width:110px" />
        </el-form-item>

        <el-form-item label="户型">
          <el-select v-model="filters.bedrooms" placeholder="不限" clearable style="width:100px">
            <el-option label="1室" :value="1" />
            <el-option label="2室" :value="2" />
            <el-option label="3室" :value="3" />
            <el-option label="4室+" :value="4" />
          </el-select>
        </el-form-item>

        <el-form-item label="类型">
          <el-select
            v-model="filters.property_type"
            placeholder="全部"
            clearable
            filterable
            allow-create
            default-first-option
            style="width:140px"
          >
            <el-option label="公寓" value="apartment" />
            <el-option label="别墅" value="house" />
            <el-option label="单间" value="studio" />
            <el-option label="合租" value="shared" />
            <el-option label="留学生公寓" value="student" />
          </el-select>
        </el-form-item>

        <el-form-item label="排序">
          <el-select v-model="sortBy" style="width:130px" @change="doSearch">
            <el-option label="匹配度优先" value="similarity" />
            <el-option label="价格低→高" value="price_asc" />
            <el-option label="价格高→低" value="price_desc" />
            <el-option label="面积大→小" value="area_desc" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :icon="Search" @click="doSearch">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Results Meta -->
    <div class="results-meta">
      <span>
        共找到 <strong>{{ searchResults.length }}</strong> 套房源
      </span>
      <span v-if="semanticMode && filters.q" class="meta-badge">
        <el-tag type="success" size="small" effect="dark">语义匹配</el-tag>
      </span>
      <span v-if="filters.country" class="meta-filter">
        筛选范围：{{ getCountryLabel(filters.country) }}
      </span>
    </div>

    <!-- Results Grid -->
    <div v-loading="loading" class="results-grid">
      <el-empty v-if="!loading && searchResults.length === 0" description="暂无匹配房源">
        <template #description>
          <p>暂无匹配房源，可切换国家/城市筛选，或放宽搜索条件</p>
        </template>
        <el-button type="primary" @click="resetFilters">一键放宽条件重新搜索</el-button>
      </el-empty>

      <div v-else class="property-grid">
        <PropertyCard
          v-for="p in pagedResults"
          :key="p.id"
          :property="p"
          :show-similarity="semanticMode && !!filters.q"
          :show-quick-book="true"
          @book="openBookingDialog"
        />
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="searchResults.length > pageSize" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="searchResults.length"
        layout="prev, pager, next"
        background
      />
    </div>

    <!-- Booking Dialog -->
    <BookingDateDialog
      v-model="showBookingDialog"
      :property-id="selectedProperty?.id || 0"
      :property-title="selectedProperty?.title"
      :property-price="selectedProperty?.price_monthly"
      @confirm="handleBookingConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { usePropertyStore } from '@/stores/property'
import { storeToRefs } from 'pinia'
import PropertyCard from '@/components/PropertyCard.vue'
import BookingDateDialog from '@/components/BookingDateDialog.vue'
import type { Property, PropertySearchParams, PropertyType } from '@/types/property'

const route = useRoute()
const router = useRouter()
const propertyStore = usePropertyStore()
const { searchResults, loading } = storeToRefs(propertyStore)

const semanticMode = ref(true)
const sortBy = ref('similarity')
const currentPage = ref(1)
const pageSize = 6

const filters = reactive<PropertySearchParams & { country?: string; overseas_area?: string }>({
  q: (route.query.q as string) || '',
  district: (route.query.district as string) || undefined,
  price_min: undefined,
  price_max: undefined,
  bedrooms: undefined,
  property_type: undefined,
  limit: 30,
  country: undefined,
  overseas_area: undefined,
})

const showBookingDialog = ref(false)
const selectedProperty = ref<Property | null>(null)

function openBookingDialog(p: Property) {
  selectedProperty.value = p
  showBookingDialog.value = true
}

function handleBookingConfirm(data: { propertyId: number; date: string; slot: string }) {
  showBookingDialog.value = false
  router.push({
    path: '/booking/confirm',
    query: { property_id: String(data.propertyId), date: data.date, slot: data.slot },
  })
}

const pagedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return searchResults.value.slice(start, start + pageSize)
})

// 国家/地区标签映射
const countryLabels: Record<string, string> = {
  china: '国内',
  hongkong: '香港',
  singapore: '新加坡',
  uk: '英国',
  usa: '美国',
  australia: '澳洲',
  japan_korea: '日韩',
  europe: '欧洲',
}

function getCountryLabel(country: string): string {
  return countryLabels[country] || country
}

function onCountryChange() {
  filters.overseas_area = undefined
  if (filters.country === 'china') filters.district = undefined
  doSearch()
}

function doSearch() {
  currentPage.value = 1
  const params: PropertySearchParams = {}
  if (semanticMode.value && filters.q) params.q = filters.q
  // 后端暂不支持 country/overseas_area 参数，映射到 district
  if (filters.district) {
    params.district = filters.district
  } else if (filters.overseas_area) {
    params.district = filters.overseas_area
  } else if (filters.country) {
    // 将国家名映射为 district（临时方案，等后端加 country 字段后移除）
    params.district = filters.country
  }
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
  filters.country = undefined
  filters.overseas_area = undefined
  filters.price_min = undefined
  filters.price_max = undefined
  filters.bedrooms = undefined
  filters.property_type = undefined
  sortBy.value = 'similarity'
  doSearch()
}

onMounted(() => {
  // 从路由参数回填筛选条件
  if (route.query.country) {
    filters.country = route.query.country as string
    filters.overseas_area = route.query.overseas_area as string || undefined
    // 如果是欧洲细分国家，需要特殊处理
    if (route.query.country === 'europe' && route.query.overseas_area) {
      filters.overseas_area = route.query.overseas_area as string
    }
  }
  if (route.query.district) {
    filters.district = route.query.district as string
  }
  if (route.query.q) {
    filters.q = route.query.q as string
  }
  doSearch()
})

// 监听路由参数变化
watch(() => route.query, (query) => {
  if (query.country !== undefined) {
    filters.country = query.country as string
  }
  if (query.overseas_area !== undefined) {
    filters.overseas_area = query.overseas_area as string
  }
  if (query.district !== undefined) {
    filters.district = query.district as string
  } else if (!query.country && !query.overseas_area) {
    filters.district = undefined
  }
  if (query.q !== undefined) {
    filters.q = query.q as string
  }
  doSearch()
})
</script>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
}

.search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.search-header h2 {
  font-size: 22px;
  color: var(--text-primary);
  margin: 0;
}

/* ── Filter Card ──────────────────── */

.filter-card {
  margin-bottom: 20px;
}

.ai-search-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}

.ai-input {
  flex: 1;
}

.ai-input :deep(.el-input__wrapper) {
  border-radius: 24px !important;
}

.mode-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.mode-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

/* ── Results ──────────────────────── */

.results-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text-secondary);
}

.meta-filter {
  font-size: 13px;
  color: var(--text-muted);
}

.property-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .property-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .property-grid {
    grid-template-columns: 1fr;
  }
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 32px;
  padding-bottom: 24px;
}
</style>
