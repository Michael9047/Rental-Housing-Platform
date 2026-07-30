<template>
  <el-container class="admin-layout">
    <!-- 左侧边栏 -->
    <el-aside width="220px" class="admin-sidebar">
      <div class="sidebar-header">
        <router-link to="/admin" class="sidebar-logo">
          <span class="logo-icon">⚙️</span>
          <span class="logo-text">管理后台</span>
        </router-link>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="#1d1e2c"
        text-color="#a0a4b8"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/admin">
          <el-icon><DataAnalysis /></el-icon>
          <span>控制台</span>
        </el-menu-item>

        <el-menu-item index="/admin/properties">
          <el-icon><House /></el-icon>
          <span>房源审核</span>
        </el-menu-item>

        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>

        <el-menu-item index="/admin/import">
          <el-icon><Upload /></el-icon>
          <span>批量导入</span>
        </el-menu-item>

        <el-sub-menu index="repairs-group">
          <template #title>
            <el-icon><Tools /></el-icon>
            <span>维修管理</span>
          </template>
          <el-menu-item index="/admin/escalated-repairs">
            <span>待派单工单</span>
          </el-menu-item>
          <el-menu-item index="/admin/landlord-workers">
            <span>房东维修工看板</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system-group">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>系统维护</span>
          </template>
          <el-menu-item index="/admin/logs">
            <span>审计日志</span>
          </el-menu-item>
          <el-menu-item index="/admin/embeddings">
            <span>向量索引</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>

      <div class="sidebar-footer">
        <el-button text class="back-btn" @click="router.push('/')">
          <el-icon><ArrowLeft /></el-icon>
          返回前台
        </el-button>
      </div>
    </el-aside>

    <!-- 右侧内容区 -->
    <el-container class="admin-main-container">
      <el-header class="admin-header">
        <div class="admin-header-left">
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="admin-header-right">
          <el-tag type="danger" size="small" effect="dark">管理员</el-tag>
          <span class="admin-username">{{ authStore.user?.username }}</span>
          <el-button text :icon="SwitchButton" @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  DataAnalysis, House, User, Upload, Tools, Monitor,
  ArrowLeft, SwitchButton,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/admin': '控制台',
    '/admin/properties': '房源审核',
    '/admin/users': '用户管理',
    '/admin/import': '批量导入',
    '/admin/logs': '审计日志',
    '/admin/embeddings': '向量索引',
    '/admin/escalated-repairs': '待派单工单',
    '/admin/landlord-workers': '房东维修工看板',
  }
  return titles[route.path] || '管理后台'
})

function handleLogout() {
  authStore.logout()
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}

/* ── 侧边栏 ── */
.admin-sidebar {
  background: #1d1e2c;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.logo-icon {
  font-size: 22px;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 1px;
}

.sidebar-menu {
  flex: 1;
  border-right: none !important;
}

.sidebar-menu :deep(.el-sub-menu__title) {
  padding-left: 20px !important;
}

.sidebar-menu :deep(.el-menu-item) {
  padding-left: 20px !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary) !important;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.back-btn {
  width: 100%;
  color: #a0a4b8;
  justify-content: flex-start;
}

.back-btn:hover {
  color: #ffffff;
}

/* ── 头部 ── */
.admin-main-container {
  flex-direction: column;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border-bottom: 1px solid #ebeef5;
  height: 56px;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.admin-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-username {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

/* ── 主内容 ── */
.admin-main {
  background: #f5f7fa;
  overflow-y: auto;
}
</style>
