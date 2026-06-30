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
        component: () => import('@/views/AdminWorkspace.vue'),
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

  if (to.meta.requiresLandlord && user && user.role !== 'landlord' && user.role !== 'admin') {
    return next({ name: 'home' })
  }

  if (to.meta.requiresAdmin && user && user.role !== 'admin') {
    return next({ name: 'home' })
  }

  next()
})

export default router
