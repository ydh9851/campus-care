<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandMark from './BrandMark.vue'
import { currentUser, isCounselor, logout } from '../auth'

const route = useRoute()
const router = useRouter()

const roleText = computed(() =>
  currentUser.value?.role === 'COUNSELOR' ? '辅导员' : '学生'
)

/** 头像只取首字。中文取姓，英文取首字母 —— 比默认头像图更省事也更稳。
 *  取首字用 [...str][0]：slice(0,1) 会把代理对（emoji、生僻字）切成半个字符，
 *  渲染出来就是一个「乱码方块」。 */
const initial = computed(() => {
  const raw = currentUser.value?.realName || currentUser.value?.username || '?'
  return [...String(raw).trim()][0]?.toUpperCase() || '?'
})

const navs = computed(() => {
  const items = [
    { name: 'home', label: '首页' },
    { name: 'chat', label: '咨询会话' },
    { name: 'assessment', label: '心理测评' },
    { name: 'profile', label: '心理档案' },
    { name: 'knowledge', label: '心理科普' },
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

/* ---------------- 滑动指示器 ---------------- */

const navEl = ref(null)
const ink = ref({ x: 0, w: 0, ready: false })

/**
 * 全站只有一枚下划线元素，靠 transform 在导航项之间平移。
 *
 * 为什么不做成「每项各自一个下划线淡入淡出」：
 *   淡入淡出是无方向的，从「首页」点到「看板」，下划线是原地消失再原地出现；
 *   平移则明确告诉你"往右走了两格"。多花不到 20 行，但整条导航的
 *   连贯度完全不一样 —— 这是 Awwwards 那类站点几乎必有的一处细节。
 */
function syncInk() {
  const nav = navEl.value
  if (!nav) return
  const active = nav.querySelector('.nav-item.active')
  if (!active) {
    ink.value = { x: 0, w: 0, ready: ink.value.ready }
    return
  }
  ink.value = { x: active.offsetLeft, w: active.offsetWidth, ready: true }
}

/* 顶栏在页面滚动后加深：一层很淡的投影告诉用户"内容从下面过去了"。
   注意这里用 capture 监听 —— 每个页面有自己的滚动容器（不是 window），
   只有捕获阶段才能收到它们的 scroll 事件。 */
const scrolled = ref(false)
let rafId = 0

function onAnyScroll(event) {
  const target = event.target
  if (!target) return
  const top = target === document ? window.scrollY : target.scrollTop
  const next = top > 6
  // 滚动事件一秒能来几十次，只用 rAF 合并写一次状态
  if (next === scrolled.value || rafId) return
  rafId = requestAnimationFrame(() => {
    rafId = 0
    scrolled.value = next
  })
}

let ro = null

onMounted(() => {
  syncInk()
  nextTick(syncInk)

  document.addEventListener('scroll', onAnyScroll, true)

  // 导航项数量会随角色变化（辅导员多两项），宽度也会随字体/缩放变
  if (typeof ResizeObserver !== 'undefined' && navEl.value) {
    ro = new ResizeObserver(syncInk)
    ro.observe(navEl.value)
  }
  window.addEventListener('resize', syncInk)
})

onBeforeUnmount(() => {
  document.removeEventListener('scroll', onAnyScroll, true)
  window.removeEventListener('resize', syncInk)
  ro?.disconnect()
  if (rafId) cancelAnimationFrame(rafId)
})

watch(
  () => [route.name, navs.value.length],
  () => nextTick(syncInk)
)

async function onLogout() {
  await logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="bar" :class="{ scrolled }">
    <div class="brand">
      <span class="brand-badge">
        <BrandMark :size="19" class="mark" />
      </span>
      <span class="name">CampusCare</span>
      <span class="sub">校园心理支持</span>
    </div>

    <nav ref="navEl" class="nav">
      <RouterLink
        v-for="item in navs"
        :key="item.name"
        :to="{ name: item.name }"
        class="nav-item"
        :class="{ active: isActive(item.name) }"
      >
        {{ item.label }}
      </RouterLink>

      <!-- 唯一一枚滑动下划线。首次定位完成前先藏起来，
           否则会在过渡动画里从左上角"飞"到目标位置。 -->
      <span
        class="nav-ink"
        :style="{
          transform: `translateX(${ink.x}px)`,
          width: `${ink.w}px`,
          opacity: ink.ready ? 1 : 0,
        }"
      />
    </nav>

    <div class="right">
      <span class="who">
        <span class="avatar">{{ initial }}</span>
        <span class="uname">{{ currentUser?.realName || currentUser?.username }}</span>
        <span class="role">{{ roleText }}</span>
      </span>
      <button class="logout" type="button" @click="onLogout">退出</button>
    </div>
  </header>
</template>

<style scoped>
.bar {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 32px;
  height: 58px;
  padding: 0 24px;
  flex: none;
  /* 玻璃拟态：半透明 + 背景模糊 + 一道内高光。
     内高光那条 1px 白线是"玻璃"的关键 —— 没有它，半透明面板看起来
     只是"掺了水的白"，加上它才有"一块玻璃浮在内容上"的体积感。 */
  background: rgba(255, 255, 255, 0.66);
  -webkit-backdrop-filter: blur(18px) saturate(180%);
  backdrop-filter: blur(18px) saturate(180%);
  border-bottom: 1px solid transparent;
  box-shadow: inset 0 1px 0 var(--glass-line);
  transition:
    background-color 0.3s var(--ease),
    border-color 0.3s var(--ease),
    box-shadow 0.3s var(--ease);
}

/* 滚动后：底色更实、底边浮出来、投影加深。
   三件事一起发生，顶栏才像"从内容里抬起来"，而不是换了个颜色。 */
.bar.scrolled {
  background: rgba(255, 255, 255, 0.82);
  border-bottom-color: var(--line);
  box-shadow:
    inset 0 1px 0 var(--glass-line),
    0 8px 24px -18px rgba(20, 22, 26, 0.5);
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  cursor: default;
}

/* 标识装在一枚浅绿方块里。
   顶栏是一整条白，Logo 直接飘在上面会没有"落点"，加个底色才立得住。 */
.brand-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--brand-soft);
  box-shadow: inset 0 0 0 1px rgba(44, 95, 82, 0.08);
  transition:
    background-color 0.3s var(--ease),
    box-shadow 0.3s var(--ease);
}

.mark {
  color: var(--brand);
  transition:
    transform 0.55s var(--ease-out),
    color 0.3s var(--ease);
}

/* 悬停品牌区：方块翻成品牌渐变、标识转一段。
   一枚 28px 的方块转 120°，动静刚好在"被注意到"和"打扰"之间。 */
.brand:hover .brand-badge {
  background: var(--brand-grad);
  box-shadow: var(--glow);
}

.brand:hover .mark {
  color: #fff;
  transform: rotate(120deg);
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
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  height: 100%;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 12px;
  font-size: 14px;
  color: var(--ink-2);
  transition: color 0.18s var(--ease);
}

.nav-item:hover {
  color: var(--ink);
}

.nav-item.active {
  color: var(--ink);
  font-weight: 500;
}

/* 悬停预览：只露出 42% 的一小截，像在说"这里可以点"。
   真正的选中态交给下面那枚滑动下划线 —— 两者分工，不重复。 */
.nav-item::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 2px;
  border-radius: 1px;
  background: var(--brand);
  opacity: 0.32;
  transform: scaleX(0);
  transform-origin: center;
  transition: transform 0.26s var(--ease-out);
}

.nav-item:hover::after {
  transform: scaleX(0.42);
}

.nav-item.active::after {
  transform: scaleX(0);
}

.nav-ink {
  position: absolute;
  left: 0;
  bottom: -1px;
  height: 2px;
  border-radius: 2px;
  background: var(--brand-grad);
  pointer-events: none;
  transition:
    transform 0.42s var(--ease-out),
    width 0.42s var(--ease-out),
    opacity 0.24s var(--ease);
}

.right {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: auto;
}

.who {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 首字头像：一枚品牌渐变小圆。
   比放一张默认头像图更轻，也比纯文字多一个视觉落点。 */
.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  box-shadow: 0 0 0 1px rgba(44, 95, 82, 0.12);
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
  transition: color 0.18s var(--ease);
}

.logout:hover {
  color: var(--brand);
}
</style>
