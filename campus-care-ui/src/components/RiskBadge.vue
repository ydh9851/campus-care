<script setup>
import { computed } from 'vue'
import { RISK_LABEL } from '../format'

const props = defineProps({
  level: { type: String, default: 'LOW' },
})

const cls = computed(() => `badge-${(props.level || 'LOW').toLowerCase()}`)
const text = computed(() => RISK_LABEL[props.level] || props.level)
</script>

<template>
  <span class="badge" :class="cls">{{ text }}</span>
</template>

<style scoped>
/* 小方标签，不用胶囊形 —— 方角看起来更像「系统里的字段」，而不是 UI 装饰 */
.badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1;
  font-weight: 500;
  white-space: nowrap;
}

.badge-high {
  color: var(--high);
  background: var(--high-bg);
}
.badge-medium {
  color: var(--med);
  background: var(--med-bg);
}
.badge-low {
  color: var(--low);
  background: var(--low-bg);
}
</style>
