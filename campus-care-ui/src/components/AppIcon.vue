<script setup>
import { computed } from 'vue'

/**
 * 全站图标。
 *
 * 为什么自己画、不引 Element Plus 的图标库：
 *   el-icon 只有 ~10 个通用图标（搜索、箭头、关闭），业务语义的图标
 *   （倾诉、测评、工单、看板、科普）根本没有；而 iconify / font-awesome
 *   为了 13 个图标引一整个包，体积上不划算，风格也未必统一。
 *   这里 13 个图标一次写完，全部 24×24 网格、1.7 描边、圆头圆角，
 *   所以它们在页面上是"同一家人"——这一步是整体质感的前提。
 *
 * 结构说明：
 *   大多数图标是一条或几条路径（paths）；只有"看板"这种本质是方块的，
 *   额外支持 rects，用真矩形而不是硬凑成 path，圆角才干净。
 */
const props = defineProps({
  /** 图标名，见下方 ICONS */
  name: { type: String, required: true },
  /** 边长（px） */
  size: { type: [Number, String], default: 18 },
  /** 描边粗细，小尺寸下可以调粗一点保证可读性 */
  stroke: { type: [Number, String], default: 1.7 },
})

const ICONS = {
  /* 倾诉 / 对话 */
  chat: { paths: ['M7.9 20A9 9 0 1 0 4 16.1L2 22Z'] },

  /* 测评：带勾选清单的写字板 */
  clipboard: {
    paths: [
      'M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2',
      'M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Z',
      'M12 11h4',
      'M12 16h4',
      'M8 11h.01',
      'M8 16h.01',
    ],
  },

  /* 档案 */
  folder: {
    paths: [
      'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
    ],
  },

  /* 科普：摊开的书 */
  book: {
    paths: [
      'M12 7v14',
      'M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z',
    ],
  },

  /* 预警工单 */
  alert: {
    paths: [
      'm21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z',
      'M12 9v4',
      'M12 17h.01',
    ],
  },

  /* 数据看板 */
  dashboard: {
    rects: [
      { x: 3, y: 3, w: 7, h: 9, r: 1.6 },
      { x: 14, y: 3, w: 7, h: 5, r: 1.6 },
      { x: 14, y: 11, w: 7, h: 10, r: 1.6 },
      { x: 3, y: 15, w: 7, h: 6, r: 1.6 },
    ],
  },

  /* 小贴士 */
  sparkles: {
    paths: [
      'M11 3.5 12.6 8.4 17.5 10 12.6 11.6 11 16.5 9.4 11.6 4.5 10 9.4 8.4Z',
      'M18 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z',
    ],
  },

  /* 危机热线 */
  phone: {
    paths: [
      'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92Z',
    ],
  },

  refresh: { paths: ['M21 12a9 9 0 1 1-2.64-6.36', 'M21 3v6h-6'] },

  user: {
    paths: [
      'M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2',
      'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
    ],
  },

  /* 隐私 / 安全 */
  shield: {
    paths: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z', 'm9 11.5 2 2 4-4'],
  },

  clock: { paths: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z', 'M12 7.5V12l3 2'] },

  /* 情绪趋势 */
  trend: { paths: ['M3 20h18', 'm4 14.5 4.5-5 3.5 3L20 5.5'] },

  /* 进入 / 跳转。之前漏登记过："进入 →" 里的箭头一直渲染成一片空白，
     只在视觉上留个 13px 的空档，不报错也不显眼，所以必须在这里补齐。 */
  arrow: { paths: ['M5 12h14', 'm12 5 7 7-7 7'] },
}

/* 名字写错时静默渲染成空白，是最难发现的一类 bug（页面上只是"少了个图标"）。
   开发环境下直接点名，构建产物里这段会被常量折叠掉。 */
const warned = new Set()

const icon = computed(() => {
  const hit = ICONS[props.name]
  if (!hit && import.meta.env?.DEV && !warned.has(props.name)) {
    warned.add(props.name)
    console.warn(`[AppIcon] 未登记的图标名 "${props.name}"，这里会渲染成空白`)
  }
  return hit || { paths: [] }
})
</script>

<template>
  <svg
    class="app-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="stroke"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <rect
      v-for="(r, i) in icon.rects || []"
      :key="`r${i}`"
      :x="r.x"
      :y="r.y"
      :width="r.w"
      :height="r.h"
      :rx="r.r"
    />
    <path v-for="(d, i) in icon.paths || []" :key="`p${i}`" :d="d" />
  </svg>
</template>

<style scoped>
.app-icon {
  display: block;
  flex: none;
}
</style>
