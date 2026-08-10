<template>
  <main class="mailbox-page">
    <el-alert title="模拟邮箱" type="info" :closable="false" show-icon>
      此页面仅展示现有通知发件箱中的邮件记录，不会发送真实邮件或重新投递。
    </el-alert>
    <div class="toolbar"><h1>虚拟邮箱</h1><el-button :loading="loading" @click="load">刷新</el-button></div>
    <el-empty v-if="!loading && items.length === 0" description="暂无邮件模拟记录" />
    <el-collapse v-else v-model="active" class="mail-list">
      <el-collapse-item v-for="mail in items" :key="mail.id" :name="mail.id">
        <template #title>
          <div class="mail-title"><strong>{{ mail.title }}</strong><span>收件人：{{ mail.recipient }}</span><el-tag size="small" :type="mail.status === 'sent' ? 'success' : mail.status === 'failed' ? 'danger' : 'warning'">{{ mail.status === 'sent' ? '模拟发送成功' : mail.status === 'failed' ? '模拟发送失败' : '等待模拟发送' }}</el-tag></div>
        </template>
        <dl><dt>事件</dt><dd>{{ mail.event_type }}</dd><dt>订单</dt><dd>{{ mail.booking_id ? `#${mail.booking_id}` : '无关联订单' }}</dd><dt>时间</dt><dd>{{ formatTime(mail.sent_at || mail.queued_at) }}</dd><dt>重试次数</dt><dd>{{ mail.attempts }}</dd></dl>
        <p class="body">{{ mail.body }}</p><el-alert v-if="mail.last_error" type="warning" :closable="false" :title="`失败原因：${mail.last_error}`" />
      </el-collapse-item>
    </el-collapse>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminService } from '@/services/admin'

type SimulatedMail = { id: string; event_type: string; booking_id: number | null; recipient: string; title: string; body: string; status: string; attempts: number; sent_at: string | null; queued_at: string; last_error: string | null; simulated: boolean }
const items = ref<SimulatedMail[]>([])
const active = ref<string[]>([])
const loading = ref(false)
const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN')
async function load() { loading.value = true; try { items.value = (await adminService.getSimulatedMailbox()).items } catch { ElMessage.error('模拟邮箱加载失败，请确认管理员登录状态') } finally { loading.value = false } }
onMounted(load)
</script>

<style scoped>
.mailbox-page{width:min(1000px,calc(100% - 32px));margin:0 auto;padding:28px 0 52px}.toolbar{display:flex;justify-content:space-between;align-items:center;margin:22px 0 12px}.toolbar h1{margin:0}.mail-list{background:#fff;border-radius:12px;padding:0 18px}.mail-title{display:flex;align-items:center;gap:14px;width:100%;min-width:0}.mail-title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mail-title span{margin-left:auto;color:#667085;font-size:13px}dl{display:grid;grid-template-columns:90px 1fr;gap:8px 14px}dt{color:#667085}dd{margin:0}.body{white-space:pre-wrap;line-height:1.7;padding:14px;background:#f7f8fa;border-radius:8px}@media(max-width:640px){.mailbox-page{width:calc(100% - 20px);padding-top:16px}.mail-title{flex-wrap:wrap}.mail-title span{margin-left:0;width:100%}}
</style>
