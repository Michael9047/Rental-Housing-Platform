<template>
  <div class="admin-properties" v-loading="loading">
    <h2>房源审核</h2>

    <!-- Tab bar -->
    <el-tabs v-model="activeTab" @tab-change="onTabChange" class="review-tabs">
      <el-tab-pane :label="'待审核 (' + pendingList.length + ')'" name="pending" />
      <el-tab-pane :label="'已上架 (' + approvedList.length + ')'" name="approved" />
      <el-tab-pane :label="'全部 (' + allList.length + ')'" name="all" />
    </el-tabs>

    <el-input
      v-model="search"
      placeholder="搜索房源标题或地址..."
      clearable
      class="search-box"
    />

    <!-- Review table -->
    <el-table :data="filteredList" stripe max-height="600" class="review-table"
              @row-click="onRowClick">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="封面" width="80">
        <template #default="{ row }">
          <el-image
            v-if="row.images?.length"
            :src="'/api/v1/uploads/' + row.images[0].filename"
            fit="cover"
            style="width:60px;height:45px;border-radius:4px"
          />
          <span v-else style="color:#c0c4cc;font-size:12px">无图</span>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="district" label="区域" width="90" />
      <el-table-column label="月租" width="100" align="right">
        <template #default="{ row }">{{ row.price_monthly }} 元</template>
      </el-table-column>
      <el-table-column label="面积" width="80" align="right">
        <template #default="{ row }">{{ row.area_sqm || '-' }}㎡</template>
      </el-table-column>
      <el-table-column label="户型" width="80">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ typeLabel(row.property_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'pending_review'" type="warning" size="small">
            ⏳ 待审核
          </el-tag>
          <el-tag v-else-if="row.status === 'available'" type="success" size="small">
            ✅ 已上架
          </el-tag>
          <el-tag v-else :type="statusTagType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="发布时间" width="110">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'pending_review'">
            <el-button type="success" size="small" @click="approve(row.id)">
              ✅ 通过
            </el-button>
            <el-button type="danger" size="small" plain @click="reject(row.id)">
              ❌ 驳回
            </el-button>
          </template>
          <template v-else>
            <el-select
              :model-value="row.status"
              size="small"
              @change="(val: string) => handleStatusChange(row.id, val)"
            >
              <el-option label="上架" value="available" />
              <el-option label="下架" value="offline" />
              <el-option label="维护" value="maintenance" />
            </el-select>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !filteredList.length" :description="emptyText" />

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="房源详情" width="700px">
      <template v-if="detailRow">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标题" :span="2">{{ detailRow.title }}</el-descriptions-item>
          <el-descriptions-item label="地址">{{ detailRow.address }}</el-descriptions-item>
          <el-descriptions-item label="区域">{{ detailRow.district }}</el-descriptions-item>
          <el-descriptions-item label="月租">{{ detailRow.price_monthly }} 元</el-descriptions-item>
          <el-descriptions-item label="面积">{{ detailRow.area_sqm || '-' }} ㎡</el-descriptions-item>
          <el-descriptions-item label="户型">{{ typeLabel(detailRow.property_type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detailRow.status) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detailRow.description || '无' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailRow.images?.length" style="margin-top:16px">
          <h4>房源图片</h4>
          <div class="image-grid">
            <el-image
              v-for="img in detailRow.images"
              :key="img.id"
              :src="'/api/v1/uploads/' + img.filename"
              fit="cover"
              style="width:120px;height:90px;border-radius:6px;margin:4px"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="detailVisible=false">关闭</el-button>
        <template v-if="detailRow?.status === 'pending_review'">
          <el-button type="success" @click="approve(detailRow!.id);detailVisible=false">通过审核</el-button>
          <el-button type="danger" @click="reject(detailRow!.id);detailVisible=false">驳回</el-button>
        </template>
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
const activeTab = ref('pending')
const pendingList = ref<Property[]>([])
const approvedList = ref<Property[]>([])
const allList = ref<Property[]>([])
const detailVisible = ref(false)
const detailRow = ref<Property | null>(null)

/** 当前 tab 的列表 */
const currentList = computed(() => {
  if (activeTab.value === 'pending') return pendingList.value
  if (activeTab.value === 'approved') return approvedList.value
  return allList.value
})

/** 搜索过滤 */
const filteredList = computed(() => {
  if (!search.value) return currentList.value
  const q = search.value.toLowerCase()
  return currentList.value.filter(
    (p) => p.title.toLowerCase().includes(q) ||
           p.address?.toLowerCase().includes(q) ||
           p.district.toLowerCase().includes(q)
  )
})

const emptyText = computed(() => {
  if (activeTab.value === 'pending') return '暂无待审核房源 🎉'
  return '暂无房源数据'
})

function typeLabel(t?: string) {
  const m: Record<string, string> = { apartment: '公寓', house: '别墅', studio: '单间', shared: '合租' }
  return m[t || ''] || t || '-'
}

function statusLabel(s: string) {
  const m: Record<string, string> = { available: '已上架', pending_review: '待审核', rented: '已租', maintenance: '维护中', offline: '已下架' }
  return m[s] || s
}

function statusTagType(s: string) {
  const m: Record<string, string> = { available: 'success', rented: 'info', maintenance: 'warning', offline: 'danger' }
  return m[s] || 'info'
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('zh-CN')
}

/** 点击行查看详情 */
function onRowClick(row: Property) {
  detailRow.value = row
  detailVisible.value = true
}

/** 加载全部数据 */
async function fetchAll() {
  loading.value = true
  try {
    const all = await propertyService.list({ page_size: 200 })
    allList.value = all.items
    pendingList.value = all.items.filter(p => (p as any).status === 'pending_review')
    approvedList.value = all.items.filter(p => p.status === 'available')
  } catch {
    ElMessage.error('加载房源数据失败')
  } finally {
    loading.value = false
  }
}

function onTabChange() {
  search.value = ''
}

/** 通过审核 → 上架 */
async function approve(id: number) {
  try {
    await adminService.moderateProperty(id, 'available')
    ElMessage.success('已通过审核，房源已上架')
    await fetchAll()
  } catch {
    ElMessage.error('操作失败')
  }
}

/** 驳回 → 下架 */
async function reject(id: number) {
  try {
    await ElMessageBox.confirm('确认驳回该房源？驳回后将下架。', '驳回确认', { type: 'warning' })
    await adminService.moderateProperty(id, 'offline')
    ElMessage.success('已驳回，房源已下架')
    await fetchAll()
  } catch {
    // cancelled
  }
}

async function handleStatusChange(propertyId: number, status: string) {
  try {
    await adminService.moderateProperty(propertyId, status)
    ElMessage.success('状态已更新')
    await fetchAll()
  } catch {
    ElMessage.error('更新失败')
  }
}

onMounted(fetchAll)
</script>

<style scoped>
.admin-properties {
  max-width: 1200px;
  margin: 0 auto;
}

.admin-properties h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 16px;
}

.review-tabs {
  margin-bottom: 12px;
}

.search-box {
  max-width: 400px;
  margin-bottom: 12px;
}

.review-table {
  cursor: pointer;
}
</style>
