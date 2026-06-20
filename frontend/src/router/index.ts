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
        path: 'property/create',
        name: 'create-property',
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
        path: 'property/:id/images',
        name: 'property-images',
        component: () => import('@/views/PropertyImages.vue'),
        meta: { requiresAuth: true, requiresLandlord: true },
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

// Navigation guards
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const userStr = localStorage.getItem('user')
  let user: { role: string } | null = null
  try {
    if (userStr) user = JSON.parse(userStr)
  } catch {
    // ignore parse errors
  }

  // Auth-required routes
  if (to.meta.requiresAuth && !token) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  // Guest-only routes (login/register) - redirect to home if already logged in
  if (to.meta.guest && token) {
    return next({ name: 'home' })
  }

  // Landlord/admin routes
  if (to.meta.requiresLandlord && user && user.role !== 'landlord' && user.role !== 'admin') {
    return next({ name: 'home' })
  }

  next()
})

export default router
