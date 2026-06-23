<template>
  <div class="profile-page">
    <h2>个人中心</h2>

    <el-card shadow="never" class="profile-card">
      <template #header><span>基本信息</span></template>
      <el-form
        v-if="!editing"
        label-width="100px"
      >
        <el-form-item label="用户名">
          <span>{{ user?.username }}</span>
        </el-form-item>
        <el-form-item label="邮箱">
          <span>{{ user?.email || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="手机号">
          <span>{{ user?.phone || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="身份">
          <el-tag :type="user?.role === 'admin' ? 'danger' : user?.role === 'landlord' ? 'warning' : 'info'">
            {{ roleLabels[user?.role || 'tenant'] }}
          </el-tag>
        </el-form-item>
        <el-form-item label="微信绑定">
          <el-tag :type="user?.wechat_openid ? 'success' : 'info'">
            {{ user?.wechat_openid ? '已绑定' : '未绑定' }}
          </el-tag>
          <span class="wechat-hint" v-if="user?.wechat_openid">
            微信小程序登录用户
          </span>
        </el-form-item>
        <el-form-item label="注册时间">
          <span>{{ user?.created_at ? formatDate(user.created_at) : '' }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="startEdit">编辑资料</el-button>
        </el-form-item>
      </el-form>

      <el-form
        v-else
        ref="formRef"
        :model="editForm"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="editForm.username" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
          <el-button @click="cancelEdit">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- WeChat Binding Section -->
    <el-card shadow="never" class="wechat-card">
      <template #header>
        <span>微信绑定管理</span>
      </template>
      <div class="wechat-section">
        <div class="wechat-status">
          <el-icon :size="20" :color="user?.wechat_openid ? '#67c23a' : '#ccc'">
            <component :is="user?.wechat_openid ? 'CircleCheckFilled' : 'CircleCloseFilled'" />
          </el-icon>
          <span class="status-text">
            绑定状态：{{ user?.wechat_openid ? '已绑定微信小程序' : '未绑定' }}
          </span>
        </div>
        <p class="wechat-desc">
          {{ user?.wechat_openid
            ? '您已通过微信小程序授权登录，可使用小程序进行房源浏览和预约。如需解绑，请联系管理员。'
            : '绑定微信后，可使用微信小程序快速登录、接收预约通知、使用模板消息等功能。请通过微信小程序完成首次登录绑定。'
          }}
        </p>
        <div class="wechat-features" v-if="!user?.wechat_openid">
          <h4>绑定后可享受：</h4>
          <ul>
            <li>微信小程序一键登录</li>
            <li>预约确认模板消息推送</li>
            <li>看房提醒通知</li>
            <li>AI 租房助手小程序端</li>
          </ul>
        </div>
        <div class="wechat-openid" v-if="user?.wechat_openid">
          <span class="label">微信 OpenID：</span>
          <span class="value">{{ maskOpenId(user.wechat_openid) }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import { storeToRefs } from 'pinia'
import type { UserRole } from '@/types/user'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const editing = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()

const roleLabels: Record<UserRole, string> = {
  tenant: '租客',
  landlord: '房东',
  admin: '管理员',
}

const editForm = reactive({
  username: '',
  email: '',
  phone: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

function startEdit() {
  if (!user.value) return
  editForm.username = user.value.username
  editForm.email = user.value.email || ''
  editForm.phone = user.value.phone || ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveProfile() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const updated = await userService.updateMyProfile({
      username: editForm.username,
      email: editForm.email || undefined,
      phone: editForm.phone || undefined,
    })
    authStore.user = updated
    localStorage.setItem('user', JSON.stringify(updated))
    editing.value = false
    ElMessage.success('资料更新成功')
  } catch {
    // handled by interceptor
  } finally {
    saving.value = false
  }
}

function maskOpenId(openid: string): string {
  if (!openid || openid.length < 12) return '***'
  return openid.slice(0, 6) + '****' + openid.slice(-4)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  await authStore.fetchCurrentUser()
})
</script>

<style scoped>
.profile-page {
  max-width: 700px;
  margin: 0 auto;
}

.profile-page h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 20px;
}

.profile-card {
  margin-bottom: 20px;
}

.wechat-card {
  margin-bottom: 20px;
}

.wechat-section {
  padding: 4px 0;
}

.wechat-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.status-text {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.wechat-desc {
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
  margin-bottom: 16px;
}

.wechat-features h4 {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.wechat-features ul {
  list-style: disc;
  padding-left: 20px;
  margin: 0;
}

.wechat-features li {
  font-size: 13px;
  color: #909399;
  line-height: 1.8;
}

.wechat-openid {
  font-size: 13px;
  color: #909399;
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.wechat-openid .label {
  color: #606266;
}

.wechat-openid .value {
  font-family: monospace;
  color: #67c23a;
}

.wechat-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #67c23a;
}
</style>
