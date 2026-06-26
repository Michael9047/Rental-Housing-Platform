<template>
  <div class="profile-edit-page">
    <div class="page-header">
      <el-button text :icon="ArrowLeft" @click="$router.back()">返回个人中心</el-button>
      <h2>编辑个人资料</h2>
    </div>

    <el-card shadow="never" class="edit-card">
      <!-- View Mode -->
      <el-form v-if="!editing" label-width="100px" class="profile-form">
        <el-form-item label="用户名"><span>{{ user?.username }}</span></el-form-item>
        <el-form-item label="邮箱"><span>{{ user?.email || '未设置' }}</span></el-form-item>
        <el-form-item label="手机号"><span>{{ user?.phone || '未设置' }}</span></el-form-item>
        <el-form-item label="身份">
          <el-tag :type="roleTagType">{{ roleLabel }}</el-tag>
        </el-form-item>
        <el-form-item label="微信绑定">
          <span style="display:flex;align-items:center;gap:10px">
            <el-tag :type="user?.wechat_openid ? 'success' : 'info'">
              {{ user?.wechat_openid ? '已绑定' : '未绑定' }}
            </el-tag>
            <el-button v-if="user?.wechat_openid" size="small" text type="warning" @click="rebindWechat">
              更换绑定
            </el-button>
            <el-button v-else size="small" text type="primary" @click="bindWechat">
              立即绑定
            </el-button>
          </span>
        </el-form-item>
        <el-form-item label="注册时间"><span>{{ formatDate(user?.created_at || '') }}</span></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="startEdit">编辑资料</el-button>
          <el-button type="danger" text @click="authStore.logout()">退出登录</el-button>
        </el-form-item>
      </el-form>

      <!-- Edit Mode -->
      <el-form
        v-else
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-width="100px"
        class="profile-form"
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
        <el-form-item label="证件上传">
          <el-upload action="#" :auto-upload="false" :show-file-list="true" :limit="1">
            <el-button type="primary" plain size="small">上传身份证/护照</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="消息通知">
          <div class="notif-switches">
            <el-switch v-model="notifSettings.booking" active-text="订单状态变更提醒" />
            <el-switch v-model="notifSettings.contract" active-text="合同签署通知" />
            <el-switch v-model="notifSettings.newListing" active-text="房源上新推送" />
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
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { userService } from '@/services/user'
import { storeToRefs } from 'pinia'
import type { UserRole } from '@/types/user'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

const editing = ref(false)
const saving = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive({ username: '', email: '', phone: '' })
const notifSettings = reactive({ booking: true, contract: true, newListing: true })

const roleLabels: Record<UserRole, string> = { tenant: '租客', landlord: '房东', admin: '管理员' }
const roleLabel = computed(() => roleLabels[user.value?.role || 'tenant'])
const roleTagType = computed(() => {
  if (user.value?.role === 'admin') return 'danger'
  if (user.value?.role === 'landlord') return 'warning'
  return 'info'
})

const editRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

function formatDate(d: string): string {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN')
}

function startEdit() {
  if (!user.value) return
  editForm.username = user.value.username
  editForm.email = user.value.email || ''
  editForm.phone = user.value.phone || ''
  editing.value = true
}

function cancelEdit() { editing.value = false }

async function saveProfile() {
  if (!editFormRef.value) return
  const v = await editFormRef.value.validate().catch(() => false)
  if (!v) return
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
  } catch { /* handled */ }
  finally { saving.value = false }
}

function rebindWechat() {
  ElMessageBox.confirm('确定要更换微信绑定吗？', '更换微信绑定', {
    confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
  }).then(() => {
    ElMessage.success('微信绑定已更新')
  }).catch(() => {})
}

function bindWechat() {
  ElMessage.info('请使用微信扫码绑定（生产环境接入微信OAuth）')
}
</script>

<style scoped>
.profile-edit-page {
  max-width: 700px;
  margin: 0 auto;
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

.edit-card {
  border-radius: var(--radius) !important;
}

.profile-form {
  max-width: 500px;
  padding-top: 12px;
}

.notif-switches {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
