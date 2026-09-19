<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  width: { type: Number, default: 280 },
  height: { type: Number, default: 36 },
})

const emit = defineEmits(['success', 'fail'])

const railRef = ref(null)
const trackW = computed(() => props.width)
const trackH = computed(() => props.height)

const state = ref('idle') // idle | sliding | success | fail
const progress = ref(0)

const thumbW = 40
const targetX = ref(0)

function reset() {
  state.value = 'idle'
  progress.value = 0
  targetX.value = Math.floor(Math.random() * (props.width - thumbW - 60)) + 50
}

onMounted(reset)

let startX = 0
let startLeft = 0
let dragging = false

function onPointerDown(e) {
  if (state.value === 'success') return
  dragging = true
  startX = e.clientX || e.touches?.[0]?.clientX || 0
  startLeft = progress.value
  state.value = 'sliding'
}

function onPointerMove(e) {
  if (!dragging) return
  const cx = e.clientX || e.touches?.[0]?.clientX || startX
  let dx = cx - startX
  let val = startLeft + dx
  const max = trackW.value - thumbW
  if (val < 0) val = 0
  if (val > max) val = max
  progress.value = val
}

function onPointerUp() {
  if (!dragging) return
  dragging = false
  const max = trackW.value - thumbW
  const ratio = progress.value / max
  const targetRatio = targetX.value / max
  const tolerance = 0.06

  if (Math.abs(ratio - targetRatio) <= tolerance) {
    state.value = 'success'
    progress.value = targetX.value
    emit('success')
  } else {
    state.value = 'fail'
    emit('fail')
    setTimeout(() => {
      progress.value = 0
      state.value = 'idle'
      targetX.value = Math.floor(Math.random() * (props.width - thumbW - 60)) + 50
    }, 400)
  }
}

onMounted(() => {
  window.addEventListener('mousemove', onPointerMove)
  window.addEventListener('mouseup', onPointerUp)
  window.addEventListener('touchmove', onPointerMove, { passive: true })
  window.addEventListener('touchend', onPointerUp)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onPointerMove)
  window.removeEventListener('mouseup', onPointerUp)
  window.removeEventListener('touchmove', onPointerMove)
  window.removeEventListener('touchend', onPointerUp)
})

defineExpose({ reset })
</script>

<template>
  <div
    class="slide-verify"
    :style="{ width: trackW + 'px', height: trackH + 'px' }"
    ref="railRef"
  >
    <!-- 目标缺口标记（一条竖线） -->
    <span
      class="target-mark"
      :style="{ left: targetX + 'px', opacity: state === 'success' ? 0 : 0.35 }"
      aria-hidden="true"
    />

    <!-- 背景轨道文字 -->
    <span class="track-text" :class="{ dim: state === 'sliding' || state === 'success' }">
      <template v-if="state === 'success'">验证通过</template>
      <template v-else>按住滑块，拖到虚线位置</template>
    </span>

    <!-- 进度高亮条 -->
    <div
      class="track-fill"
      :class="{ ok: state === 'success' }"
      :style="{ width: (progress + thumbW / 2) + 'px' }"
    />

    <!-- 滑块 -->
    <div
      class="thumb"
      :class="{ ok: state === 'success', shake: state === 'fail' }"
      :style="{ transform: `translateX(${progress}px)` }"
      @mousedown="onPointerDown"
      @touchstart="onPointerDown"
    >
      <svg v-if="state !== 'success'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
      <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.slide-verify {
  position: relative;
  user-select: none;
  border-radius: 20px;
  background: #f1f3f5;
  overflow: hidden;
  border: 1px solid var(--line-2);
  transition: border-color 0.18s var(--ease);
}
.track-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12.5px;
  color: var(--ink-4);
  transition: opacity 0.2s var(--ease);
}
.track-text.dim {
  opacity: 0.3;
}
.target-mark {
  position: absolute;
  top: 4px;
  bottom: 4px;
  width: 2px;
  border-radius: 1px;
  background: var(--brand);
  transition: opacity 0.3s var(--ease);
}
.track-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: rgba(44, 95, 82, 0.08);
  border-radius: 20px;
  transition: width 0.05s linear, background 0.3s var(--ease);
}
.track-fill.ok {
  background: rgba(44, 95, 82, 0.14);
}
.thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 36px;
  height: calc(100% - 4px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.04);
  color: var(--ink-3);
  cursor: grab;
  transition: color 0.2s var(--ease), box-shadow 0.2s var(--ease);
  will-change: transform;
}
.thumb:active {
  cursor: grabbing;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.12);
}
.thumb.ok {
  color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand);
}
@keyframes shakeThumb {
  0%, 100% { transform: translateX(var(--x, 0)); }
  25% { transform: translateX(calc(var(--x, 0) - 6px)); }
  75% { transform: translateX(calc(var(--x, 0) + 6px)); }
}
.thumb.shake {
  animation: shakeThumb 0.3s var(--ease);
}
</style>
