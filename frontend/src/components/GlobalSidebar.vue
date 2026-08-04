<template>
  <el-aside :class="['layout-sidebar', { collapsed }]" :width="collapsed ? '64px' : '200px'">
    <!-- 折叠切换按钮 -->
    <div class="sidebar-toggle" @click="collapsed = !collapsed">
      <el-icon :size="20">
        <Expand v-if="collapsed" />
        <Fold v-else />
      </el-icon>
    </div>
    <el-menu :default-active="activeMenu" router class="sidebar-menu" :collapse="collapsed">
      <!-- 公共 -->
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <span>首页</span>
      </el-menu-item>

      <!-- ====== 维修师傅侧边栏 ====== -->
      <template v-if="authStore.isMaintenance">
        <el-menu-item index="/worker/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>工单中心</span>
        </el-menu-item>
        <el-menu-item index="/notifications">
          <el-icon><Bell /></el-icon>
          <span>消息通知</span>
        </el-menu-item>
      </template>

      <!-- ====== BD经理侧边栏（已废弃） ====== -->

      <!-- ====== 房东侧边栏 ====== -->
      <template v-if="authStore.isLandlord">
        <el-menu-item index="/buildings">
          <el-icon><HomeFilled /></el-icon>
          <span>公寓管理</span>
        </el-menu-item>
        <el-menu-item index="/unit-type/manage">
          <el-icon><Grid /></el-icon>
          <span>户型管理</span>
        </el-menu-item>
        <el-menu-item index="/bookings/landlord">
          <el-icon><Tickets /></el-icon>
          <span>预约管理</span>
        </el-menu-item>
        <el-menu-item index="/contracts/landlord">
          <el-icon><Document /></el-icon>
          <span>合约管理</span>
        </el-menu-item>
        <el-menu-item index="/tenants">
          <el-icon><User /></el-icon>
          <span>租客管理</span>
        </el-menu-item>
        <el-menu-item index="/repairs/manage">
          <el-icon><Tools /></el-icon>
          <span>维修工单</span>
        </el-menu-item>
      </template>

      <!-- 管理员：系统管理（不含仪表盘，仪表盘归房东） -->
      <template v-if="authStore.isAdmin">
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/logs">
          <el-icon><Document /></el-icon>
          <span>审计日志</span>
        </el-menu-item>
      </template>
    </el-menu>
  </el-aside>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, Bell, DataAnalysis, User, Document,
  Tickets, Fold, Expand, Grid, Tools,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()

// 侧边栏折叠状态 —— 持久化到 localStorage
const SIDEBAR_KEY = 'sidebar_collapsed'
const collapsed = ref(localStorage.getItem(SIDEBAR_KEY) !== 'false')

watch(collapsed, (v) => localStorage.setItem(SIDEBAR_KEY, String(v)))

// 当前激活菜单高亮
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/admin')) return path
  if (path.startsWith('/bookings/')) return path
  if (path.startsWith('/buildings')) return '/buildings'
  if (path.startsWith('/unit-type')) return '/unit-type/manage'
  if (path.startsWith('/contracts')) return '/contracts/landlord'
  if (path.startsWith('/tenants')) return '/tenants'
  if (path.startsWith('/repairs')) return '/repairs/manage'
  if (path.startsWith('/notifications')) return '/notifications'
  return path
})
</script>

<style scoped>
.layout-sidebar {
  background: var(--bg-white);
  border-right: 1px solid var(--border);
  transition: width 0.3s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 折叠切换按钮 */
.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  cursor: pointer;
  color: var(--text-muted);
  transition: color 0.2s, background 0.2s;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
}

.sidebar-toggle:hover {
  color: var(--primary);
  background: var(--primary-light);
}

.sidebar-menu {
  border-right: none !important;
  height: 100%;
  padding-top: 8px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 折叠状态下菜单项居中 */
.layout-sidebar.collapsed .sidebar-menu :deep(.el-menu-item) {
  justify-content: center;
}
</style>
