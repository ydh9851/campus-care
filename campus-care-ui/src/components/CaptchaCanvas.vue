<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  width: { type: Number, default: 100 },
  height: { type: Number, default: 38 },
})

const emit = defineEmits(['change'])

const canvasRef = ref(null)
const code = ref('')

const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefhjkmnpqrstuvwxyz2345678'

function randomColor(min, max) {
  return `rgb(${rand(min, max)},${rand(min, max)},${rand(min, max)})`
}
function rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function refresh() {
  const cvs = canvasRef.value
  if (!cvs) return
  const ctx = cvs.getContext('2d')
  const w = props.width
  const h = props.height

  ctx.fillStyle = '#f6f8fa'
  ctx.fillRect(0, 0, w, h)

  // 干扰线
  for (let i = 0; i < 4; i++) {
    ctx.strokeStyle = randomColor(160, 220)
    ctx.lineWidth = rand(1, 2)
    ctx.beginPath()
    ctx.moveTo(rand(0, w), rand(0, h))
    ctx.lineTo(rand(0, w), rand(0, h))
    ctx.stroke()
  }

  // 干扰点
  for (let i = 0; i < 20; i++) {
    ctx.fillStyle = randomColor(180, 230)
    ctx.beginPath()
    ctx.arc(rand(0, w), rand(0, h), rand(0.5, 1.5), 0, Math.PI * 2)
    ctx.fill()
  }

  let txt = ''
  const len = 4
  for (let i = 0; i < len; i++) {
    const ch = chars[rand(0, chars.length - 1)]
    txt += ch
    ctx.font = `${rand(18, 22)}px 'Segoe UI', sans-serif`
    ctx.fillStyle = randomColor(60, 120)
    ctx.textBaseline = 'middle'
    const x = (w / len) * i + rand(4, 10)
    const y = h / 2 + rand(-4, 4)
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate((rand(-25, 25) * Math.PI) / 180)
    ctx.fillText(ch, 0, 0)
    ctx.restore()
  }

  code.value = txt
  emit('change', txt)
}

onMounted(refresh)

watch(() => props.width, refresh)
watch(() => props.height, refresh)

defineExpose({ refresh, code })
</script>

<template>
  <div class="captcha-wrap" title="点击刷新验证码" @click="refresh">
    <canvas ref="canvasRef" :width="width" :height="height" />
    <span class="refresh-hint" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="23 4 23 10 17 10"></polyline>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
      </svg>
    </span>
  </div>
</template>

<style scoped>
.captcha-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--line-2);
  background: #f6f8fa;
  transition: border-color 0.18s var(--ease), box-shadow 0.18s var(--ease);
}
.captcha-wrap:hover {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(44, 95, 82, 0.08);
}
canvas {
  display: block;
}
.refresh-hint {
  position: absolute;
  right: 4px;
  bottom: 2px;
  color: var(--ink-4);
  opacity: 0;
  transition: opacity 0.2s var(--ease);
}
.captcha-wrap:hover .refresh-hint {
  opacity: 1;
}
</style>
