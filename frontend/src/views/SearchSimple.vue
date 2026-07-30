<template>
  <div class="search-page" v-loading="loading">
    <div style="display:flex;gap:12px;padding:16px;align-items:center">
      <el-input v-model="keyword" placeholder="搜索房源..." style="width:300px" clearable @keyup.enter="doSearch" />
      <el-button type="primary" @click="doSearch">搜索</el-button>
      <span style="color:#909399">{{ results.length }} 套</span>
    </div>
    <div class="card-grid" v-if="results.length">
      <div v-for="p in results" :key="p.id" class="card" @click="$router.push('/room/'+p.id)">
        <div class="card-img-wrap">
          <img v-if="p.images?.length" :src="imgUrl(p.images[0])" class="card-img" />
          <div v-else class="card-noimg">暂无图片</div>
        </div>
        <div class="card-info">
          <h3>{{ p.title }}</h3>
          <p class="addr">{{ p.address || p.district }}</p>
          <span class="price">¥{{ Number(p.price_monthly).toLocaleString() }}/月</span>
        </div>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="没有找到房源" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '@/services/api'

const results = ref<any[]>([])
const loading = ref(false)
const keyword = ref('')

function imgUrl(img: any) {
  const f = img?.filename || ''
  return f.startsWith('http') ? f : '/api/v1/uploads/' + f
}

async function doSearch() {
  loading.value = true
  try {
    const params: any = { limit: 50 }
    if (keyword.value) params.q = keyword.value
    const r = await api.get('/properties/search', { params })
    results.value = Array.isArray(r.data) ? r.data : (r.data.items || [])
  } catch { results.value = [] }
  finally { loading.value = false }
}
doSearch()
</script>

<style scoped>
.search-page { max-width: 1200px; margin: 0 auto; padding: 20px }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px }
.card { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.06); cursor: pointer; transition: transform .2s }
.card:hover { transform: translateY(-2px) }
.card-img-wrap { height: 180px; background: #f5f6f8; display: flex; align-items: center; justify-content: center }
.card-img { width: 100%; height: 100%; object-fit: cover }
.card-noimg { color: #c0c4cc }
.card-info { padding: 12px 16px 16px }
.card-info h3 { font-size: 16px; margin: 0 0 4px; color: #303133 }
.addr { font-size: 13px; color: #909399; margin: 0 0 8px }
.price { font-size: 18px; font-weight: 700; color: #f56c6c }
</style>
