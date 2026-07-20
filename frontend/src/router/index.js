import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../api/index.js'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/report', name: 'ReportGenerator', component: () => import('../views/ReportGenerator.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

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
