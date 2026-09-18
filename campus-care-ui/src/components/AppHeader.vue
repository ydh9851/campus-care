<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { currentUser, isCounselor, logout } from '../auth'

const route = useRoute()
const router = useRouter()

const roleText = computed(() =>
  currentUser.value?.role === 'COUNSELOR' ? '辅导员' : '学生'
)

const navs = computed(() => {
  const items = [
    { name: 'chat', label: '咨询会话' },
    { name: 'assessment', label: '心理测评' },
    { name: 'profile', label: '心理档案' },
  ]
  if (isCounselor.value) {
    items.push({ name: 'alerts', label: '预警工单' })
    items.push({ name: 'dashboard', label: '数据看板' })
  }
  return items
})

/** 「心理档案」在查看别人的档案时也要保持高亮，所以要按前缀判断 */
function isActive(name) {
  if (name === 'profile') return route.name === 'profile'
  return route.name === name
}

async function onLogout() {
  await logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="bar">
    <div class="brand">
      <span class="mark" aria-hidden="true"></span>
      <span class="name">CampusCare</span>
      <span class="sub">校园心理支持</span>
    </div>

    <nav class="nav">
      <RouterLink
        v-for="item in navs"
        :key="item.name"
        :to="{ name: item.name }"
        class="nav-item"
        :class="{ active: isActive(item.name) }"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <div class="right">
      <span class="who">
        <span class="uname">{{ currentUser?.realName || currentUser?.username }}</span>
        <span class="role">{{ roleText }}</span>
      </span>
      <button class="logout" type="button" @click="onLogout">退出</button>
    </div>
  </header>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  gap: 32px;
  height: 56px;
  padding: 0 24px;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
  flex: none;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

/* 纯色小方块当 logo，不用图标库、不用渐变圆球 */
.mark {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: var(--brand);
  transform: translateY(1px);
}

.name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.sub {
  font-size: 12px;
  color: var(--ink-3);
}

.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 100%;
}

/* 选中态用「下划线贴到顶栏底边」，比高亮底色安静 */
.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 12px;
  font-size: 14px;
  color: var(--ink-2);
  transition: color 0.15s;
}

.nav-item:hover {
  color: var(--ink);
}

.nav-item.active {
  color: var(--ink);
  font-weight: 500;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 2px;
  background: var(--brand);
}

.right {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: auto;
}

.who {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.uname {
  font-size: 13px;
  color: var(--ink);
}

.role {
  font-size: 11px;
  color: var(--ink-3);
  border: 1px solid var(--line-2);
  border-radius: 3px;
  padding: 0 4px;
  line-height: 16px;
}

.logout {
  border: none;
  background: none;
  padding: 4px 0;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
}

.logout:hover {
  color: var(--brand);
}
</style>
