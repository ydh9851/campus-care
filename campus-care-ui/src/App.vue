<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
const showHeader = computed(() => !route.meta.bare)
</script>

<template>
  <div class="app">
    <!-- 背景极光：三团缓慢漂移的品牌色光斑。
         它的职责是让「灰底」不至于像一张没画完的纸，而不是被看见 ——
         所以强度压得很低，而且全程 pointer-events: none。 -->
    <div class="aurora" aria-hidden="true">
      <span class="b1" />
      <span class="b2" />
      <span class="b3" />
    </div>

    <!-- 颗粒：一层 2.8% 的灰噪点。作用不是「看见颗粒」，
         而是消掉大面积浅色渐变在低色深屏上的色带，顺带给平面一点纸的质感。 -->
    <div class="grain" aria-hidden="true" />

    <AppHeader v-if="showHeader" />
    <RouterView v-slot="{ Component }">
      <component :is="Component" :class="showHeader ? 'with-header' : ''" />
    </RouterView>
  </div>
</template>

<style scoped>
.app {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 除了背景两层，其余内容一律抬到 z-index: 1 之上。
   用 :not 精确排除，而不是给每个子元素各写一遍 —— 以后加页面不会漏。 */
.app > :not(.aurora):not(.grain) {
  position: relative;
  z-index: 1;
}

/* 有顶栏时，内容区占满剩余高度 */
.with-header {
  flex: 1;
  min-height: 0;
}

/* ---------- 极光 ---------- */
.aurora {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.aurora span {
  position: absolute;
  display: block;
  border-radius: 50%;
  /* 90px 的模糊让光斑没有边界，看起来才像"光"而不是"圆"。
     代价是一次性的绘制开销 —— 之后只走 transform，由合成器接管。 */
  filter: blur(90px);
}

/* 三团光斑的周期取 26 / 34 / 42 秒。这三个数互质：
   它们永远不会同时回到起点，所以看不出这是在循环播放。
   周期一旦取成一样，「背景在动」就会变成「背景在鬼畜」。 */
.aurora .b1 {
  width: 760px;
  height: 760px;
  top: -28%;
  left: -14%;
  background: radial-gradient(circle, var(--aurora-1) 0%, rgba(61, 125, 107, 0) 68%);
  animation: aurora-a 26s var(--ease) infinite;
}

.aurora .b2 {
  width: 640px;
  height: 640px;
  top: 6%;
  right: -12%;
  background: radial-gradient(circle, var(--aurora-3) 0%, rgba(122, 168, 155, 0) 68%);
  animation: aurora-b 34s var(--ease) infinite;
}

.aurora .b3 {
  width: 720px;
  height: 720px;
  bottom: -32%;
  left: 26%;
  background: radial-gradient(circle, var(--aurora-2) 0%, rgba(44, 95, 82, 0) 70%);
  animation: aurora-c 42s var(--ease) infinite;
}

@keyframes aurora-a {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(7%, 9%, 0) scale(1.14);
  }
}

@keyframes aurora-b {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1.08);
  }
  50% {
    transform: translate3d(-9%, 7%, 0) scale(0.93);
  }
}

@keyframes aurora-c {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(-7%, -9%, 0) scale(1.12);
  }
}

/* ---------- 颗粒 ---------- */
.grain {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.028;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* 系统开了「减弱动态效果」：光斑就地冻住。
   冻住的静态光斑仍然是有效的背景，不需要整个删掉。 */
@media (prefers-reduced-motion: reduce) {
  .aurora span {
    animation: none;
  }
}
</style>
