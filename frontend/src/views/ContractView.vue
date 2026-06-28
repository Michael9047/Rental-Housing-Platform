<template>
  <div class="contract-page" v-loading="loading">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回</el-button>
      <h2>电子合同</h2>
    </div>

    <el-empty v-if="!loading && !contract" description="合同数据未找到" />

    <template v-if="contract">
      <el-card shadow="never" class="contract-card">
        <div class="contract-watermark">电子合同</div>

        <div class="contract-header">
          <h1>房屋租赁合同</h1>
          <p class="contract-no">合同编号：{{ contract.id }}</p>
          <el-tag :type="contract.status === 'signed' ? 'success' : 'warning'" round>
            {{ contract.status === 'signed' ? '已签署' : '待签署' }}
          </el-tag>
        </div>

        <el-divider />

        <el-descriptions :column="2" border class="contract-meta">
          <el-descriptions-item label="预约编号">#{{ contract.booking_id }}</el-descriptions-item>
          <el-descriptions-item label="房源编号">#{{ contract.property_id }}</el-descriptions-item>
          <el-descriptions-item label="租客编号">#{{ contract.tenant_id }}</el-descriptions-item>
          <el-descriptions-item label="模板">{{ contract.template_name }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(contract.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="签署时间">
            {{ contract.signed_at ? formatDate(contract.signed_at) : '未签署' }}
          </el-descriptions-item>
        </el-descriptions>

        <pre class="contract-content">{{ contract.content }}</pre>
      </el-card>

      <div class="download-bar">
        <el-button
          v-if="contract.status !== 'signed'"
          type="primary"
          size="large"
          round
          :loading="signing"
          @click="handleSign"
        >
          签署合同
        </el-button>
        <el-button size="large" round @click="handleDownload">下载合同文本</el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { contractService, type Contract } from '@/services/contract'

const route = useRoute()
const contract = ref<Contract | null>(null)
const loading = ref(false)
const signing = ref(false)

function formatDate(d: string): string {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}

async function loadContract() {
  const id = String(route.params.id || '')
  if (!id) return

  loading.value = true
  try {
    contract.value = /^\d+$/.test(id)
      ? await contractService.generate(Number(id))
      : await contractService.get(id)
  } catch {
    contract.value = null
  } finally {
    loading.value = false
  }
}

async function handleSign() {
  if (!contract.value) return
  signing.value = true
  try {
    contract.value = await contractService.sign(contract.value.id)
    ElMessage.success('合同已签署')
  } catch {
    ElMessage.error('签署失败，请确认当前账号是否为合同租客')
  } finally {
    signing.value = false
  }
}

async function handleDownload() {
  if (!contract.value) return
  try {
    const content = await contractService.download(contract.value.id)
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `contract-${contract.value.id}.txt`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('合同下载失败')
  }
}

onMounted(loadContract)
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

.contract-header,
.contract-meta,
.contract-content {
  position: relative;
  z-index: 1;
}

.contract-header {
  text-align: center;
  padding: 20px 0 10px;
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
  margin-bottom: 10px;
}

.contract-content {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  white-space: pre-wrap;
}

.download-bar {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}

@media print {
  .page-header,
  .download-bar {
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
