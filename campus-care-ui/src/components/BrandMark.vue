<script setup>
/**
 * 品牌标识。
 *
 * 用几何说事，而不是画一颗心加一个对话气泡 —— 那套符号在心理健康类产品里
 * 已经被用到失去含义了。这里三个元素的含义：
 *   外圈细环 = 心理中心提供的安全场域
 *   主环缺口 = 不封闭、留出口（不是"被关起来"，随时可以走出去）
 *   中心圆点 = 学生本人
 *
 * 全部走 currentColor，所以同一份代码在深色登录页和浅色顶栏都能直接用，
 * 不用维护两份资源。
 */
defineProps({
  /** 边长（px），SVG 会等比缩放 */
  size: { type: [Number, String], default: 28 },
})
</script>

<template>
  <svg
    class="brand-mark"
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    fill="none"
    aria-hidden="true"
  >
    <!-- 外圈：极细，只作"场域"的暗示，不抢主体 -->
    <circle
      cx="24"
      cy="24"
      r="21"
      stroke="currentColor"
      stroke-opacity="0.16"
      stroke-width="1.4"
    />

    <!-- 主环：周长 2π×16.5 ≈ 103.7，留 20 的缺口（约 70°），
         旋转 -18° 后缺口落在右上 —— 视觉上是个"开口"，不是"闭环" -->
    <circle
      cx="24"
      cy="24"
      r="16.5"
      stroke="currentColor"
      stroke-width="3.2"
      stroke-linecap="round"
      stroke-dasharray="83.7 20"
      transform="rotate(-18 24 24)"
    />

    <!-- 中心：学生本人 -->
    <circle cx="24" cy="24" r="5" fill="currentColor" />
  </svg>
</template>

<style scoped>
.brand-mark {
  display: block;
  flex: none;
}
</style>
