import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

import './styles.css'
import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api'
import { forceLogout, restoreSession } from './auth'

// api.js 遇到 401 时回调这里：清登录态 + 跳登录页，避免每个请求都写一遍
setUnauthorizedHandler(() => {
  forceLogout()
  if (router.currentRoute.value.name !== 'login') {
    router.push({ name: 'login' })
  }
})

// 先把登录态恢复完再挂载，避免首屏闪一下登录页（路由守卫不能覆盖所有时序）
restoreSession().finally(() => {
  createApp(App)
    .use(router)
    .use(ElementPlus, { locale: zhCn })
    .mount('#app')
})
