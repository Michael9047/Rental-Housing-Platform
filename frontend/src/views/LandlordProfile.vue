<template>
  <div class="landlord-profile-page">
    <h2>👤 个人中心</h2>
    <p class="sub">管理您的联系方式，这些信息将在公寓详情中展示给租客。</p>

    <el-card shadow="never" class="profile-card">
      <!-- View Mode -->
      <el-form v-if="!editing" label-width="100px" class="profile-form">
        <el-form-item label="姓名">
          <span>{{ profile.username || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="电话">
          <span>{{ profile.phone || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="微信">
          <span>{{ profile.wechat || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="邮箱">
          <span>{{ profile.email || '未设置' }}</span>
        </el-form-item>
        <el-form-item label="二维码">
          <el-image v-if="qrPreview" :src="qrPreview" style="width:120px;height:120px;border-radius:8px" fit="cover" />
          <span v-else style="color:#909399">未上传</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="startEdit">编辑资料</el-button>
        </el-form-item>
      </el-form>

      <!-- Edit Mode -->
      <el-form
        v-else
        ref="editFormRef"
        :model="editForm"
        label-width="100px"
        class="profile-form"
      >
        <el-form-item label="姓名" prop="username">
          <el-input v-model="editForm.username" placeholder="请输入姓名" maxlength="100" />
        </el-form-item>
        <el-form-item label="电话" prop="phone">
          <el-input v-model="editForm.phone" placeholder="请输入手机号" maxlength="32" />
        </el-form-item>
        <el-form-item label="微信" prop="wechat">
          <el-input v-model="editForm.wechat" placeholder="请输入微信号" maxlength="100" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="请输入邮箱" maxlength="255" />
        </el-form-item>
        <el-form-item label="二维码">
          <div style="display:flex;gap:8px;align-items:center">
            <el-image v-if="qrTempUrl" :src="qrTempUrl" style="width:120px;height:120px;border-radius:8px" fit="cover" />
            <input ref="qrInput" type="file" accept="image/*" style="display:none" @change="onQrUpload" />
            <el-button size="small" @click="($refs.qrInput as any)?.click()">{{ editForm.wechat_qr ? '更换二维码' : '上传二维码' }}</el-button>
            <el-button v-if="editForm.wechat_qr" size="small" type="danger" @click="editForm.wechat_qr=''; qrTempUrl=''">删除</el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveProfile">保存修改</el-button>
          <el-button @click="cancelEdit">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import api from '@/services/api'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const editing = ref(false)
const saving = ref(false)
const editFormRef = ref<FormInstance>()
const qrInput = ref<HTMLInputElement>()
const qrTempUrl = ref('')

const profile = reactive({
  username: '',
  phone: '',
  wechat: '',
  email: '',
  wechat_qr: '',
})

const editForm = reactive({
  username: '',
  phone: '',
  wechat: '',
  email: '',
  wechat_qr: '',
})

const qrPreview = computed(() => {
  if (profile.wechat_qr) {
    return profile.wechat_qr.startsWith('http') ? profile.wechat_qr : '/api/v1/uploads/' + profile.wechat_qr
  }
  return ''
})

async function loadProfile() {
  try {
    const r = await api.get('/users/me')
    const u = r.data
    profile.username = u.username || ''
    profile.phone = u.phone || ''
    profile.wechat = u.wechat || ''
    profile.email = u.email || ''
    profile.wechat_qr = u.wechat_qr || ''
  } catch (e) {
    // fallback to auth store
    if (user.value) {
      profile.username = user.value.username || ''
      profile.phone = (user.value as any).phone || ''
      profile.email = (user.value as any).email || ''
    }
  }
}

function startEdit() {
  editForm.username = profile.username
  editForm.phone = profile.phone
  editForm.wechat = profile.wechat
  editForm.email = profile.email
  editForm.wechat_qr = profile.wechat_qr
  qrTempUrl.value = qrPreview.value
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  qrTempUrl.value = ''
}

async function onQrUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const fd = new FormData()
  fd.append('files', file)
  try {
    const r = await api.post('/upload/temp', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    qrTempUrl.value = r.data.urls?.[0] || ''
    editForm.wechat_qr = qrTempUrl.value.split('/').pop() || ''
  } catch {
    ElMessage.error('上传失败')
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const body: Record<string, any> = {
      username: editForm.username.trim() || undefined,
      phone: editForm.phone.trim() || undefined,
      wechat: editForm.wechat.trim() || undefined,
      email: editForm.email.trim() || undefined,
      wechat_qr: editForm.wechat_qr || undefined,
    }
    await api.patch('/users/me', body)

    // 同步到本地状态
    profile.username = editForm.username
    profile.phone = editForm.phone
    profile.wechat = editForm.wechat
    profile.email = editForm.email
    profile.wechat_qr = editForm.wechat_qr

    // 更新 auth store
    if (user.value) {
      (user.value as any).username = editForm.username
      ;(user.value as any).phone = editForm.phone
      ;(user.value as any).email = editForm.email
      ;(user.value as any).wechat = editForm.wechat
      ;(user.value as any).wechat_qr = editForm.wechat_qr
      localStorage.setItem('user', JSON.stringify(user.value))
    }

    editing.value = false
    qrTempUrl.value = ''
    ElMessage.success('个人资料已保存')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '保存失败'
    ElMessage.error(typeof msg === 'string' ? msg : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.landlord-profile-page {
  max-width: 700px;
  margin: 0 auto;
}

h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 8px;
}

.sub {
  color: #909399;
  margin-bottom: 20px;
  font-size: 14px;
}

.profile-card {
  border-radius: var(--radius) !important;
}

.profile-form {
  max-width: 500px;
  padding-top: 12px;
}
</style>
