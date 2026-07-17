<template>
  <el-container class="layout-container">
    <!-- Top Navigation -->
    <el-header class="layout-header">
      <div class="header-left">
        <router-link to="/" class="logo">
          <span class="logo-icon">🏠</span>
          <span class="logo-text">AI全球公寓租赁</span>
        </router-link>
      </div>

      <div class="header-center">
        <div class="header-search-wrapper">
          <el-input
            v-model="searchQuery"
            placeholder="搜索房源：输入区域、小区、国家、城市..."
            :prefix-icon="Search"
            class="search-input"
            size="large"
            @keyup.enter="handleSearch"
          />
          <el-button type="primary" @click="handleSearch" class="search-btn">搜索</el-button>
        </div>
      </div>

      <div class="header-right">
        <template v-if="authStore.isLoggedIn">
          <el-tag v-if="authStore.isAdmin" type="danger" size="small" effect="dark">管理员</el-tag>
          <el-tag v-else-if="authStore.isLandlord" type="warning" size="small" effect="dark">公寓运营商</el-tag>
          <el-tag v-else-if="authStore.isMaintenance" type="success" size="small" effect="dark">维修师傅</el-tag>
          <el-tag v-else-if="authStore.isBdManager" type="" size="small" effect="dark" style="background-color: #8b5cf6; border-color: #8b5cf6; color: #fff;">商务拓展</el-tag>
          <el-tag v-else type="info" size="small" effect="plain">租客</el-tag>

          <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
            <el-button :icon="Bell" circle @click="router.push('/notifications')" />
          </el-badge>

          <el-dropdown trigger="click">
            <span class="user-dropdown">
              <el-avatar :size="34" :icon="UserFilled" />
              <span class="username">{{ authStore.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <!-- 租客菜单 -->
                <template v-if="!authStore.isLandlord && !authStore.isAdmin && !authStore.isMaintenance && !authStore.isBdManager">
                  <el-dropdown-item @click="router.push('/profile')">
                    <el-icon><User /></el-icon> 个人中心
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/bookings/tenant')">
                    <el-icon><List /></el-icon> 我的预订
                  </el-dropdown-item>
                </template>
                <!-- 房东/管理员菜单 -->
                <template v-if="authStore.isLandlord || authStore.isAdmin">
                  <el-dropdown-item @click="router.push('/workspace')">
                    <el-icon><DataAnalysis /></el-icon> 运营工作台
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/bookings/landlord')">
                    <el-icon><Tickets /></el-icon> 预约管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/manage')">
                    <el-icon><Setting /></el-icon> 房源管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/create')">
                    <el-icon><Plus /></el-icon> 发布房源
                  </el-dropdown-item>
                </template>
                <!-- 维修师傅菜单 -->
                <template v-if="authStore.isMaintenance">
                  <el-dropdown-item @click="router.push('/worker/dashboard')">
                    <el-icon><DataAnalysis /></el-icon> 工单中心
                  </el-dropdown-item>
                </template>
                <!-- BD经理菜单 -->
                <template v-if="authStore.isBdManager">
                  <el-dropdown-item @click="router.push('/bd/dashboard')">
                    <el-icon><DataAnalysis /></el-icon> 数据台
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/manage')">
                    <el-icon><Setting /></el-icon> 房源管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/property/create')">
                    <el-icon><Plus /></el-icon> 发布房源
                  </el-dropdown-item>
                </template>
                <el-dropdown-item v-if="authStore.isAdmin" @click="router.push('/admin')">
                  <el-icon><DataAnalysis /></el-icon> 系统管理
                </el-dropdown-item>
                <el-dropdown-item divided @click="authStore.logout()">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button type="primary" @click="router.push('/login')" round>登录</el-button>
          <el-button @click="router.push('/register')" round>注册</el-button>
        </template>
      </div>
    </el-header>

    <el-container class="layout-body">
      <!-- Sidebar -->
      <el-aside class="layout-sidebar" width="200px">
        <el-menu :default-active="activeMenu" router class="sidebar-menu">
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
              <span v-if="cartStore.count > 0" class="cart-menu-badge">
                {{ cartStore.count > 99 ? '99+' : cartStore.count }}
              </span>
            </el-menu-item>
            <el-menu-item v-if="authStore.isLoggedIn" index="/compare">
              <el-icon><Histogram /></el-icon>
              <span>房源对比</span>
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
            <el-menu-item index="/property/manage">
              <el-icon><OfficeBuilding /></el-icon>
              <span>房源管理</span>
            </el-menu-item>
            <el-menu-item index="/property/create">
              <el-icon><Plus /></el-icon>
              <span>发布房源</span>
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

      <!-- Main Content -->
      <el-main class="layout-main">
        <div class="back-bar" v-if="route.path !== '/'">
          <el-button text :icon="ArrowLeft" @click="router.back()">返回上一页</el-button>
        </div>
        <router-view />
        <GlobalFooter />
      </el-main>
    </el-container>

    <!-- 浮动 AI 管家：全站唯一的找房/对比入口，登录可见 -->
    <AssistantBubble />
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  MagicStick, Search, HomeFilled, User, UserFilled, ArrowDown, ArrowLeft, Setting, SwitchButton,
  Plus, List, Bell, DataAnalysis, Tickets, OfficeBuilding, Location,
  ShoppingCart, Histogram,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useAgentChatStore } from '@/stores/agentChat'
import { useCartStore } from '@/stores/cart'
import { notificationService } from '@/services/notification'
import GlobalFooter from '@/components/GlobalFooter.vue'
import AssistantBubble from '@/components/AssistantBubble.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const cartStore = useCartStore()
const agentChatStore = useAgentChatStore()

const searchQuery = ref('')
const unreadCount = ref(0)

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
  if (path.startsWith('/workspace')) return '/workspace'
  return path
})

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ name: 'search', query: { q: searchQuery.value.trim() } })
  }
}

async function fetchUnreadCount() {
  if (!authStore.isLoggedIn) return
  try {
    const resp = await notificationService.getUnreadCount()
    unreadCount.value = resp.count
  } catch {
    // ignore
  }
}

onMounted(() => {
  fetchUnreadCount()
  if (authStore.isLoggedIn) cartStore.fetch()
})

// 每次路由变化刷新未读数（从通知页回来时数字更新）
watch(() => route.path, () => {
  fetchUnreadCount()
})

// 登录状态变化时同步候选清单与管家会话（登录后拉取、登出清空）
watch(
  () => authStore.isLoggedIn,
  (loggedIn) => {
    if (loggedIn) {
      cartStore.fetch()
    } else {
      cartStore.clear()
      agentChatStore.reset()
    }
  },
)
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Header ───────────────────────── */

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-white);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  height: 64px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}

.header-left .logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
}

.logo-icon {
  font-size: 26px;
}

.logo-text {
  font-size: 17px;
  font-weight: 700;
  color: var(--primary);
  letter-spacing: 0.5px;
}

.header-center {
  flex: 1;
  max-width: 520px;
  margin: 0 40px;
}

.header-search-wrapper {
  display: flex;
  align-items: center;
  border-radius: 36px;
  overflow: hidden;
  height: 48px;
}

.search-input {
  flex: 1;
  border-radius: 36px 0 0 36px;
  overflow: hidden;
}

.search-input :deep(.el-input__wrapper) {
  border-radius: 36px 0 0 36px !important;
  background: var(--bg-white) !important;
  border: 2px solid var(--primary) !important;
  box-shadow: none !important;
  height: 48px;
  padding-left: 16px;
}

.search-input :deep(.el-input__inner) {
  color: var(--text-primary);
}

.search-input :deep(.el-input__prefix) {
  color: var(--text-muted);
}

.search-btn {
  height: 48px !important;
  border: 2px solid var(--primary) !important;
  border-radius: 0 36px 36px 0 !important;
  background: var(--primary) !important;
  color: #fff !important;
  font-size: 15px;
  font-weight: 600;
  margin-left: -2px;
  padding: 0 20px !important;
}

.search-btn:hover {
  background: var(--primary-light) !important;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 24px;
  transition: background 0.2s;
}

.user-dropdown:hover {
  background: var(--bg);
}

.username {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

/* ── Body ─────────────────────────── */

.layout-body {
  flex: 1;
}

.layout-sidebar {
  background: var(--bg-white);
  border-right: 1px solid var(--border);
}

.sidebar-menu {
  border-right: none !important;
  height: 100%;
  padding-top: 8px;
}

.cart-menu-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  margin-left: 8px;
  border-radius: 9px;
  background: var(--el-color-danger, #f56c6c);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  flex-shrink: 0;
}

.layout-main {
  background: var(--bg);
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.back-bar {
  margin-bottom: 12px;
}

.back-bar .el-button {
  font-size: 13px;
  color: var(--text-secondary, #606266);
}

.back-bar .el-button:hover {
  color: var(--primary);
}
</style>
