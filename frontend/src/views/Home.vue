<template>
  <div class="home-page">
    <!-- Hero Section -->
    <div class="hero">
      <h1>找到你的理想居所</h1>
      <p class="hero-subtitle">智能匹配 · 真实房源 · 轻松租房</p>
      <div class="hero-search">
        <el-input
          v-model="query"
          size="large"
          placeholder="输入区域、小区名称或描述..."
          :prefix-icon="Search"
          class="hero-search-input"
          @keyup.enter="quickSearch"
        >
          <template #append>
            <el-button type="primary" :icon="Search" @click="quickSearch">搜索</el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- Quick Filters -->
    <div class="quick-filters">
      <h2>快速查找</h2>
      <div class="filter-tags">
        <el-tag
          v-for="district in districts"
          :key="district"
          class="filter-tag"
          :type="selectedDistrict === district ? 'primary' : 'info'"
          @click="selectDistrict(district)"
        >
          {{ district }}
        </el-tag>
      </div>
    </div>

    <!-- Latest Properties -->
    <div class="latest-section">
      <div class="section-header">
        <h2>最新房源</h2>
        <el-button text type="primary" @click="$router.push('/search')">
          查看更多 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
      <el-row :gutter="20">
        <el-col v-for="p in properties.slice(0, 6)" :key="p.id" :span="8">
          <PropertyCard :property="p" />
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ArrowRight } from '@element-plus/icons-vue'
import { usePropertyStore } from '@/stores/property'
import PropertyCard from '@/components/PropertyCard.vue'
import { storeToRefs } from 'pinia'

const router = useRouter()
const propertyStore = usePropertyStore()
const { properties } = storeToRefs(propertyStore)

const query = ref('')
const selectedDistrict = ref('')
const searchHints = [
  '地铁站附近两室一厅',
  '工业园区预算2500以内',
  '带阳台精装修公寓',
  '学校周边适合合租',
]

const districts = ['工业园区', '姑苏区', '高新区', '吴中区', '相城区', '吴江区']

function quickSearch() {
  const params: Record<string, string> = {}
  if (query.value.trim()) params.q = query.value.trim()
  router.push({ name: 'search', query: params })
}

function selectDistrict(district: string) {
  if (selectedDistrict.value === district) {
    selectedDistrict.value = ''
  } else {
    selectedDistrict.value = district
  }
  router.push({ name: 'search', query: { district: selectedDistrict.value || undefined } })
}

onMounted(() => {
  propertyStore.fetchList({ limit: 6 })
})
</script>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.hero {
  text-align: center;
  padding: 60px 0 40px;
}

.hero h1 {
  font-size: 36px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 12px;
}

.hero-subtitle {
  font-size: 16px;
  color: #909399;
  margin-bottom: 32px;
}

.ai-search-wrapper {
  max-width: 640px;
  margin: 0 auto;
}

.ai-search-label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 16px;
  color: #409eff;
  font-weight: 600;
}

.ai-search-hints {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.hint-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.hint-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
}

.hero-search {
  max-width: 640px;
  margin: 0 auto;
}

.hero-search-input {
  width: 100%;
}

.quick-filters {
  margin-top: 40px;
}

.quick-filters h2 {
  font-size: 18px;
  color: #303133;
  margin-bottom: 16px;
}

.filter-tags {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-tag {
  cursor: pointer;
  font-size: 14px;
  padding: 8px 20px;
}

.latest-section {
  margin-top: 48px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  font-size: 20px;
  color: #303133;
}
</style>
