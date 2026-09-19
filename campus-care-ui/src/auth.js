import { computed, reactive } from 'vue'
import { authApi, clearToken, getToken, setToken } from './api'

/**
 * 登录态。
 *
 * 只做两件事：把 token 放 localStorage（刷新页面不丢），
 * 把用户信息放在内存里（刷新后用 /auth/me 重新拉一次）。
 * 项目小，没必要上 Pinia。
 */
const state = reactive({
  user: null,
  ready: false, // 是否已经尝试过恢复登录态
})

export const isLoggedIn = computed(() => !!state.user)
export const currentUser = computed(() => state.user)
export const authReady = computed(() => state.ready)

/** 辅导员/管理员才能进预警工作台 */
export const isCounselor = computed(() => {
  const role = state.user?.role
  return role === 'COUNSELOR' || role === 'ADMIN'
})

export async function login(username, password) {
  const data = await authApi.login(username, password)
  if (!data || !data.token) {
    throw new Error('登录失败，服务器未返回有效凭证，请稍后重试')
  }
  setToken(data.token)
  state.user = {
    userId: data.userId,
    username: data.username,
    realName: data.realName,
    role: data.role,
  }
  state.ready = true
  return state.user
}

export async function logout() {
  try {
    await authApi.logout()
  } catch {
    // 后端已失效也无所谓，本地清干净就行
  }
  clearToken()
  state.user = null
}

/**
 * 应用启动时调用：带着 localStorage 里的 token 去问一次「我是谁」。
 * token 已过期/被登出时，api.js 的 401 分支会把它清掉。
 */
export async function restoreSession() {
  if (!getToken()) {
    state.ready = true
    return
  }
  try {
    state.user = await authApi.me()
  } catch {
    state.user = null
  } finally {
    state.ready = true
  }
}

export function forceLogout() {
  clearToken()
  state.user = null
}
