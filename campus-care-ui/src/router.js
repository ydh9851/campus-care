import { createRouter, createWebHistory } from 'vue-router'
import { authReady, currentUser, isCounselor } from './auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('./views/LoginView.vue'),
    meta: { bare: true }, // 登录页不显示顶部导航
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('./views/ChatView.vue'),
  },
  {
    path: '/assessment',
    name: 'assessment',
    component: () => import('./views/AssessmentView.vue'),
  },
  {
    // /profile       -> 我的档案
    // /profile/:userId -> 辅导员查看某学生档案（后端用 @PreAuthorize 兜底）
    path: '/profile/:userId?',
    name: 'profile',
    component: () => import('./views/ProfileView.vue'),
  },
  {
    // 数据看板：仅辅导员/管理员可见，后端 @PreAuthorize 兜底
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('./views/DashboardView.vue'),
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('./views/AlertView.vue'),
    meta: { counselorOnly: true },
  },
  { path: '/', redirect: '/chat' },
  { path: '/:pathMatch(.*)*', redirect: '/chat' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * 路由守卫。
 * 注意 authReady：刷新页面时 restoreSession() 还没跑完，
 * 这时 currentUser 是 null —— 如果直接跳登录页，用户会觉得「刚登录就被踢了」。
 * 所以必须等「恢复登录态」这一步结束再判断。
 */
router.beforeEach(async (to) => {
  if (!authReady.value) {
    await new Promise((resolve) => {
      const timer = setInterval(() => {
        if (authReady.value) {
          clearInterval(timer)
          resolve()
        }
      }, 20)
    })
  }

  if (to.meta.bare) return true

  if (!currentUser.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.counselorOnly && !isCounselor.value) {
    return { name: 'chat' }
  }
  return true
})

export default router
