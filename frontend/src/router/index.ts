import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: DefaultLayout,
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/views/Home.vue'),
      },
      {
        path: 'search',
        name: 'search',
        component: () => import('@/views/Search.vue'),
      },
      {
        path: 'ai-search',
        name: 'ai-search',
        component: () => import('@/views/AiSearch.vue'),
      },
      {
        path: 'map',
        name: 'map-search',
        component: () => import('@/views/MapSearch.vue'),
      },
      {
        path: 'property/:id',
        name: 'property-detail',
        component: () => import('@/views/PropertyDetail.vue'),
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/Profile.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'profile/edit',
        name: 'profile-edit',
        component: () => import('@/views/ProfileEdit.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'contract/:id',
        name: 'contract-view',
        component: () => import('@/views/ContractView.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'property/create',
        name: 'create-property',
        component: () => import('@/views/CreateProperty.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/:id/edit',
        name: 'edit-property',
        component: () => import('@/views/CreateProperty.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/manage',
        name: 'manage-properties',
        component: () => import('@/views/ManageProperties.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/:id/edit',
        name: 'edit-property',
        component: () => import('@/views/CreateProperty.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/:id/images',
        name: 'property-images',
        component: () => import('@/views/PropertyImages.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'booking/confirm',
        name: 'booking-confirm',
        component: () => import('@/views/BookingConfirm.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/payment/:id',
        name: 'pending-payment',
        component: () => import('@/views/PendingPayment.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/payment/:id/deposit',
        name: 'deposit-payment',
        component: () => import('@/views/DepositPayment.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'bookings/tenant',
        name: 'tenant-bookings',
        component: () => import('@/views/TenantBookings.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'bookings/landlord',
        name: 'landlord-bookings',
        component: () => import('@/views/LandlordBookings.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'customer-service',
        name: 'customer-service',
        component: () => import('@/views/CustomerService.vue'),
      },
      {
        path: 'platform-rules',
        name: 'platform-rules',
        component: () => import('@/views/PlatformRules.vue'),
      },
      {
        path: 'privacy-policy',
        name: 'privacy-policy',
        component: () => import('@/views/PrivacyPolicy.vue'),
      },
      {
        path: 'notifications',
        name: 'notifications',
        component: () => import('@/views/Notifications.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'admin',
        name: 'admin-dashboard',
        component: () => import('@/views/admin/AdminDashboard.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'workspace',
        name: 'landlord-workspace',
        component: () => import('@/views/landlord/LandlordDashboard.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'admin/users',
        name: 'admin-users',
        component: () => import('@/views/admin/AdminUsers.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'admin/properties',
        name: 'admin-properties',
        component: () => import('@/views/admin/AdminProperties.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'admin/logs',
        name: 'admin-logs',
        component: () => import('@/views/admin/AdminLogs.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'admin/embeddings',
        name: 'admin-embeddings',
        component: () => import('@/views/admin/AdminEmbeddings.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'admin/import',
        name: 'admin-import',
        component: () => import('@/views/admin/AdminImport.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      // ---- 报修详情（通用）----
      {
        path: 'repairs/:id',
        name: 'repair-detail',
        component: () => import('@/views/repair/RepairDetail.vue'),
        meta: { requiresAuth: true },
      },
      // ---- 房东报修管理 ----
      {
        path: 'workspace/repairs',
        name: 'landlord-repairs',
        component: () => import('@/views/landlord/LandlordRepairs.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'workspace/workers',
        name: 'landlord-workers',
        component: () => import('@/views/landlord/WorkerManagement.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      // ---- 维修师傅 ----
      {
        path: 'worker/dashboard',
        name: 'worker-dashboard',
        component: () => import('@/views/maintenance/WorkerDashboard.vue'),
        meta: { requiresAuth: true, requiresMaintenance: true },
      },
      {
        path: 'worker/orders',
        name: 'worker-orders',
        component: () => import('@/views/maintenance/WorkerOrders.vue'),
        meta: { requiresAuth: true, requiresMaintenance: true },
      },
      // ---- BD经理 ----
      {
        path: 'bd/dashboard',
        name: 'bd-dashboard',
        component: () => import('@/views/bd-manager/BdDashboard.vue'),
        meta: { requiresAuth: true, requiresBdManager: true },
      },
    ],
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/Register.vue'),
    meta: { guest: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const userStr = localStorage.getItem('user')
  let user: { role: string } | null = null
  try {
    if (userStr) user = JSON.parse(userStr)
  } catch {
    // ignore
  }

  if (to.meta.requiresAuth && !token) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  if (to.meta.guest && token) {
    return next({ name: 'home' })
  }

  if (to.meta.requiresLandlord && user && user.role !== 'landlord' && user.role !== 'admin' && user.role !== 'bd_manager') {
    return next({ name: 'home' })
  }

  if (to.meta.requiresAdmin && user && user.role !== 'admin') {
    return next({ name: 'home' })
  }

  if (to.meta.requiresMaintenance && user && user.role !== 'maintenance_worker' && user.role !== 'admin') {
    return next({ name: 'home' })
  }

  if (to.meta.requiresBdManager && user && user.role !== 'bd_manager' && user.role !== 'admin') {
    return next({ name: 'home' })
  }

  next()
})

export default router
