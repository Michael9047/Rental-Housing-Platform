<template>
  <div class="admin-properties" v-loading="loading">
    <h2>户型信息审核</h2>

    <div class="filters">
      <el-input v-model="search" placeholder="搜索户型、公寓、地址、城市" clearable class="search-box" />
      <el-select v-model="statusFilter" placeholder="户型状态" clearable>
        <el-option label="可租" value="available" />
        <el-option label="已租" value="rented" />
        <el-option label="维修中" value="maintenance" />
      </el-select>
      <el-button type="primary" @click="fetchAll">查询</el-button>
    </div>

    <el-table :data="filteredList" stripe max-height="620" class="review-table" @row-click="openDetail">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="户型图" width="90">
        <template #default="{ row }">
          <el-image
            v-if="coverOf(row)"
            :src="coverOf(row)"
            fit="cover"
            class="cover"
          />
          <span v-else class="empty-cover">无图</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="房型" min-width="150" show-overflow-tooltip />
      <el-table-column prop="institute_name" label="公寓" min-width="150" show-overflow-tooltip />
      <el-table-column prop="institute_address" label="地址" min-width="220" show-overflow-tooltip />
      <el-table-column label="地区" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">{{ locationOf(row) }}</template>
      </el-table-column>
      <el-table-column label="租金" width="110" align="right">
        <template #default="{ row }">{{ moneyOf(row) }}</template>
      </el-table-column>
      <el-table-column label="户型" width="110">
        <template #default="{ row }">{{ roomTypeOf(row) }}</template>
      </el-table-column>
      <el-table-column label="库存" width="90" align="center">
        <template #default="{ row }">{{ row.available_count }}/{{ row.total_count }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="120">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="审核" width="190" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="success" @click.stop="recordReview(row, 'normal')">正常</el-button>
          <el-button size="small" type="warning" plain @click.stop="recordReview(row, 'abnormal')">异常</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !filteredList.length" description="暂无户型数据" />

    <el-dialog v-model="detailVisible" title="户型信息" width="760px">
      <template v-if="detailRow">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="房型" :span="2">{{ detailRow.name }}</el-descriptions-item>
          <el-descriptions-item label="公寓">{{ detailRow.institute_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detailRow.status) }}</el-descriptions-item>
          <el-descriptions-item label="地址" :span="2">{{ detailRow.institute_address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ locationOf(detailRow) }}</el-descriptions-item>
          <el-descriptions-item label="租金">{{ moneyOf(detailRow) }}</el-descriptions-item>
          <el-descriptions-item label="户型">{{ roomTypeOf(detailRow) }}</el-descriptions-item>
          <el-descriptions-item label="面积">{{ detailRow.area_sqm || '-' }} ㎡</el-descriptions-item>
          <el-descriptions-item label="库存">{{ detailRow.available_count }}/{{ detailRow.total_count }}</el-descriptions-item>
          <el-descriptions-item label="最短租期">{{ detailRow.min_stay_months }} 个月</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detailRow.description || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailRow.image_urls?.length" class="image-grid">
          <el-image
            v-for="img in detailRow.image_urls"
            :key="img"
            :src="img"
            fit="cover"
            class="detail-image"
          />
        </div>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="detailRow" type="success" @click="recordReview(detailRow, 'normal')">信息正常</el-button>
        <el-button v-if="detailRow" type="warning" plain @click="recordReview(detailRow, 'abnormal')">标记异常</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminService } from '@/services/admin'
import { propertyService } from '@/services/property'
import type { Property } from '@/types/property'

const loading = ref(false)
const search = ref('')
const statusFilter = ref('')
const allList = ref<Property[]>([])
const detailVisible = ref(false)
const detailRow = ref<Property | null>(null)

const filteredList = computed(() => {
  const q = search.value.trim().toLowerCase()
  return allList.value.filter((p) => {
    if (statusFilter.value && p.status !== statusFilter.value) return false
    if (!q) return true
    return [
      p.name,
      p.institute_name,
      p.institute_address,
      p.city,
      p.district,
      p.country,
    ].some((v) => String(v || '').toLowerCase().includes(q))
  })
})

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    available: '可租',
    rented: '已租',
    maintenance: '维修中',
  }
  return labels[status] || status
}

function statusTagType(status: string) {
  const types: Record<string, string> = {
    available: 'success',
    rented: 'info',
    maintenance: 'warning',
  }
  return types[status] || 'info'
}

function roomTypeOf(row: Property) {
  const hall = row.hall_count ? `${row.hall_count}厅` : ''
  return `${row.bedrooms || 0}室${hall}${row.bathrooms || 0}卫`
}

function locationOf(row: Property) {
  return [row.country, row.city, row.district].filter(Boolean).join(' / ') || '-'
}

function moneyOf(row: Property) {
  const currency = row.currency || 'CNY'
  return `${currency} ${row.base_rent ?? '-'}`
}

function coverOf(row: Property) {
  return row.image_urls?.[0] || row.primary_image_url || ''
}

function formatDate(date?: string) {
  return date ? new Date(date).toLocaleDateString('zh-CN') : '-'
}

function openDetail(row: Property) {
  detailRow.value = row
  detailVisible.value = true
}

async function fetchAll() {
  loading.value = true
  try {
    const result = await propertyService.list({ page_size: 500 })
    allList.value = result.items || []
  } catch {
    ElMessage.error('加载户型数据失败')
  } finally {
    loading.value = false
  }
}

async function recordReview(row: Property, result: 'normal' | 'abnormal') {
  const title = result === 'normal' ? '确认信息正常' : '标记信息异常'
  let note = ''
  try {
    if (result === 'abnormal') {
      const value = await ElMessageBox.prompt('填写异常说明', title, {
        inputType: 'textarea',
        inputPlaceholder: '例如：地址不完整、图片缺失、租金异常',
        inputValidator: (v) => Boolean(v && v.trim()),
        inputErrorMessage: '请填写异常说明',
      })
      note = value.value
    } else {
      await ElMessageBox.confirm(`确认「${row.name}」户型信息正常？`, title, { type: 'success' })
      note = '信息正常'
    }
    await adminService.reviewUnitType(row.id, result, note)
    ElMessage.success('审核记录已写入')
    detailVisible.value = false
  } catch {
    // cancelled
  }
}

onMounted(fetchAll)
</script>

<style scoped>
.admin-properties {
  box-sizing: border-box;
  width: 100%;
}

.admin-properties h2 {
  color: #303133;
  font-size: 22px;
  margin-bottom: 16px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

.search-box {
  max-width: 360px;
}

.review-table {
  cursor: pointer;
  width: 100%;
}

.cover {
  border-radius: 4px;
  height: 48px;
  width: 64px;
}

.empty-cover {
  color: #c0c4cc;
  font-size: 12px;
}

.image-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.detail-image {
  border-radius: 6px;
  height: 96px;
  width: 128px;
}
</style>
