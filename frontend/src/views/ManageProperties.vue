<template>
  <div class="manage-page" v-loading="loading">
    <div class="page-header">
      <h2>{{ showRecycleBin ? '回收站' : '房源管理' }}</h2>
      <div class="header-actions">
        <el-button @click="router.push('/buildings')">🏢 管理公寓</el-button>
        <el-button :type="showRecycleBin ? 'danger' : 'default'" @click="toggleRecycleBin">
          {{ showRecycleBin ? '📋 返回房源列表' : '🗑 回收站' }}
        </el-button>
        <el-button
          :type="batchMode ? 'warning' : 'default'"
          @click="toggleBatchMode"
        >
          {{ batchMode ? '取消批量操作' : '📋 批量操作' }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="router.push('/property/create')">
          发布新房源
        </el-button>
      </div>
    </div>

    <!-- ═══════ 检索组件 ═══════ -->
    <div class="search-section">
      <div class="search-bar">
        <el-input
          v-model="searchKeyword"
          placeholder="输入房号/房源标题/地址快速检索房源"
          clearable
          @keyup.enter="doSearch"
          @clear="clearSearch"
          class="search-input"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="doSearch">搜索</el-button>
        <el-button @click="clearSearch">清空</el-button>
        <el-button @click="showFilterPanel = !showFilterPanel">
          {{ showFilterPanel ? '收起筛选 ▲' : '高级筛选 ▼' }}
        </el-button>
      </div>

      <!-- 折叠筛选面板 -->
      <div v-show="showFilterPanel" class="filter-panel">
        <el-row :gutter="16">
          <el-col :span="8">
            <div class="filter-label">所属公寓</div>
            <el-select v-model="filterInstituteId" placeholder="全部公寓" clearable style="width:100%">
              <el-option
                v-for="b in buildings"
                :key="b.id"
                :label="b.name + ' (' + getBuildingPropertyCount(b.id) + '间)'"
                :value="b.id"
              />
            </el-select>
          </el-col>
          <el-col :span="8">
            <div class="filter-label">户型</div>
            <el-select v-model="filterPropertyType" placeholder="全部户型" clearable style="width:100%">
              <el-option label="Studio / 单间" value="studio" />
              <el-option label="Ensuite / 套间" value="apartment" />
              <el-option label="Twin / 双人间" value="shared" />
              <el-option label="Double / 大床房" value="house" />
            </el-select>
          </el-col>
          <el-col :span="8">
            <div class="filter-label">状态</div>
            <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width:100%">
              <el-option label="可租" value="available" />
              <el-option label="已下架" value="offline" />
              <el-option label="审核中" value="pending_review" />
              <el-option label="已租" value="rented" />
              <el-option label="维护中" value="maintenance" />
            </el-select>
          </el-col>
        </el-row>
        <el-row :gutter="16" style="margin-top:12px">
          <el-col :span="8">
            <div class="filter-label">最低月租</div>
            <el-input-number v-model="filterPriceMin" :min="0" :max="999999" placeholder="不限" style="width:100%" controls-position="right" />
          </el-col>
          <el-col :span="8">
            <div class="filter-label">最高月租</div>
            <el-input-number v-model="filterPriceMax" :min="0" :max="999999" placeholder="不限" style="width:100%" controls-position="right" />
          </el-col>
          <el-col :span="8" style="display:flex;align-items:flex-end">
            <el-button type="primary" @click="applyFilters" style="margin-right:8px">确认筛选</el-button>
            <el-button @click="resetFilters">重置筛选条件</el-button>
          </el-col>
        </el-row>
      </div>

      <!-- 无匹配提示 -->
      <div v-if="searchNoResult" class="no-result-hint">
        未查询到匹配房源，请更换检索条件
      </div>
    </div>

    <!-- Empty: no buildings at all -->
    <el-empty
      v-if="!loading && !showRecycleBin && buildings.length === 0 && unlinkedProperties.length === 0"
      description="还没有创建任何公寓，请先创建公寓再发布房源"
    >
      <el-button type="primary" @click="router.push('/buildings')">前往创建公寓</el-button>
    </el-empty>
    <el-empty
      v-if="!loading && showRecycleBin && allProperties.length === 0"
      description="回收站为空"
    />

    <!-- Building groups -->
    <template v-for="building in buildings" :key="building.id">
      <el-card v-if="!showRecycleBin || getBuildingPropertyCount(building.id) > 0" shadow="never" class="building-card">
        <!-- Building header -->
        <div class="building-header" @click="toggleExpand(building.id)">
          <div class="building-info">
            <span class="building-icon">🏢</span>
            <span class="building-name">{{ building.name }}</span>
            <el-tag size="small" type="info" class="building-count">
              {{ getBuildingPropertyCount(building.id) }} 间房源
            </el-tag>
            <span v-if="building.address" class="building-addr">{{ building.address }}</span>
          </div>
          <div class="building-toggle">
            <el-icon :class="{ rotated: expandedIds.has(building.id) }">
              <ArrowDown />
            </el-icon>
          </div>
        </div>

        <!-- Expanded property table -->
        <div v-show="expandedIds.has(building.id)" class="building-properties">
          <el-table
            v-if="getBuildingProperties(building.id).length > 0"
            :data="getBuildingProperties(building.id)"
            :row-class-name="getRowClass"
            stripe
            size="small"
            style="width: 100%"
          >
            <el-table-column v-if="batchMode" width="40"><template #default="{ row }"><el-checkbox :model-value="selectedIds.has(row.id)" @change="toggleSelect(row.id)" /></template></el-table-column>
            <el-table-column prop="id" label="ID" width="55" />
            <el-table-column label="房号" width="90" show-overflow-tooltip>
              <template #default="{ row }">
                <span :style="{ color: row.room_number ? '#303133' : '#c0c4cc' }">
                  {{ row.room_number || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="户型" width="100">
              <template #default="{ row }">
                {{ row.bedrooms }}室{{ row.bathrooms }}卫
              </template>
            </el-table-column>
            <el-table-column label="月租" width="110">
              <template #default="{ row }">
                <span class="price-cell">¥{{ row.price_monthly?.toLocaleString() }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="property_type" label="类型" width="70">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ typeLabels[row.property_type as PropertyType] }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="85">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">
                  {{ statusLabels[row.status as PropertyStatus] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <template v-if="!batchMode">
                  <el-button size="small" text type="primary" @click="editProperty(row.id)">编辑</el-button>
                  <el-button size="small" text type="success" @click="manageImages(row.id)">图片</el-button>
                  <template v-if="!showRecycleBin">
                    <el-button
                      size="small" text
                      :type="row.status === 'offline' ? 'success' : 'warning'"
                      @click="toggleStatus(row, building.id)"
                    >
                      {{ row.status === 'offline' ? '上架' : '下架' }}
                    </el-button>
                    <el-popconfirm
                      title="确定删除该房源吗？"
                      confirm-button-text="删除"
                      cancel-button-text="取消"
                      @confirm="deleteProperty(row.id, building.id)"
                    >
                      <template #reference>
                        <el-button size="small" text type="danger">删除</el-button>
                      </template>
                    </el-popconfirm>
                  </template>
                  <template v-else>
                    <el-button size="small" text type="success" @click="restoreProperty(row.id, building.id)">恢复</el-button>
                    <el-popconfirm
                      title="确定永久删除该房源吗？此操作不可恢复"
                      confirm-button-text="永久删除"
                      cancel-button-text="取消"
                      @confirm="hardDeleteProperty(row.id, building.id)"
                    >
                      <template #reference>
                        <el-button size="small" text type="danger">硬删除</el-button>
                      </template>
                    </el-popconfirm>
                  </template>
                </template>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-building">
            该公寓下暂无房源 —
            <el-button size="small" type="primary" text @click="router.push('/property/create')">立即发布</el-button>
          </div>
        </div>
      </el-card>
    </template>

    <!-- Unlinked properties (no institute) -->
    <el-card v-if="!showRecycleBin && unlinkedProperties.length > 0" shadow="never" class="building-card unlinked-card">
      <div class="building-header" @click="toggleExpand(-1)">
        <div class="building-info">
          <span class="building-icon">⚠️</span>
          <span class="building-name">未绑定公寓</span>
          <el-tag size="small" type="warning" class="building-count">
            {{ unlinkedProperties.length }} 间房源
          </el-tag>
          <span class="building-addr hint">这些房源未关联任何公寓，建议尽快绑定</span>
        </div>
        <div class="building-toggle">
          <el-icon :class="{ rotated: expandedIds.has(-1) }">
            <ArrowDown />
          </el-icon>
        </div>
      </div>
      <div v-show="expandedIds.has(-1)" class="building-properties">
        <el-table :data="unlinkedProperties" :row-class-name="getRowClass" stripe size="small" style="width: 100%">
          <el-table-column v-if="batchMode" width="40"><template #default="{ row }"><el-checkbox :model-value="selectedIds.has(row.id)" @change="toggleSelect(row.id)" /></template></el-table-column>
          <el-table-column prop="id" label="ID" width="55" />
          <el-table-column label="房号" width="90" show-overflow-tooltip>
            <template #default="{ row }">
              <span :style="{ color: row.room_number ? '#303133' : '#c0c4cc' }">
                {{ row.room_number || '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column label="户型" width="100">
            <template #default="{ row }">
              {{ row.bedrooms }}室{{ row.bathrooms }}卫
            </template>
          </el-table-column>
          <el-table-column label="月租" width="110">
            <template #default="{ row }">
              <span class="price-cell">¥{{ row.price_monthly?.toLocaleString() }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="property_type" label="类型" width="70">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ typeLabels[row.property_type as PropertyType] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="85">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)">
                {{ statusLabels[row.status as PropertyStatus] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="350" fixed="right">
            <template #default="{ row }">
              <template v-if="!batchMode">
                <el-button size="small" text type="primary" @click="editProperty(row.id)">编辑</el-button>
                <el-button size="small" text type="success" @click="manageImages(row.id)">图片</el-button>
                <template v-if="!showRecycleBin">
                  <el-button size="small" text type="warning" @click="openBindDialog(row)">绑定</el-button>
                  <el-button
                    size="small" text
                    :type="row.status === 'offline' ? 'success' : 'warning'"
                    @click="toggleStatus(row, -1)"
                  >
                    {{ row.status === 'offline' ? '上架' : '下架' }}
                  </el-button>
                  <el-popconfirm
                    title="确定删除该房源吗？"
                    confirm-button-text="删除"
                    cancel-button-text="取消"
                    @confirm="deleteProperty(row.id, -1)"
                  >
                    <template #reference>
                      <el-button size="small" text type="danger">删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
                <template v-else>
                  <el-button size="small" text type="success" @click="restoreProperty(row.id, -1)">恢复</el-button>
                  <el-popconfirm
                    title="确定永久删除该房源吗？此操作不可恢复"
                    confirm-button-text="永久删除"
                    cancel-button-text="取消"
                    @confirm="hardDeleteProperty(row.id, -1)"
                  >
                    <template #reference>
                      <el-button size="small" text type="danger">硬删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- 分页（仅回收站模式显示） -->
    <div v-if="showRecycleBin && totalPages > 1" style="display:flex;justify-content:center;margin:24px 0">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>

    <!-- 绑定公寓弹窗 -->
    <el-dialog v-model="showBindDialog" title="绑定到公寓" width="420px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="房源">
          <span style="font-weight:600">{{ bindTarget?.title }}</span>
        </el-form-item>
        <el-form-item label="目标公寓" required>
          <el-select v-model="bindInstituteId" placeholder="请选择要绑定的公寓" filterable style="width:100%">
            <el-option v-for="b in buildings" :key="b.id" :label="b.name + (b.address ? ' — ' + b.address : '')" :value="b.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" :loading="binding" :disabled="!bindInstituteId" @click="doBind">
          确认绑定
        </el-button>
      </template>
    </el-dialog>

    <!-- End of list -->
    <div
      v-if="!loading && !showRecycleBin && buildings.length > 0 && allProperties.length === 0"
      style="text-align: center; padding: 40px; color: #909399"
    >
      公寓已创建，但还没有发布房源 —
      <el-button type="primary" text @click="router.push('/property/create')">前往发布</el-button>
    </div>

    <!-- ═══════ 批量操作底栏 ═══════ -->
    <transition name="batch-slide">
      <div v-if="batchMode && selectedIds.size > 0" class="batch-bar">
        <div class="batch-bar-inner">
          <span class="batch-count">已选择 <strong>{{ selectedIds.size }}</strong> 间房源</span>
          <div class="batch-actions">
            <template v-if="!showRecycleBin">
              <el-button type="success" :loading="batchOperating" @click="batchSetStatus('available')">
                批量上架
              </el-button>
              <el-button type="warning" :loading="batchOperating" @click="batchSetStatus('offline')">
                批量下架
              </el-button>
              <el-button :loading="batchOperating" @click="openBatchBindDialog">
                📦 批量绑定公寓
              </el-button>
              <el-dropdown trigger="click" @command="handleBatchImageCmd">
                <el-button type="primary" :loading="batchOperating">
                  🖼 批量图片操作 <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="set">📤 批量设置图片</el-dropdown-item>
                    <el-dropdown-item command="clearShared" divided>🧹 清空公共图片（保留封面）</el-dropdown-item>
                    <el-dropdown-item command="clearAll">🗑 清空全部图片</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-popconfirm
                title="确定批量删除已选房源吗？此操作不可恢复"
                confirm-button-text="确认删除"
                cancel-button-text="取消"
                @confirm="batchDelete"
              >
                <template #reference>
                  <el-button type="danger" :loading="batchOperating">🗑 批量删除</el-button>
                </template>
              </el-popconfirm>
            </template>
            <template v-else>
              <el-button type="success" :loading="batchOperating" @click="batchRestore">
                批量恢复
              </el-button>
              <el-popconfirm
                title="确定永久删除已选房源吗？此操作完全不可恢复"
                confirm-button-text="永久删除"
                cancel-button-text="取消"
                @confirm="batchHardDelete"
              >
                <template #reference>
                  <el-button type="danger" :loading="batchOperating">🗑 批量硬删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </div>
          <el-button text @click="toggleBatchMode">取消</el-button>
        </div>
      </div>
    </transition>

    <!-- 批量绑定公寓弹窗 -->
    <el-dialog v-model="showBatchBindDialog" title="批量绑定到公寓" width="420px" :close-on-click-modal="false">
      <p style="color:#606266;margin-bottom:16px">将已选择的 <strong>{{ selectedIds.size }}</strong> 间房源统一绑定到目标公寓</p>
      <el-form label-width="80px">
        <el-form-item label="目标公寓" required>
          <el-select v-model="batchBindInstituteId" placeholder="请选择目标公寓" filterable style="width:100%">
            <el-option v-for="b in buildings" :key="b.id" :label="b.name + (b.address ? ' — ' + b.address : '')" :value="b.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchBindDialog = false">取消</el-button>
        <el-button type="primary" :loading="batchOperating" :disabled="!batchBindInstituteId" @click="doBatchBind">
          确认绑定 {{ selectedIds.size }} 间房源
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量设置图片弹窗 -->
    <el-dialog v-model="showBatchImageDialog" title="批量设置图片" width="560px" :close-on-click-modal="false">
      <p style="color:#606266;margin-bottom:8px">
        将下方图片应用到已选择的 <strong>{{ selectedIds.size }}</strong> 间房源（每间都会收到相同的图片）
      </p>
      <p style="color:#909399;font-size:12px;margin-bottom:16px">
        已选房源若已有图片，新图片会追加到末尾，不会覆盖
      </p>
      <el-upload
        v-model:file-list="batchImageFiles"
        :auto-upload="false"
        list-type="picture-card"
        multiple
        :limit="10"
        accept="image/jpeg,image/png,image/webp"
        :before-upload="beforeBatchImageUpload"
        drag
      >
        <el-icon><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">仅支持 JPG/PNG/WebP，单文件不超过 5MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showBatchImageDialog = false">取消</el-button>
        <el-button type="primary" :loading="batchOperating" :disabled="batchImageFiles.length === 0" @click="doBatchImages">
          应用到 {{ selectedIds.size }} 间房源
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, ArrowDown, UploadFilled, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePropertyStore } from '@/stores/property'
import { useAuthStore } from '@/stores/auth'
import { buildingService, type Building } from '@/services/building'
import { storeToRefs } from 'pinia'
import type { Property, PropertyStatus, PropertyType } from '@/types/property'
import { nextTick } from 'vue'

const router = useRouter()
const propertyStore = usePropertyStore()
const authStore = useAuthStore()
const { loading, properties: allProperties, total, page, pageSize, totalPages } = storeToRefs(propertyStore)

const buildings = ref<Building[]>([])
const expandedIds = ref<Set<number>>(new Set())
const loadingData = ref(false)
const showRecycleBin = ref(false)

// ── 检索筛选 ──
const searchKeyword = ref('')
const showFilterPanel = ref(false)
const filterInstituteId = ref<number | null>(null)
const filterPropertyType = ref<string | null>(null)
const filterStatus = ref<string | null>(null)
const filterPriceMin = ref<number | undefined>(undefined)
const filterPriceMax = ref<number | undefined>(undefined)
const highlightedIds = ref<Set<number>>(new Set())
const searchNoResult = ref(false)
const isSearching = ref(false)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

function doSearch() {
  const kw = searchKeyword.value.trim()
  if (!kw && !filterInstituteId.value && !filterPropertyType.value && !filterStatus.value && filterPriceMin.value === undefined && filterPriceMax.value === undefined) {
    ElMessage.info('请输入检索关键词或设置筛选条件')
    return
  }
  applyFilters()
}

function clearSearch() {
  searchKeyword.value = ''
  highlightedIds.value = new Set()
  searchNoResult.value = false
  resetFilters()
}

function applyFilters() {
  isSearching.value = true
  searchNoResult.value = false
  const user = authStore.user
  if (!user) { isSearching.value = false; return }

  page.value = 1  // reset to first page on new search
  const kw = searchKeyword.value.trim()

  propertyStore.fetchList({
    page: 1, page_size: 500, landlord_id: user.id,
    keyword: kw || undefined,
    property_type: filterPropertyType.value || undefined,
    status: filterStatus.value || undefined,
    price_min: filterPriceMin.value,
    price_max: filterPriceMax.value,
  }).then(() => {
    let filtered = [...propertyStore.properties]
    if (filterInstituteId.value) {
      filtered = filtered.filter(p => p.institute_id === filterInstituteId.value)
    }
    const matches = new Set<number>()
    if (kw) {
      const lower = kw.toLowerCase()
      for (const p of filtered) {
        if (
          (p.room_number && p.room_number.toLowerCase().includes(lower)) ||
          (p.title && p.title.toLowerCase().includes(lower)) ||
          (p.address && p.address.toLowerCase().includes(lower))
        ) { matches.add(p.id) }
      }
    }
    if (filtered.length === 0) {
      searchNoResult.value = true
    } else {
      searchNoResult.value = false
      const filteredIds = new Set(filtered.map(p => p.id))
      highlightedIds.value = kw ? matches : filteredIds
      if (highlightedIds.value.size > 0) scrollToFirstMatch(highlightedIds.value)
      if (highlightTimer) clearTimeout(highlightTimer)
      highlightTimer = setTimeout(() => { highlightedIds.value = new Set() }, 3000)
    }
    isSearching.value = false
  }).catch(() => { isSearching.value = false })
}

function scrollToFirstMatch(_ids: Set<number>) {
  nextTick(() => {
    // 找到第一个高亮行并滚动到它
    const el = document.querySelector('.highlight-row')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

function resetFilters() {
  filterInstituteId.value = null
  filterPropertyType.value = null
  filterStatus.value = null
  filterPriceMin.value = undefined
  filterPriceMax.value = undefined
  highlightedIds.value = new Set()
  searchNoResult.value = false
  if (!searchKeyword.value.trim()) {
    loadData()
  }
}

// ── 批量操作 ──
const batchMode = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const batchOperating = ref(false)
const showBatchBindDialog = ref(false)
const batchBindInstituteId = ref<number | null>(null)

function toggleBatchMode() {
  batchMode.value = !batchMode.value
  selectedIds.value = new Set()
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

async function batchSetStatus(status: PropertyStatus) {
  if (selectedIds.value.size === 0) return
  batchOperating.value = true
  try {
    const result = await propertyStore.batchUpdateStatus(Array.from(selectedIds.value), status)
    if (result.success > 0) {
      ElMessage.success(`已批量${status === 'available' ? '上架' : '下架'} ${result.success} 间房源`)
    }
    if (result.failed > 0) {
      ElMessage.warning(`${result.failed} 间操作失败`)
    }
    selectedIds.value = new Set()
    await loadData()
  } catch {
    ElMessage.error('批量操作失败，请重试')
  } finally {
    batchOperating.value = false
  }
}

async function batchDelete() {
  if (selectedIds.value.size === 0) return
  batchOperating.value = true
  try {
    const result = await propertyStore.batchDelete(Array.from(selectedIds.value))
    ElMessage.success(`已批量删除 ${result.success} 间房源`)
    selectedIds.value = new Set()
    await loadData()
  } catch {
    ElMessage.error('批量删除失败，请重试')
  } finally {
    batchOperating.value = false
  }
}

async function batchRestore() {
  if (selectedIds.value.size === 0) return
  batchOperating.value = true
  try {
    const result = await propertyStore.batchRestore(Array.from(selectedIds.value))
    ElMessage.success(`已批量恢复 ${result.success} 间房源`)
    selectedIds.value = new Set()
    await loadData()
  } catch {
    ElMessage.error('批量恢复失败，请重试')
  } finally {
    batchOperating.value = false
  }
}

async function batchHardDelete() {
  if (selectedIds.value.size === 0) return
  batchOperating.value = true
  try {
    const result = await propertyStore.batchHardDelete(Array.from(selectedIds.value))
    ElMessage.success(`已永久删除 ${result.success} 间房源`)
    selectedIds.value = new Set()
    await loadData()
  } catch {
    ElMessage.error('批量硬删除失败，请重试')
  } finally {
    batchOperating.value = false
  }
}

function openBatchBindDialog() {
  if (selectedIds.value.size === 0) return
  batchBindInstituteId.value = null
  showBatchBindDialog.value = true
}

// ── 批量设图 ──
const showBatchImageDialog = ref(false)
const batchImageFiles = ref<any[]>([])

function beforeBatchImageUpload(file: any) {
  const isValidType = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
  if (!isValidType) { ElMessage.error('仅支持 JPG、PNG、WebP 格式'); return false }
  const isValidSize = file.size <= 5 * 1024 * 1024
  if (!isValidSize) { ElMessage.error('图片大小不能超过 5MB'); return false }
  return true
}

function handleBatchImageCmd(cmd: string) {
  switch (cmd) {
    case 'set': openBatchImageDialog(); break
    case 'clearShared': batchClearSharedImages(); break
    case 'clearAll': batchClearAllImages(); break
  }
}

function openBatchImageDialog() {
  if (selectedIds.value.size === 0) return
  batchImageFiles.value = []
  showBatchImageDialog.value = true
}

async function batchClearAllImages() {
  if (selectedIds.value.size === 0) return
  try {
    await ElMessageBox.prompt('请输入「确认清空图片」以确认操作', '清空全部图片', {
      type: 'warning',
      confirmButtonText: '确认清空',
      inputPattern: /^确认清空图片$/,
      inputErrorMessage: '请输入「确认清空图片」',
    })
  } catch { return }
  batchOperating.value = true
  let done = 0; const total = selectedIds.value.size
  try {
    // 先获取所有图片ID
    for (const id of selectedIds.value) {
      try {
        const images = await propertyStore.fetchImagesRef(id)
        for (const img of images) {
          await propertyStore.deleteImage(id, img.id)
        }
        done++
      } catch { /* skip */ }
    }
    ElMessage.success(`已清空 ${done} 间房源的图片`)
    selectedIds.value = new Set()
  } catch {
    ElMessage.error(`完成 ${done}/${total} 间，部分失败`)
  } finally {
    batchOperating.value = false
  }
}

async function batchClearSharedImages() {
  if (selectedIds.value.size === 0) return
  try {
    await ElMessageBox.prompt('请输入「确认清空图片」以确认操作', '清空公共图片', {
      type: 'warning',
      confirmButtonText: '确认清空',
      inputPattern: /^确认清空图片$/,
      inputErrorMessage: '请输入「确认清空图片」',
    })
  } catch { return }
  batchOperating.value = true
  let done = 0; const total = selectedIds.value.size
  try {
    for (const id of selectedIds.value) {
      try {
        const images = await propertyStore.fetchImagesRef(id)
        // 只删除非封面图片（公共图）
        for (const img of images) {
          if (!img.is_primary) {
            await propertyStore.deleteImage(id, img.id)
          }
        }
        done++
      } catch { /* skip */ }
    }
    ElMessage.success(`已清空 ${done} 间房源的公共图片`)
  } catch {
    ElMessage.error(`完成 ${done}/${total} 间，部分失败`)
  } finally {
    batchOperating.value = false
  }
}

async function doBatchImages() {
  if (batchImageFiles.value.length === 0 || selectedIds.value.size === 0) return
  batchOperating.value = true
  const rawFiles = batchImageFiles.value.map((f: any) => f.raw).filter(Boolean)
  let done = 0
  const total = selectedIds.value.size
  try {
    for (const id of selectedIds.value) {
      await propertyStore.uploadImages(id, rawFiles)
      done++
    }
    ElMessage.success(`已为 ${done} 间房源批量上传 ${rawFiles.length} 张图片`)
    batchImageFiles.value = []
    showBatchImageDialog.value = false
  } catch {
    ElMessage.error(`完成 ${done}/${total} 间，部分失败`)
  } finally {
    batchOperating.value = false
  }
}

async function doBatchBind() {
  if (!batchBindInstituteId.value || selectedIds.value.size === 0) return
  batchOperating.value = true
  let done = 0
  const total = selectedIds.value.size
  try {
    for (const id of selectedIds.value) {
      await propertyStore.update(id, { institute_id: batchBindInstituteId.value })
      done++
    }
    ElMessage.success(`已绑定 ${done} 间房源到公寓`)
    selectedIds.value = new Set()
    showBatchBindDialog.value = false
    await loadData()
  } catch {
    ElMessage.error(`完成 ${done}/${total} 间，部分失败`)
  } finally {
    batchOperating.value = false
  }
}

// ── 绑定公寓（单个） ──
const showBindDialog = ref(false)
const binding = ref(false)
const bindTarget = ref<Property | null>(null)
const bindInstituteId = ref<number | null>(null)

function openBindDialog(property: Property) {
  bindTarget.value = property
  bindInstituteId.value = null
  showBindDialog.value = true
}

async function doBind() {
  if (!bindTarget.value || !bindInstituteId.value) return
  binding.value = true
  try {
    await propertyStore.update(bindTarget.value.id, { institute_id: bindInstituteId.value })
    ElMessage.success(`已绑定到公寓`)
    showBindDialog.value = false
    await loadData()
    expandedIds.value.add(-1)
  } catch (e: any) {
    ElMessage.error('绑定失败，请重试')
  } finally {
    binding.value = false
  }
}

// Status/type labels (same as before)
const statusLabels: Record<PropertyStatus, string> = {
  available: '可租',
  pending_review: '审核中',
  rented: '已租',
  maintenance: '维护中',
  offline: '已下架',
}
const typeLabels: Record<PropertyType, string> = {
  apartment: '公寓',
  house: '别墅',
  studio: '单间',
  shared: '合租',
}

function statusTagType(status: PropertyStatus): string {
  const map: Record<PropertyStatus, string> = {
    available: 'success',
    pending_review: 'warning',
    rented: 'warning',
    maintenance: 'info',
    offline: 'danger',
  }
  return map[status]
}

// Group properties by institute_id
const propertyGroups = computed(() => {
  const groups = new Map<number, Property[]>()
  for (const p of allProperties.value) {
    const key = p.institute_id ?? -1
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(p)
  }
  return groups
})

const unlinkedProperties = computed(() => propertyGroups.value.get(-1) || [])

function getBuildingProperties(buildingId: number): Property[] {
  return propertyGroups.value.get(buildingId) || []
}

function getRowClass({ row }: { row: Property }): string {
  return highlightedIds.value.has(row.id) ? 'highlight-row' : ''
}

function getBuildingPropertyCount(buildingId: number): number {
  return getBuildingProperties(buildingId).length
}

function toggleExpand(id: number) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
  // Trigger reactivity
  expandedIds.value = new Set(expandedIds.value)
}

// Operations (same logic as before)
function editProperty(id: number) {
  router.push('/property/' + id + '/edit')
}

function manageImages(id: number) {
  router.push('/property/' + id + '/images')
}

async function toggleStatus(property: Property, buildingId: number) {
  const newStatus: PropertyStatus = property.status === 'offline' ? 'available' : 'offline'
  console.log('[toggleStatus] id=%d %s -> %s', property.id, property.status, newStatus)
  try {
    const updated = await propertyStore.update(property.id, { status: newStatus })
    console.log('[toggleStatus] server returned status=%s', updated.status)
    ElMessage.success(newStatus === 'offline' ? '已下架' : '已上架')
    // Update in place in the store's properties array
    const storeProps = propertyStore.properties
    const idx = storeProps.findIndex(p => p.id === property.id)
    if (idx !== -1) {
      storeProps[idx] = { ...storeProps[idx], ...updated }
    }
    expandedIds.value.add(buildingId)
  } catch (e: any) {
    console.error('[toggleStatus] failed', e)
    ElMessage.error('操作失败，请检查网络连接')
  }
}

async function deleteProperty(id: number, buildingId: number) {
  try {
    await propertyStore.remove(id)
    ElMessage.success('房源已删除')
    await loadData()
    if (buildingId !== -1) expandedIds.value.add(buildingId)
  } catch (e: any) {
    console.error('deleteProperty failed', e)
    ElMessage.error('删除失败，请重试')
  }
}

function toggleRecycleBin() {
  showRecycleBin.value = !showRecycleBin.value
  page.value = 1
  loadData()
}

async function restoreProperty(id: number, buildingId: number) {
  try {
    await propertyStore.restoreProperty(id)
    ElMessage.success('房源已恢复')
    await loadData()
    if (buildingId !== -1) expandedIds.value.add(buildingId)
  } catch {
    ElMessage.error('恢复失败，请重试')
  }
}

async function hardDeleteProperty(id: number, buildingId: number) {
  try {
    await propertyStore.hardDeleteProperty(id)
    ElMessage.success('房源已永久删除')
    await loadData()
    if (buildingId !== -1) expandedIds.value.add(buildingId)
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

function onPageChange(p: number) {
  page.value = p
  loadData()
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  loadData()
}

async function loadData() {
  loadingData.value = true
  try {
    const user = authStore.user
    if (!user) return

    if (showRecycleBin.value) {
      await propertyStore.fetchRecycleBin({ page: page.value, page_size: pageSize.value, landlord_id: user.id })
    } else {
      // 管理页加载全部房源，客户端按楼栋分组后再分页
      const params: any = { page: 1, page_size: 500, landlord_id: user.id }
      if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
      if (filterPropertyType.value) params.property_type = filterPropertyType.value
      if (filterStatus.value) params.status = filterStatus.value
      if (filterPriceMin.value !== undefined) params.price_min = filterPriceMin.value
      if (filterPriceMax.value !== undefined) params.price_max = filterPriceMax.value
      await propertyStore.fetchList(params)
    }

    const blds = await buildingService.list({ limit: 200 })
    buildings.value = blds
  } finally {
    loadingData.value = false
  }
}

onMounted(async () => {
  await loadData()
  // 首次加载展开所有楼栋
  const allIds = new Set<number>()
  for (const b of buildings.value) allIds.add(b.id)
  if (unlinkedProperties.value.length > 0) allIds.add(-1)
  expandedIds.value = allIds
})
</script>

<style scoped>
.manage-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* ── Search Section ── */
.search-section {
  margin-bottom: 20px;
}

.search-bar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-input {
  flex: 1;
}

.filter-panel {
  margin-top: 12px;
  padding: 16px;
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.filter-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  font-weight: 500;
}

.no-result-hint {
  text-align: center;
  color: #909399;
  padding: 20px;
  font-size: 14px;
}

/* ── Highlight row ── */
:deep(.highlight-row) {
  animation: highlightFade 3s ease-out forwards;
}

@keyframes highlightFade {
  0%   { background-color: #e6f7ff; }
  70%  { background-color: #e6f7ff; }
  100% { background-color: transparent; }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  color: #303133;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
}

/* ── Building Card ── */
.building-card {
  margin-bottom: 16px;
  border-radius: 12px;
  transition: box-shadow 0.2s;
}

.building-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.building-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  cursor: pointer;
  user-select: none;
}

.building-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.building-icon {
  font-size: 20px;
}

.building-name {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
}

.building-count {
  flex-shrink: 0;
}

.building-addr {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.building-addr.hint {
  color: #e6a23c;
}

.building-toggle {
  flex-shrink: 0;
  margin-left: 16px;
  color: #909399;
  transition: transform 0.25s;
}

.building-toggle .el-icon {
  font-size: 18px;
  transition: transform 0.25s;
}

.building-toggle .el-icon.rotated {
  transform: rotate(180deg);
}

/* ── Property Table inside building ── */
.building-properties {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.price-cell {
  color: #f56c6c;
  font-weight: 600;
}

.empty-building {
  text-align: center;
  padding: 24px;
  color: #909399;
  font-size: 14px;
}

/* ── Unlinked card ── */
.unlinked-card {
  border: 2px dashed #e6a23c;
}

/* ── Batch bar ── */
.batch-bar {
  position: fixed;
  bottom: 0;
  left: 200px;
  right: 0;
  z-index: 300;
  background: #fff;
  border-top: 2px solid #e6a23c;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.12);
  padding: 0;
}

.batch-bar-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
}

.batch-count {
  font-size: 15px;
  color: #303133;
  white-space: nowrap;
}

.batch-count strong {
  color: #e6a23c;
  font-size: 18px;
}

.batch-actions {
  display: flex;
  gap: 8px;
  flex: 1;
  justify-content: center;
}

/* ── Slide transition ── */
.batch-slide-enter-active,
.batch-slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.batch-slide-enter-from,
.batch-slide-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
