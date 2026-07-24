<template>
  <div class="bookings-page" v-loading="loading">
    <h2>我的预订</h2>
    <el-empty v-if="!loading && bookings.length === 0" description="还没有预约，去看看心仪的房源吧">
      <el-button type="primary" @click="$router.push('/search')">去找房</el-button>
    </el-empty>
    <el-table v-else :data="bookings" stripe>
      <el-table-column label="房源" min-width="150">
        <template #default="{ row }">
          <span class="link-text" @click="$router.push('/room/'+row.property_id)">房源 #{{ row.property_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status==='approved'?'success':row.status==='pending'?'warning':'info'" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="scheduled_time" label="预约时间" width="170" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.status==='pending'" size="small" type="danger" text @click="cancelBooking(row)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bookingService } from '@/services/booking'
import type { Booking } from '@/types/booking'

const bookings = ref<Booking[]>([])
const loading = ref(false)

function statusLabel(s: string) {
  const m: Record<string,string> = { pending: '待确认', approved: '已同意', cancelled: '已取消', completed: '已完成' }
  return m[s] || s
}

onMounted(async () => {
  loading.value = true
  try { bookings.value = await bookingService.list() } catch { bookings.value = [] }
  loading.value = false
})

async function cancelBooking(b: Booking) {
  try {
    await ElMessageBox.confirm('确定取消预约？', '取消预约', { type: 'warning' })
    await bookingService.cancel(b.id)
    ElMessage.success('已取消')
    loading.value = true
    try { bookings.value = await bookingService.list() } catch { /* */ }
    loading.value = false
  } catch { /* */ }
}
</script>

<style scoped>
.bookings-page { padding: 20px; max-width: 900px; margin: 0 auto }
h2 { margin-bottom: 20px }
.link-text { color: #409eff; cursor: pointer }
.link-text:hover { text-decoration: underline }
</style>
