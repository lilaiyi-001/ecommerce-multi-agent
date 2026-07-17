import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../api/index.js'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/chat', name: 'Chat', component: () => import('../views/Chat.vue') },
  { path: '/selection', name: 'Selection', component: () => import('../views/Selection.vue') },
  { path: '/trend', name: 'Trend', component: () => import('../views/Trend.vue') },
  { path: '/competitor', name: 'Competitor', component: () => import('../views/Competitor.vue') },
  { path: '/profile', name: 'Profile', component: () => import('../views/Profile.vue') },
  { path: '/pricing', name: 'Pricing', component: () => import('../views/Pricing.vue') },
  { path: '/copy', name: 'Copy', component: () => import('../views/Copy.vue') },
  { path: '/inventory', name: 'Inventory', component: () => import('../views/Inventory.vue') },
  { path: '/promotion', name: 'Promotion', component: () => import('../views/Promotion.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, from, next) => {
  if (to.meta.public) {
    next()
  } else if (isAuthenticated()) {
    next()
  } else {
    next('/login')
  }
})

export default router
