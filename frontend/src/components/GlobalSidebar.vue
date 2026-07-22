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

      <!-- ====== 租客侧边栏 ====== -->
      <template v-if="!authStore.isLandlord && !authStore.isAdmin && !authStore.isMaintenance && !authStore.isBdManager">
        <el-menu-item index="/ai-search">
          <el-icon><MagicStick /></el-icon>
          <span>AI 找房</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.isLoggedIn" index="/cart">
          <el-icon><ShoppingCart /></el-icon>
          <span>候选清单</span>
        </el-menu-item>
        <el-menu-item index="/search">
          <el-icon><Search /></el-icon>
          <span>搜索房源</span>
        </el-menu-item>
        <el-menu-item index="/map">
          <el-icon><Location /></el-icon>
          <span>地图找房</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.isLoggedIn" index="/bookings/tenant">
          <el-icon><List /></el-icon>
          <span>我的预订</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.isLoggedIn" index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
      </template>

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

      <!-- ====== BD经理侧边栏 ====== -->
      <template v-if="authStore.isBdManager">
        <el-menu-item index="/bd/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据台</span>
        </el-menu-item>
        <el-menu-item index="/property/manage">
          <el-icon><OfficeBuilding /></el-icon>
          <span>房源管理</span>
        </el-menu-item>
        <el-menu-item index="/property/create">
          <el-icon><Plus /></el-icon>
          <span>发布房源</span>
        </el-menu-item>
        <el-menu-item index="/notifications">
          <el-icon><Bell /></el-icon>
          <span>消息通知</span>
        </el-menu-item>
      </template>

      <!-- ====== 房东/管理员侧边栏 ====== -->
      <template v-if="authStore.isLandlord || authStore.isAdmin">
        <el-menu-item index="/workspace">
          <el-icon><DataAnalysis /></el-icon>
          <span>运营工作台</span>
        </el-menu-item>
        <el-menu-item index="/buildings">
          <el-icon><HomeFilled /></el-icon>
          <span>公寓管理</span>
        </el-menu-item>
        <el-menu-item index="/unit-type/manage">
          <el-icon><Grid /></el-icon>
          <span>户型管理</span>
        </el-menu-item>
        <el-menu-item index="/rooms/manage">
          <el-icon><OfficeBuilding /></el-icon>
          <span>房间管理</span>
        </el-menu-item>
        <el-menu-item index="/property/history">
          <el-icon><Clock /></el-icon>
          <span>修改记录</span>
        </el-menu-item>
        <el-menu-item index="/bookings/landlord">
          <el-icon><Tickets /></el-icon>
          <span>预约管理</span>
        </el-menu-item>
        <el-menu-item index="/notifications">
          <el-icon><Bell /></el-icon>
          <span>消息通知</span>
        </el-menu-item>
      </template>

      <!-- 管理员额外菜单 -->
      <template v-if="authStore.isAdmin">
        <el-divider style="margin: 8px 0" />
        <el-sub-menu index="admin-sub">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/admin">仪表盘</el-menu-item>
          <el-menu-item index="/admin/users">用户管理</el-menu-item>
          <el-menu-item index="/admin/properties">房源审核</el-menu-item>
          <el-menu-item index="/admin/import">数据导入</el-menu-item>
          <el-menu-item index="/admin/logs">审计日志</el-menu-item>
          <el-menu-item index="/admin/embeddings">Embedding</el-menu-item>
        </el-sub-menu>
      </template>
    </el-menu>
  </el-aside>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, ChatDotRound, MagicStick, ShoppingCart, Search,
  Location, User, List, Bell, DataAnalysis, OfficeBuilding,
  Plus, Tickets, Fold, Expand, Cpu, Grid, Upload, Document, Clock,
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
  if (path.startsWith('/notifications')) return '/notifications'
  if (path.startsWith('/property/')) {
    if (path === '/property/create') return '/property/create'
    if (path === '/property/manage') return '/property/manage'
    return '/search'
  }
  if (path.startsWith('/bookings/')) return path
  if (path.startsWith('/buildings')) return '/buildings'
  if (path.startsWith('/unit-type')) return path.startsWith('/unit-type/create') ? '/unit-type/create' : '/unit-type/manage'
  if (path.startsWith('/rooms/')) return '/rooms/manage'
  if (path.startsWith('/room/')) return '/room/import'
  if (path.startsWith('/tenants')) return '/tenants'
  if (path.startsWith('/orders')) return '/orders'
  if (path.startsWith('/workspace')) return '/workspace'
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
