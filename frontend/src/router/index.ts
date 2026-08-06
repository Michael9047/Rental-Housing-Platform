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
        meta: { hideFooter: true },
      },
      {
        path: 'ai-search',
        name: 'ai-search',
        component: () => import('@/views/AiSearch.vue'),
        meta: { hideFooter: true },
      },
      {
        path: 'cart',
        name: 'cart',
        component: () => import('@/views/CartView.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'room/:id',
        name: 'property-detail',
        component: () => import('@/views/BuildingRedirect.vue'),
      },
      // 兼容旧版 /property/:id 链接
      {
        path: 'property/:id',
        redirect: (to: any) => ({ path: `/building/${to.params.id}` }),
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
        path: 'my-contracts/:id',
        name: 'my-contract-detail',
        component: () => import('@/views/MyContractDetail.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'my-orders/:id',
        name: 'my-order-detail',
        component: () => import('@/views/MyOrderDetail.vue'),
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
        path: 'property/import',
        name: 'batch-import',
        component: () => import('@/views/publish/BatchImport.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/publish',
        name: 'publish-home',
        component: () => import('@/views/publish/PublishHome.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/manage',
        name: 'manage-properties',
        component: () => import('@/views/ManageProperties.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'buildings/:id/unit-types',
        name: 'building-unit-types',
        component: () => import('@/views/UnitTypeList.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'buildings/:id/staff',
        name: 'building-staff',
        component: () => import('@/views/BuildingStaff.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'unit-type/manage',
        name: 'unit-type-manage',
        component: () => import('@/views/ManageProperties.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'unit-type/create',
        name: 'unit-type-create',
        component: () => import('@/views/CreateProperty.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'unit-type/:id/edit',
        name: 'unit-type-edit',
        component: () => import('@/views/CreateProperty.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'unit-type/:id/copy',
        name: 'unit-type-copy',
        component: () => import('@/views/CreateProperty.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/history',
        name: 'property-history',
        component: () => import('@/views/PropertyHistory.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'property/:id/images',
        name: 'property-images',
        component: () => import('@/views/PropertyImages.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      {
        path: 'booking/:id/move-in-date',
        redirect: (to: any) => ({ name: 'property-detail', params: { id: to.params.id } }),
      },
      // ── 新版预订流程（6步）──
      {
        path: 'booking/:propertyId/move-in-date',
        name: 'booking-move-in-date',
        component: () => import('@/views/booking/MoveInDate.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/:propertyId/lease-term',
        name: 'booking-lease-term',
        component: () => import('@/views/booking/LeaseTerm.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/:propertyId/personal-info',
        name: 'booking-personal-info',
        component: () => import('@/views/booking/PersonalInfo.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/:propertyId/emergency-contact',
        name: 'booking-emergency-contact',
        component: () => import('@/views/booking/EmergencyContact.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/:propertyId/review',
        name: 'booking-review',
        component: () => import('@/views/booking/BookingReview.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/:propertyId/contract',
        name: 'booking-contract-placeholder',
        component: () => import('@/views/booking/ContractPlaceholder.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'booking/order/:bookingId/:status',
        name: 'booking-result',
        component: () => import('@/views/BookingResult.vue'),
        meta: { requiresAuth: true },
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
        path: 'building/:id',
        name: 'building-detail',
        component: () => import('@/views/BuildingDetail.vue'),
      },
      {
        path: 'buildings',
        name: 'buildings',
        component: () => import('@/views/BuildingList.vue'),
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
        path: 'workspace',
        name: 'landlord-workspace',
        component: () => import('@/views/admin/AdminWorkspace.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
      // ---- 报修（通用）----
      {
        path: 'repairs',
        name: 'repair-list',
        component: () => import('@/views/repair/RepairList.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'repairs/:id',
        name: 'repair-detail',
        component: () => import('@/views/repair/RepairDetail.vue'),
        meta: { requiresAuth: true },
      },
      // ---- 房东报修管理 ----
      {
        path: 'workspace/visit-messages',
        name: 'landlord-visit-messages',
        component: () => import('@/views/landlord/VisitMessages.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
      },
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
      // ---- 管理员（共用主布局）----
      {
        path: 'admin',
        name: 'admin-dashboard',
        component: () => import('@/views/admin/AdminWorkspace.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'admin/users',
        name: 'admin-users',
        component: () => import('@/views/admin/AdminUsers.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      {
        path: 'admin/logs',
        name: 'admin-logs',
        component: () => import('@/views/admin/AdminLogs.vue'),
        meta: { requiresAuth: true, requiresAdmin: true },
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
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('@/views/ForgotPassword.vue'),
    meta: { guest: true },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/views/ResetPassword.vue'),
    meta: { guest: true },
  },
  {
    path: '/auth/wechat/callback',
    name: 'wechat-callback',
    component: () => import('@/views/WeChatCallback.vue'),
    meta: { guest: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  // 清理损坏的 localStorage（user 为 {} 或缺少 role 字段）
  const userStr = localStorage.getItem('user')
  if (userStr) {
    try {
      const parsed = JSON.parse(userStr)
      if (!parsed || !parsed.role) {
        localStorage.clear()
        if (to.name !== 'login') return next({ name: 'login' })
      }
    } catch {
      localStorage.clear()
      if (to.name !== 'login') return next({ name: 'login' })
    }
  }

  const token = localStorage.getItem('access_token')
  const _userStr = localStorage.getItem('user')
  let user: { role: string } | null = null
  try {
    if (_userStr) user = JSON.parse(_userStr)
  } catch {
    // ignore
  }

  if (to.meta.requiresAuth && !token) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  if (to.meta.guest && token) {
    if (user?.role === 'admin') return next({ name: 'admin-dashboard' })
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
