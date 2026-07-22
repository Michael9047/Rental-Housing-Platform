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
        <el-button type="primary" size="large" @click="doSearch" class="search-btn">搜索</el-button>
      </div>
    </section>

    <!-- 公寓卡片列表 -->
    <section class="building-list" v-loading="loading">
      <div class="section-header">
        <h2 class="section-title">🏢 全部公寓</h2>
        <span class="section-count" v-if="buildings.length">{{ buildings.length }} 栋</span>
      </div>

      <div class="card-grid" v-if="buildings.length">
        <div v-for="b in buildings" :key="b.id" class="building-card" @click="$router.push('/room/'+b.id)">
          <div class="card-cover">
            <img v-if="b.primary_image" :src="'/api/v1/uploads/'+b.primary_image" alt="" />
            <div v-else class="card-cover-placeholder">🏢</div>
            <div class="card-price" v-if="b.min_rent">
              <span class="price-amount">¥{{ b.min_rent.toLocaleString() }}</span>
              <span class="price-slash">/月起</span>
            </div>
          </div>
          <div class="card-body">
            <h3 class="card-name">{{ b.name }}</h3>
            <p class="card-addr" v-if="b.address">📍 {{ b.address?.slice(0, 50) }}{{ b.address?.length > 50 ? '...' : '' }}</p>
            <div class="card-tags" v-if="b.amenities?.length">
              <span v-for="a in b.amenities.slice(0,5)" :key="a" class="card-tag">{{ a }}</span>
              <span v-if="b.amenities.length > 5" class="card-tag card-tag-more">+{{ b.amenities.length - 5 }}</span>
            </div>
            <div class="card-special" v-if="b.female_only || b.couples_allowed">
              <span v-if="b.female_only" class="special-badge badge-girls">👩 女生独栋</span>
              <span v-if="b.couples_allowed" class="special-badge badge-couples">💑 支持情侣</span>
            </div>
            <div class="card-footer">
              <span class="footer-types" v-if="b.unit_type_count">📐 {{ b.unit_type_count }} 种户型可选</span>
              <span class="footer-empty" v-else>暂无户型</span>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无公寓数据" :image-size="100" />
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
    const params: any = { page_size: 50 }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const r = await api.get('/properties', { params })
    // 将 properties API 返回的数据映射为卡片需要的格式
    buildings.value = (r.data.items || []).map((p: any) => ({
      id: p.id,
      name: p.title || p.address,
      address: p.address,
      min_rent: p.price_monthly ? Number(p.price_monthly) : null,
      primary_image: p.images?.find((i: any) => i.is_primary)?.filename || p.images?.[0]?.filename || null,
      amenities: p.amenities || [],
      female_only: false,
      couples_allowed: false,
      unit_type_count: null,
    }))
  } catch { /* */ }
  finally { loading.value = false }
}

function doSearch() { loadBuildings() }

onMounted(() => loadBuildings())
</script>

<style scoped>
.home-page { max-width: 1200px; margin: 0 auto; padding: 0 24px 60px }

/* ═══════════ Hero ═══════════ */
.hero {
  text-align: center;
  padding: 56px 0 40px;
}

.hero-title {
  font-size: 36px;
  font-weight: 800;
  color: #1a1a2e;
  margin: 0 0 10px;
  letter-spacing: -0.5px;
}

.hero-subtitle {
  color: #6b7280;
  font-size: 18px;
  margin: 0 0 28px;
  line-height: 1.5;
}

.hero-search-bar {
  display: flex;
  gap: 10px;
  max-width: 600px;
  margin: 0 auto;
}

.search-input { flex: 1 }
.search-input :deep(.el-input__wrapper) {
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  padding: 6px 16px;
}

.search-btn {
  border-radius: 12px;
  padding: 0 28px;
  font-weight: 600;
  font-size: 15px;
}

/* ═══════════ 区块标题 ═══════════ */
.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 24px;
}

.section-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.section-count {
  font-size: 15px;
  color: #909399;
  font-weight: 500;
}

/* ═══════════ 卡片网格 ═══════════ */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.building-card {
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.25s ease;
}

.building-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0,0,0,0.1);
  border-color: #FF6B35;
}

/* 封面 */
.card-cover {
  height: 200px;
  background: #f5f6f8;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s ease;
}

.building-card:hover .card-cover img {
  transform: scale(1.05);
}

.card-cover-placeholder {
  font-size: 64px;
  opacity: 0.2;
}

.card-price {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: rgba(0,0,0,0.72);
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 6px 14px;
  border-radius: 10px;
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.price-amount {
  font-size: 18px;
  font-weight: 700;
}

.price-slash {
  font-size: 12px;
  opacity: 0.8;
}

/* 卡片内容 */
.card-body {
  padding: 18px 20px 22px;
}

.card-name {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 6px;
  line-height: 1.35;
}

.card-addr {
  font-size: 14px;
  color: #909399;
  margin: 0 0 12px;
  line-height: 1.4;
}

/* 标签 */
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.card-tag {
  font-size: 12px;
  padding: 3px 10px;
  background: #f5f7fa;
  border: 1px solid #e9ecf1;
  border-radius: 6px;
  color: #606266;
  font-weight: 500;
}

.card-tag-more {
  background: #fffaeb;
  color: #e6a23c;
  border-color: #faecd8;
}

/* 特殊标识 */
.card-special {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.special-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 8px;
}

.badge-girls {
  background: #fef0f0;
  color: #e0485c;
  border: 1px solid #fcd4da;
}

.badge-couples {
  background: #f4f0fe;
  color: #7c3aed;
  border: 1px solid #e0d4fc;
}

/* 底部 */
.card-footer {
  padding-top: 14px;
  border-top: 1px solid #f0f2f5;
}

.footer-types {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.footer-empty {
  font-size: 14px;
  color: #c0c4cc;
}

@media (max-width: 768px) {
  .home-page { padding: 0 12px 40px }
  .hero { padding: 36px 0 28px }
  .hero-title { font-size: 28px }
  .hero-subtitle { font-size: 16px }
  .card-grid { grid-template-columns: 1fr }
}
</style>
