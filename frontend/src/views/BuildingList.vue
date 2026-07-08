<template>
  <div class="building-page">
    <h2>🏢 公寓管理</h2>
    <p class="sub">发布房源前需要先创建公寓。每个房间必须绑定到已有公寓。</p>

    <el-button type="primary" @click="openCreateDialog" style="margin-bottom:20px">+ 新建公寓</el-button>

    <el-table :data="buildings" v-loading="loading" border stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="公寓名称" min-width="160" />
      <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column prop="contact_phone" label="联系电话" width="130" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{row}"><el-tag :type="row.status==='active'?'success':'info'" size="small">{{ row.status==='active'?'正常':'已停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{row}">
          <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteBuilding(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading&&!buildings.length" description="暂无公寓，请先创建" />

    <!-- 创建/编辑弹窗 -->
    <el-dialog
      v-model="showDialog"
      :title="editingId ? '编辑公寓' : '新建公寓'"
      width="480px"
      :close-on-click-modal="false"
      @closed="onDialogClosed"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="80px"
        @submit.prevent="saveBuilding"
      >
        <el-form-item label="公寓名称" prop="name" required>
          <el-input
            v-model="form.name"
            placeholder="如：翰林缘公寓"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="地址" prop="address">
          <el-input v-model="form.address" placeholder="公寓详细地址" maxlength="300" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contact_phone">
          <el-input
            v-model="form.contact_phone"
            placeholder="手机号或固定电话（选填）"
            maxlength="20"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="公寓简介（选填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false" :disabled="saving">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveBuilding">
          {{ editingId ? '保存修改' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { buildingService, type Building } from '@/services/building'
import { extractErrorMessage } from '@/services/api'

// ── 数据 ──
const buildings = ref<Building[]>([])
const loading = ref(false)
const showDialog = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const defaultForm = () => ({ name: '', address: '', contact_phone: '', description: '' })
const form = reactive(defaultForm())

// ── 表单校验规则 ──
const formRules: FormRules = {
  name: [
    { required: true, message: '公寓名称不能为空', trigger: 'blur' },
    { max: 200, message: '公寓名称不能超过200个字符', trigger: 'blur' },
  ],
  contact_phone: [
    {
      validator: (_rule, value, callback) => {
        const v = (value || '').trim()
        if (!v) return callback() // 选填
        // 手机号：1[3-9]xxxxxxxxx，固定电话：区号-号码
        const phoneRe = /^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$/
        if (!phoneRe.test(v)) {
          return callback(new Error('请输入正确的联系电话（11位手机号或带区号固话）'))
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

// ── 加载列表 ──
async function load() {
  loading.value = true
  try {
    buildings.value = await buildingService.list({ limit: 200 })
  } catch {
    // 拦截器已弹错误
  } finally {
    loading.value = false
  }
}

// ── 弹窗操作 ──
function openCreateDialog() {
  editingId.value = null
  Object.assign(form, defaultForm())
  formRef.value?.clearValidate()
  showDialog.value = true
}

function openEditDialog(b: Building) {
  editingId.value = b.id
  form.name = b.name
  form.address = b.address || ''
  form.contact_phone = b.contact_phone || ''
  form.description = b.description || ''
  formRef.value?.clearValidate()
  showDialog.value = true
}

function onDialogClosed() {
  // 关闭后重置表单
  Object.assign(form, defaultForm())
  editingId.value = null
  formRef.value?.clearValidate()
}

// ── 提交 ──
async function saveBuilding() {
  if (!formRef.value) return

  // 1. 表单前端校验
  try {
    await formRef.value.validate()
  } catch {
    return // 校验不通过，Element Plus 已在各字段下方显示红字
  }

  // 2. 发起请求
  saving.value = true
  const payload = {
    name: form.name.trim(),
    address: form.address.trim(),
    contact_phone: form.contact_phone.trim(),
    description: form.description.trim(),
  }

  try {
    if (editingId.value) {
      await buildingService.update(editingId.value, payload)
      ElMessage.success('公寓信息已更新')
    } else {
      await buildingService.create(payload)
      ElMessage.success('公寓创建成功')
    }
    showDialog.value = false
    load()
  } catch (e: any) {
    // extractErrorMessage 从 {error:{message}} 或 {detail} 中提取真实错误
    const msg = extractErrorMessage(e)
    if (msg) {
      ElMessage.error(msg)
    } else {
      ElMessage.error(editingId.value ? '更新失败，请重试' : '创建失败，请检查网络后重试')
    }
  } finally {
    saving.value = false
  }
}

// ── 删除 ──
async function deleteBuilding(id: number) {
  try {
    await ElMessageBox.confirm(
      '删除公寓将同时影响关联房源（如有），确定删除？',
      '确认删除',
      { type: 'warning' },
    )
    await buildingService.remove(id)
    ElMessage.success('已删除')
    load()
  } catch {
    // 用户取消 或 删除失败（拦截器已弹错误）
  }
}

onMounted(load)
</script>

<style scoped>
.building-page {
  max-width: 960px;
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
</style>
