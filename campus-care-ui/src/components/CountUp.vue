<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

/**
 * 数字滚动。
 *
 * 为什么值得单独做个组件：
 *   看板上的数字是整页唯一「有信息量又看得见」的东西。让它从 0 数上去，
 *   用户的目光会被自动带过去，比一个静止的数字强得多。
 *   代价只是几百毫秒，比任何装饰性动画都划算。
 *
 * 非数字（null / '—' / 空）不参与补间，原样显示 —— 硬把 '—' 数成 0 是错的。
 */
const props = defineProps({
  value: { type: [Number, String], default: 0 },
  /** 补间时长（ms） */
  duration: { type: Number, default: 900 },
  /** 后缀。单独拼在数字后面，而不是让它跟着一起补间（否则 '%' 会闪） */
  suffix: { type: String, default: '' },
})

const numeric = computed(() => {
  const n = Number(props.value)
  return Number.isFinite(n) ? n : null
})

const shown = ref(0)
let frame = 0

function run() {
  const to = numeric.value
  if (to === null) return
  cancelAnimationFrame(frame)

  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    shown.value = to
    return
  }

  const start = performance.now()
  const step = (now) => {
    const t = Math.min(1, (now - start) / props.duration)
    // easeOutExpo：前段冲得快、最后慢慢贴住目标值。
    // 匀速补间看起来像进度条，不像"数字停下来"。
    const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
    shown.value = Math.round(to * eased)
    if (t < 1) frame = requestAnimationFrame(step)
  }
  frame = requestAnimationFrame(step)
}

onMounted(run)
watch(numeric, run)
onBeforeUnmount(() => cancelAnimationFrame(frame))
</script>

<template>
  <span>{{ numeric === null ? value : shown }}{{ suffix }}</span>
</template>
