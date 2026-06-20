<template>
  <el-container class="layout-container">
    <!-- Top Navigation -->
    <el-header class="layout-header">
      <div class="header-left">
        <router-link to="/" class="logo">
          <el-icon :size="24"><House /></el-icon>
          <span class="logo-text">租房匹配</span>
        </router-link>
      </div>
      <div class="header-center">
        <el-input
          v-model="searchQuery"
          placeholder="搜索房源、小区、区域..."
          :prefix-icon="Search"
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button :icon="Search" @click="handleSearch" />
          </template>
        </el-input>
      </div>
      <div class="header-right">
        <template v-if="authStore.isLoggedIn">
          <el-dropdown trigger="click">
            <span class="user-dropdown">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">{{ authStore.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click=".push('/profile')">
                  <el-icon><User /></el-icon> 个人中心
                </el-dropdown-item>
                <el-dropdown-item v-if="authStore.isLandlord" @click=".push('/property/manage')">
                  <el-icon><Setting /></el-icon> 房源管理
                </el-dropdown-item>
                <el-dropdown-item divided @click="authStore.logout()">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button type="primary" @click=".push('/login')">登录</el-button>
          <el-button @click=".push('/register')">注册</el-button>
        </template>
      </div>
    </el-header>

    <el-container class="layout-body">
      <!-- Sidebar -->
      <el-aside class="layout-sidebar" width="200px">
        <el-menu
          :default-active="activeMenu"
          router
          class="sidebar-menu"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/search">
            <el-icon><Search /></el-icon>
            <span>搜索房源</span>
          </el-menu-item>
          <template v-if="authStore.isLandlord">
            <el-menu-item index="/property/create">
              <el-icon><Plus /></el-icon>
              <span>发布房源</span>
            </el-menu-item>
            <el-menu-item index="/property/manage">
              <el-icon><List /></el-icon>
              <span>房源管理</span>
            </el-menu-item>
          </template>
          <el-menu-item v-if="authStore.isLoggedIn" index="/profile">
            <el-icon><User /></el-icon>
            <span>个人中心</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- Main Content -->
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, UserFilled, ArrowDown, House, HomeFilled, User, Setting, SwitchButton, Plus, List } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const searchQuery = ref('')

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/property/')) {
    if (path === '/property/create') return '/property/create'
    if (path === '/property/manage') return '/property/manage'
    return '/search'
  }
  return path
})

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ name: 'search', query: { q: searchQuery.value.trim() } })
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
  height: 60px;
}

.header-left .logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: #409eff;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
}

.header-center {
  flex: 1;
  max-width: 480px;
  margin: 0 40px;
}

.search-input {
  width: 100%;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.username {
  font-size: 14px;
  color: #303133;
}

.layout-body {
  height: calc(100vh - 60px);
}

.layout-sidebar {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.sidebar-menu {
  border-right: none;
  height: 100%;
}

.layout-main {
  background: #f5f7fa;
  overflow-y: auto;
  padding: 24px;
}
</style>
