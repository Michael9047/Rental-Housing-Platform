<template>
  <div class="publish-home">
    <h2>发布房源</h2>
    <p class="subtitle">选择发布方式，上传公寓房源信息</p>

    <el-row :gutter="24" class="entry-cards">
      <el-col :span="12">
        <div class="entry-card" @click="$router.push('/property/create')">
          <div class="entry-icon">📝</div>
          <h3>单房录入</h3>
          <p>手动填写单个房间信息，适用于少量零散房间录入</p>
          <ul><li>绑定已有楼栋</li><li>实时字段校验</li><li>AI智能解析描述</li></ul>
          <el-button type="primary" size="large">开始录入</el-button>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="entry-card" @click="$router.push('/property/import')">
          <div class="entry-icon">📦</div>
          <h3>批量 CSV 导入</h3>
          <p>下载标准模板，批量填入整栋房间信息后一键导入</p>
          <ul><li>支持 .csv/.xlsx</li><li>智能列名匹配</li><li>异常数据自动检测</li></ul>
          <el-button type="success" size="large">批量导入</el-button>
        </div>
      </el-col>
    </el-row>

    <el-divider />

    <div class="quick-links">
      <el-button @click="downloadTemplate" :icon="Download">📥 下载 CSV 导入模板</el-button>
      <el-button @click="$router.push('/property/manage')">📋 查看我的房源列表</el-button>
      <el-button @click="$router.push('/buildings')">🏢 管理楼栋信息</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
import { adminService } from '@/services/admin'
import { ElMessage } from 'element-plus'

function downloadTemplate() {
  adminService.downloadTemplate().then(blob => {
    const u = URL.createObjectURL(blob); const a = document.createElement('a')
    a.href = u; a.download = 'property_import_template.xlsx'; a.click(); URL.revokeObjectURL(u)
    ElMessage.success('模板下载成功')
  }).catch(() => ElMessage.error('下载失败'))
}
</script>

<style scoped>
.publish-home{max-width:960px;margin:0 auto}
h2{font-size:24px;color:#303133;margin-bottom:8px}
.subtitle{color:#909399;margin-bottom:32px;font-size:15px}
.entry-cards{margin-bottom:32px}
.entry-card{cursor:pointer;background:#fff;border:2px solid #e4e7ed;border-radius:16px;padding:32px 24px;text-align:center;transition:all .3s}
.entry-card:hover{border-color:#FF6B35;box-shadow:0 4px 24px rgba(255,107,53,.12);transform:translateY(-2px)}
.entry-icon{font-size:48px;margin-bottom:12px}
.entry-card h3{font-size:20px;color:#303133;margin:8px 0}
.entry-card p{color:#909399;font-size:14px;margin-bottom:16px}
.entry-card ul{text-align:left;color:#606266;font-size:13px;padding-left:20px;margin-bottom:20px;line-height:1.8}
.quick-links{display:flex;gap:12px;flex-wrap:wrap}
</style>
