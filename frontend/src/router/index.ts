import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: DefaultLayout,
    children: [
      { path: '', name: 'home', component: () => import('@/views/Home.vue') },
      { path: 'search', name: 'search', component: () => import('@/views/Search.vue') },
      { path: 'ai-search', name: 'ai-search', component: () => import('@/views/AiSearch.vue') },
      { path: 'map', name: 'map-search', component: () => import('@/views/MapSearch.vue') },

      // ── 三层架构核心 ──
      // 户型 (原 properties → unit-types)
      { path: 'unit-type/create', name: 'create-unit-type', component: () => import('@/views/CreateProperty.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'unit-type/:id/edit', name: 'edit-unit-type', component: () => import('@/views/CreateProperty.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'unit-type/:id/copy', name: 'copy-unit-type', component: () => import('@/views/CreateProperty.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'unit-type/manage', name: 'manage-unit-types', component: () => import('@/views/ManageProperties.vue'), meta: { requiresAuth: true, requiresLandlord: true } },

      // 房间
      { path: 'room/import', name: 'room-import', component: () => import('@/views/publish/BatchImport.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'room/:id', name: 'room-detail', component: () => import('@/views/PropertyDetail.vue') },
      { path: 'room/:id/images', name: 'room-images', component: () => import('@/views/PropertyImages.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'rooms/manage', name: 'manage-rooms', component: () => import('@/views/RoomManagement.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'rooms/:id/transfers', name: 'room-transfers', component: () => import('@/views/RoomTransferLog.vue'), meta: { requiresAuth: true, requiresLandlord: true } },

      // 公寓
      { path: 'buildings', name: 'buildings', component: () => import('@/views/BuildingList.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'buildings/:id/unit-types', name: 'building-unit-types', component: () => import('@/views/UnitTypeList.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'buildings/:id/staff', name: 'building-staff', component: () => import('@/views/BuildingStaff.vue'), meta: { requiresAuth: true, requiresLandlord: true } },

      // 修改记录
      { path: 'property/history', name: 'property-history', component: () => import('@/views/PropertyHistory.vue'), meta: { requiresAuth: true, requiresLandlord: true } },

      // 配套
      { path: 'tenants', name: 'tenants', component: () => import('@/views/TenantManagement.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'orders', name: 'orders', component: () => import('@/views/OrderManagement.vue'), meta: { requiresAuth: true, requiresLandlord: true } },

      // 旧路由兼容
      { path: 'property/create', redirect: '/unit-type/create' },
      { path: 'property/:id/edit', redirect: '/unit-type/:id/edit' },
      { path: 'property/manage', redirect: '/unit-type/manage' },
      { path: 'property/import', redirect: '/room/import' },
      { path: 'property/:id', redirect: (to: any) => `/room/${to.params.id}` },

      // 原有
      { path: 'agent', name: 'agent', component: () => import('@/views/AgentView.vue'), meta: { requiresAuth: true } },
      { path: 'cart', name: 'cart', component: () => import('@/views/CartView.vue'), meta: { requiresAuth: true } },
      { path: 'profile', name: 'profile', component: () => import('@/views/Profile.vue'), meta: { requiresAuth: true } },
      { path: 'profile/edit', name: 'profile-edit', component: () => import('@/views/ProfileEdit.vue'), meta: { requiresAuth: true } },
      { path: 'contract/:id', name: 'contract-view', component: () => import('@/views/ContractView.vue'), meta: { requiresAuth: true } },
      // 预定-支付-合同流程
      { path: 'booking/confirm', name: 'booking-confirm', component: () => import('@/views/BookingConfirm.vue'), meta: { requiresAuth: true } },
      { path: 'booking/payment/:id/deposit', name: 'deposit-payment', component: () => import('@/views/DepositPayment.vue'), meta: { requiresAuth: true } },

      // 租客预定列表
      { path: 'bookings/tenant', name: 'tenant-bookings', component: () => import('@/views/TenantBookings.vue'), meta: { requiresAuth: true } },
      // 房东管理页面
      { path: 'bookings/landlord', name: 'landlord-bookings', component: () => import('@/views/LandlordBookings.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'workspace', name: 'landlord-workspace', component: () => import('@/views/landlord/LandlordDashboard.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'workspace/repairs', name: 'landlord-repairs', component: () => import('@/views/landlord/LandlordRepairs.vue'), meta: { requiresAuth: true, requiresLandlord: true } },
      { path: 'notifications', name: 'notifications', component: () => import('@/views/Notifications.vue'), meta: { requiresAuth: true } },
      { path: 'admin', name: 'admin-dashboard', component: () => import('@/views/admin/AdminDashboard.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/users', name: 'admin-users', component: () => import('@/views/admin/AdminUsers.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/properties', name: 'admin-properties', component: () => import('@/views/admin/AdminProperties.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/logs', name: 'admin-logs', component: () => import('@/views/admin/AdminLogs.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/import', name: 'admin-import', component: () => import('@/views/admin/AdminImport.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'admin/embeddings', name: 'admin-embeddings', component: () => import('@/views/admin/AdminEmbeddings.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
      { path: 'repairs/:id', name: 'repair-detail', component: () => import('@/views/repair/RepairDetail.vue'), meta: { requiresAuth: true } },
      { path: 'bd/dashboard', name: 'bd-dashboard', component: () => import('@/views/bd-manager/BdDashboard.vue'), meta: { requiresAuth: true, requiresBdManager: true } },
      { path: 'customer-service', name: 'customer-service', component: () => import('@/views/CustomerService.vue') },
      { path: 'platform-rules', name: 'platform-rules', component: () => import('@/views/PlatformRules.vue') },
      { path: 'privacy-policy', name: 'privacy-policy', component: () => import('@/views/PrivacyPolicy.vue') },
    ],
  },
  { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { guest: true } },
  { path: '/register', name: 'register', component: () => import('@/views/Register.vue'), meta: { guest: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const userStr = localStorage.getItem('user')
  let user: { role: string } | null = null
  try { if (userStr) user = JSON.parse(userStr) } catch { /* ignore */ }

  if (to.meta.requiresAuth && !token) return next({ name: 'login', query: { redirect: to.fullPath } })
  if (to.meta.guest && token) return next({ name: 'home' })
  if (to.meta.requiresLandlord && user && !['landlord','admin','bd_manager'].includes(user.role)) return next({ name: 'home' })
  if (to.meta.requiresAdmin && user?.role !== 'admin') return next({ name: 'home' })
  if (to.meta.requiresMaintenance && user && !['maintenance_worker','admin'].includes(user.role)) return next({ name: 'home' })
  if (to.meta.requiresBdManager && user && !['bd_manager','admin'].includes(user.role)) return next({ name: 'home' })
  next()
})

export default router
