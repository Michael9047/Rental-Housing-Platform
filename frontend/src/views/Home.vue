<template>
  <div class="home-page">
    <!-- Hero -->
    <section class="hero">
      <h1 class="hero-title">全球留学生公寓</h1>
      <p class="hero-subtitle">覆盖主流留学城市，一站式预订海外公寓</p>
      <div class="hero-search-bar">
        <el-input v-model="searchKeyword" placeholder="搜索城市、学校或公寓名称..." size="large" clearable @keyup.enter="doSearch" class="search-input">
          <template #prefix><span style="font-size:18px">🔍</span></template>
        </el-input>
        <el-button type="primary" size="large" @click="doSearch">搜索</el-button>
      </div>
    </section>

    <!-- 公寓卡片列表 -->
    <section class="building-list" v-loading="loading">
      <h2 class="section-title">🏢 全部公寓</h2>
      <div class="card-grid" v-if="buildings.length">
        <div v-for="b in buildings" :key="b.id" class="building-card" @click="$router.push('/room/'+b.id)">
          <div class="card-cover">
            <img v-if="b.primary_image" :src="'/api/v1/uploads/'+b.primary_image" alt="" />
            <div v-else class="card-cover-placeholder">🏢</div>
            <div class="card-price" v-if="b.min_rent">¥{{ b.min_rent.toLocaleString() }}/月起</div>
          </div>
          <div class="card-body">
            <h3 class="card-name">{{ b.name }}</h3>
            <p class="card-addr" v-if="b.address">📍 {{ b.address?.slice(0, 40) }}{{ b.address?.length > 40 ? '...' : '' }}</p>
            <div class="card-tags" v-if="b.amenities?.length">
              <el-tag v-for="a in b.amenities.slice(0,4)" :key="a" size="small" type="info">{{ a }}</el-tag>
            </div>
            <div class="card-special" v-if="b.female_only || b.couples_allowed">
              <el-tag v-if="b.female_only" size="small" type="danger" effect="dark">👩 女生独栋</el-tag>
              <el-tag v-if="b.couples_allowed" size="small" type="warning" effect="dark">💑 支持情侣</el-tag>
            </div>
            <div class="card-footer">
              <span v-if="b.unit_type_count">{{ b.unit_type_count }} 种户型可选</span>
              <span v-else style="color:#c0c4cc">暂无户型</span>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无公寓数据" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

const router = useRouter()
const buildings = ref<any[]>([])
const loading = ref(false)
const searchKeyword = ref('')

async function loadBuildings() {
  loading.value = true
  try {
    const params: any = { limit: 50 }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const r = await api.get('/buildings/public/list', { params })
    buildings.value = r.data.items || []
  } catch { /* */ }
  finally { loading.value = false }
}

function doSearch() { loadBuildings() }

onMounted(() => loadBuildings())
</script>

<style scoped>
.home-page { max-width: 1200px; margin: 0 auto; padding: 0 20px }
.hero { text-align: center; padding: 48px 0 32px }
.hero-title { font-size: 32px; font-weight: 700; color: #303133; margin: 0 0 8px }
.hero-subtitle { color: #909399; font-size: 16px; margin: 0 0 24px }
.hero-search-bar { display: flex; gap: 8px; max-width: 560px; margin: 0 auto }
.search-input { flex: 1 }

.section-title { font-size: 20px; color: #303133; margin: 0 0 16px }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px }
.building-card { border-radius: 12px; overflow: hidden; background: #fff; box-shadow: 0 2px 12px rgba(0,0,0,0.06); cursor: pointer; transition: transform 0.2s, box-shadow 0.2s }
.building-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.12) }
.card-cover { height: 180px; background: #f5f6f8; position: relative; display: flex; align-items: center; justify-content: center }
.card-cover img { width: 100%; height: 100%; object-fit: cover }
.card-cover-placeholder { font-size: 48px; opacity: 0.3 }
.card-price { position: absolute; bottom: 8px; left: 8px; background: rgba(0,0,0,0.7); color: #fff; padding: 4px 12px; border-radius: 6px; font-size: 14px; font-weight: 600 }
.card-body { padding: 12px 16px 16px }
.card-name { font-size: 16px; font-weight: 600; color: #303133; margin: 0 0 4px }
.card-addr { font-size: 13px; color: #909399; margin: 0 0 8px }
.card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px }
.card-footer { font-size: 13px; color: #606266 }
</style>
