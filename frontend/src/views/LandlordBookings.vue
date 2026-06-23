<template>
  <div class="bookings-page" v-loading="loading">
    <h2>收到的预约</h2>

    <el-empty v-if="!loading && bookings.length === 0" description="暂无预约" />

    <el-card v-for="booking in bookings" :key="booking.id" shadow="hover" class="booking-card">
      <div class="booking-header">
        <span class="booking-id">预约 #{{ booking.id }}</span>
        <el-tag :type="statusTagType(booking.status)">{{ statusLabel(booking.status) }}</el-tag>
      </div>
      <div class="booking-body">
        <div class="booking-meta">
          <p><strong>租客 ID：</strong>{{ booking.tenant_id }}</p>
          <p><strong>房源 ID：</strong>{{ booking.property_id }}</p>
          <p v-if="booking.scheduled_date"><strong>预约时间：</strong>{{ booking.scheduled_date }}</p>
          <p v-if="booking.message"><strong>留言：</strong>{{ booking.message }}</p>
        </div>
        <div class="booking-actions" v-if="booking.status === 'pending'">
          <el-button type="success" size="small" @click="handleApprove(booking.id)">
            批准
          </el-button>
          <el-button type="danger" size="small" @click="handleReject(booking.id)">
            拒绝
          </el-button>
        </div>
      </div>
      <div class="booking-footer">
        <span class="booking-time">{{ formatDate(booking.created_at) }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bookingService } from '@/services/booking'
import type { Booking } from '@/types/booking'

const bookings = ref<Booking[]>([])
const loading = ref(false)

const statusLabels: Record<string, string> = {
  pending: '待处理',
  approved: '已批准',
  rejected: '已拒绝',
  cancelled: '已取消',
  completed: '已完成',
}

const statusTagMap: Record<string, string> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  cancelled: 'info',
  completed: '',
}

function statusLabel(status: string) {
  return statusLabels[status] || status
}

function statusTagType(status: string) {
  return statusTagMap[status] || 'info'
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

async function fetchBookings() {
  loading.value = true
  try {
    bookings.value = await bookingService.list()
  } finally {
    loading.value = false
  }
}

async function handleApprove(bookingId: number) {
  try {
    await ElMessageBox.confirm('确定批准此预约吗？', '确认批准', {
      confirmButtonText: '批准',
      cancelButtonText: '取消',
      type: 'success',
    })
    await bookingService.updateStatus(bookingId, 'approved')
    ElMessage.success('预约已批准')
    await fetchBookings()
  } catch {
    // cancelled or error
  }
}

async function handleReject(bookingId: number) {
  try {
    await ElMessageBox.confirm('确定拒绝此预约吗？', '确认拒绝', {
      confirmButtonText: '拒绝',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await bookingService.updateStatus(bookingId, 'rejected')
    ElMessage.success('预约已拒绝')
    await fetchBookings()
  } catch {
    // cancelled or error
  }
}

onMounted(fetchBookings)
</script>

<style scoped>
.bookings-page {
  max-width: 800px;
  margin: 0 auto;
}

.bookings-page h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 20px;
}

.booking-card {
  margin-bottom: 16px;
}

.booking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.booking-id {
  font-weight: 600;
  color: #409eff;
}

.booking-body {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.booking-meta p {
  margin: 4px 0;
  font-size: 14px;
  color: #606266;
}

.booking-footer {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
}

.booking-time {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
