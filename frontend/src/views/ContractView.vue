<template>
  <div class="contract-page" v-loading="loading">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>📄 电子合同</h2>
    </div>

    <el-empty v-if="!loading && !booking" description="合同数据未找到" />

    <template v-if="booking">
      <!-- Contract Preview Card -->
      <el-card shadow="never" class="contract-card">
        <div class="contract-watermark">电子合同</div>

        <div class="contract-header">
          <h1>房屋租赁定金合同</h1>
          <p class="contract-no">合同编号：HT{{ String(booking.id).padStart(8, '0') }}</p>
        </div>

        <el-divider />

        <div class="contract-section">
          <h3>第一条 租赁双方信息</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="出租方（房东）">房东 #{{ booking.landlord_id }}</el-descriptions-item>
            <el-descriptions-item label="承租方（租客）">{{ authStore.user?.username || '租客' }}</el-descriptions-item>
            <el-descriptions-item label="房源编号">#{{ booking.property_id }}</el-descriptions-item>
            <el-descriptions-item label="签订日期">{{ today }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="contract-section">
          <h3>第二条 押金条款</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="押金金额">
              <strong>¥{{ booking.deposit_amount || 0 }}</strong>
            </el-descriptions-item>
            <el-descriptions-item label="支付状态">
              <el-tag type="success">已支付</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="支付流水号">{{ booking.payment_transaction_id || '—' }}</el-descriptions-item>
            <el-descriptions-item label="支付时间">{{ formatDate(booking.updated_at) }}</el-descriptions-item>
          </el-descriptions>
          <p class="clause-text">
            1. 承租方在签订正式租赁合同前需支付上述押金作为定约保证。<br />
            2. 押金将在正式签署租赁合同后自动转为首期租金的一部分。<br />
            3. 如因出租方原因未能签订正式合同，押金全额无息退还。<br />
            4. 如因承租方原因取消租赁，按平台取消政策执行退款。
          </p>
        </div>

        <div class="contract-section">
          <h3>第三条 租赁基本条款</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="预定看房日期">{{ booking.scheduled_date || '待定' }}</el-descriptions-item>
            <el-descriptions-item label="合同状态">待签署正式租赁合同</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="contract-section">
          <h3>第四条 其他约定</h3>
          <p class="clause-text">
            1. 本合同为电子合同，与纸质合同具有同等法律效力。<br />
            2. 双方因本合同发生争议的，应协商解决；协商不成的，提交房源所在地人民法院管辖。<br />
            3. 本合同的签署、履行、解释及争议解决均适用中华人民共和国法律。
          </p>
        </div>
      </el-card>

      <!-- Download Button -->
      <div class="download-bar">
        <el-button type="primary" size="large" round @click="handleDownload">
          📥 下载电子合同 (PDF)
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { bookingService } from '@/services/booking'
import { useAuthStore } from '@/stores/auth'
import type { Booking } from '@/types/booking'

const route = useRoute()
const authStore = useAuthStore()
const booking = ref<Booking | null>(null)
const loading = ref(false)

const today = computed(() => new Date().toLocaleDateString('zh-CN'))

function formatDate(d: string): string {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN')
}

function handleDownload() {
  // In production, call backend to generate PDF
  // For now, trigger browser print / save
  ElMessage.success('合同下载功能已触发（生产环境将调用后端PDF生成服务）')
  window.print()
}

onMounted(async () => {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    booking.value = await bookingService.getById(id)
  } catch {
    // handle
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.contract-page {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: 80px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 22px;
  margin: 0;
}

.contract-card {
  border-radius: var(--radius) !important;
  position: relative;
  overflow: hidden;
  line-height: 1.8;
}

.contract-watermark {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-25deg);
  font-size: 120px;
  font-weight: 900;
  color: rgba(64, 158, 255, 0.04);
  pointer-events: none;
  white-space: nowrap;
  z-index: 0;
}

.contract-header {
  text-align: center;
  padding: 20px 0 10px;
  position: relative;
  z-index: 1;
}

.contract-header h1 {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.contract-no {
  font-size: 14px;
  color: var(--text-muted);
}

.contract-section {
  margin-bottom: 24px;
  position: relative;
  z-index: 1;
}

.contract-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.clause-text {
  margin-top: 12px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 2;
  padding: 12px 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}

.download-bar {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

@media print {
  .page-header, .download-bar {
    display: none !important;
  }
  .contract-card {
    box-shadow: none !important;
    border: 1px solid #ddd !important;
  }
  .contract-watermark {
    color: rgba(0, 0, 0, 0.03) !important;
  }
}
</style>
