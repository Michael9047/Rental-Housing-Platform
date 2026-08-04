<template>
  <div class="page-container">
    <h2 class="section-title">合约管理</h2>

    <el-table :data="contracts" v-loading="loading" stripe empty-text="暂无合约">
      <el-table-column prop="agreement_number" label="合同编号" width="180" />
      <el-table-column prop="tenant_name" label="租客姓名" width="140" />
      <el-table-column prop="unit_type_name" label="户型" min-width="160" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'signed' ? 'success' : 'info'" size="small">
            {{ row.status === 'signed' ? '已签署' : row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="signed_at" label="签署日期" width="130">
        <template #default="{ row }">
          {{ row.signed_at ? row.signed_at.slice(0, 10) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="generated_at" label="生成日期" width="130">
        <template #default="{ row }">
          {{ row.generated_at ? row.generated_at.slice(0, 10) : '-' }}
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      @current-change="loadContracts"
      style="margin-top: 20px; justify-content: center"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const loading = ref(false)
const contracts = ref<any[]>([])
const page = ref(1)
const pageSize = 20
const total = ref(0)

async function loadContracts() {
  loading.value = true
  try {
    const res = await api.get('/contracts/landlord', { params: { page: page.value, page_size: pageSize } })
    contracts.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e: any) {
    console.error('[LandlordContracts]', e?.message || e)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadContracts())
</script>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 20px;
}
</style>
