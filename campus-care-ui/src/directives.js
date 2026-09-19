/* =============================================================
   全局动效指令

   为什么用「指令」而不是「组件」：
     动效是外加在元素上的行为，不是元素本身的身份。用指令就
     不必为每张卡片再套一层 wrapper 组件、多一层 DOM。
     一个 v-spotlight 写在卡片标签上，样式和语义都不动。
   ============================================================= */

/** 系统是否要求减弱动态效果。前庭功能障碍的用户会因位移产生眩晕，这不是可选项。 */
function reducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  )
}

/* -------------------------------------------------------------
   v-reveal —— 滚入视口时淡入上浮
   用法：<div v-reveal>…</div>  /  <div v-reveal="2">…</div>（第 3 个出现）

   用 IntersectionObserver 而不是 scroll 事件：
     scroll 回调在主线程跑，一屏几十张卡就掉帧；IO 由浏览器异步派发，
     回调次数和元素数量无关。
   触发一次就 unobserve：来回滚动反复重播入场动画，
   是「廉价感」最典型的来源。
   ------------------------------------------------------------- */
const REVEAL_OPTS = { threshold: 0.1, rootMargin: '0px 0px -6% 0px' }

let revealObserver = null

function getRevealObserver() {
  if (revealObserver || typeof IntersectionObserver === 'undefined') return revealObserver
  revealObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue
      entry.target.classList.add('is-in')
      revealObserver.unobserve(entry.target)
    }
  }, REVEAL_OPTS)
  return revealObserver
}

export const reveal = {
  mounted(el, binding) {
    el.classList.add('reveal')

    if (reducedMotion()) {
      el.classList.add('is-in')
      return
    }

    // 同一批卡片按顺序依次出现，比整页一起蹦出来有节奏
    const order = Number(binding.value) || 0
    el.style.setProperty('--rv-delay', `${Math.min(order, 12) * 65}ms`)

    const io = getRevealObserver()
    if (!io) {
      el.classList.add('is-in')
      return
    }
    io.observe(el)
  },
  unmounted(el) {
    revealObserver?.unobserve(el)
  },
}

/* -------------------------------------------------------------
   v-spotlight —— 卡片上跟着鼠标走的一圈柔光
   用法：<div class="tile" v-spotlight>…</div>

   做的事只有一件：把鼠标坐标写进 --mx / --my，让背景里那层
   radial-gradient 自己跟过去。不读写任何布局属性，
   所以不会触发重排，也就没有掉帧的风险。
   mousemove 一秒能触发上百次，用 rAF 合并到每帧一次。
   ------------------------------------------------------------- */
export const spotlight = {
  mounted(el) {
    if (reducedMotion()) return
    el.classList.add('spotlight')

    let frame = 0
    let x = 0
    let y = 0

    const flush = () => {
      frame = 0
      el.style.setProperty('--mx', `${x}px`)
      el.style.setProperty('--my', `${y}px`)
    }

    el.__spotMove = (event) => {
      const rect = el.getBoundingClientRect()
      x = event.clientX - rect.left
      y = event.clientY - rect.top
      if (!frame) frame = requestAnimationFrame(flush)
    }

    el.addEventListener('mousemove', el.__spotMove, { passive: true })
  },
  unmounted(el) {
    if (el.__spotMove) el.removeEventListener('mousemove', el.__spotMove)
    delete el.__spotMove
  },
}

/* -------------------------------------------------------------
   v-tilt —— 鼠标在元素上时做轻微 3D 倾斜
   用法：<div v-tilt>…</div>  /  <div v-tilt="3">（最大角度，默认 4°）

   角度压在 4° 以内。超过 6° 就从「有质感」变成「网页小游戏」了。
   只给首页 hero 这样的大块用；卡片多了会晕，也会拖累合成层数量。
   顺带把 -3px 的抬升写进同一支 transform —— 否则内联 transform
   会盖掉 .tile:hover 里的抬升，鼠标一进卡片反而不动了。
   ------------------------------------------------------------- */
export const tilt = {
  mounted(el, binding) {
    if (reducedMotion()) return

    const max = Number(binding.value) || 4
    let frame = 0
    let rx = 0
    let ry = 0

    const flush = () => {
      frame = 0
      el.style.transform = `perspective(1000px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(
        2
      )}deg) translate3d(0, -3px, 0)`
    }

    el.__tiltMove = (event) => {
      const rect = el.getBoundingClientRect()
      // 归一化到 -0.5 ~ 0.5，再乘最大角度 —— 这样不管元素多大，
      // 手感都是「从中心到边缘刚好转满 max 度」
      const px = (event.clientX - rect.left) / rect.width - 0.5
      const py = (event.clientY - rect.top) / rect.height - 0.5
      ry = px * max * 2
      rx = -py * max * 2
      if (!frame) frame = requestAnimationFrame(flush)
    }

    el.__tiltLeave = () => {
      if (frame) cancelAnimationFrame(frame)
      frame = 0
      // 清空内联样式交还给 CSS：.tile 自己的 transition 会把它平滑推回去
      el.style.transform = ''
    }

    el.addEventListener('mousemove', el.__tiltMove, { passive: true })
    el.addEventListener('mouseleave', el.__tiltLeave)
  },
  unmounted(el) {
    if (el.__tiltMove) el.removeEventListener('mousemove', el.__tiltMove)
    if (el.__tiltLeave) el.removeEventListener('mouseleave', el.__tiltLeave)
    delete el.__tiltMove
    delete el.__tiltLeave
  },
}

export function registerDirectives(app) {
  app.directive('reveal', reveal)
  app.directive('spotlight', spotlight)
  app.directive('tilt', tilt)
}
