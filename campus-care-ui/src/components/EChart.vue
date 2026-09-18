<script setup>
/**
 * ECharts 的 Vue 封装。
 *
 * 三个容易踩的坑，都在这里一次性处理掉：
 *   1. 按需引入：只注册用到的图表类型和组件，打包体积从 ~1MB 降到 ~300KB；
 *   2. 尺寸变化：侧栏折叠、窗口缩放、抽屉打开都会改变容器宽度，
 *      不调 resize() 图表就会「挤在旧尺寸里」或者左边留一大块空白；
 *   3. 销毁：组件卸载时必须 dispose()，否则 ECharts 实例和它监听的窗口事件会泄漏，
 *      反复切页面会越用越卡。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '240px' },
})

const el = ref(null)
let chart = null
let observer = null

onMounted(() => {
  chart = echarts.init(el.value)
  chart.setOption(props.option)

  // ResizeObserver 比 window.resize 更准：能感知「父容器变宽但窗口没变」的情况
  observer = new ResizeObserver(() => chart && chart.resize())
  observer.observe(el.value)
})

watch(
  () => props.option,
  (opt) => {
    // 第二个参数 notMerge = true 很关键：
    // 当系列数量变化时（例如趋势从单条变成两条），
    // 默认的合并模式会把旧系列留在图上，出现「幽灵数据」。
    if (chart) chart.setOption(opt, true)
  },
  { deep: true },
)

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<template>
  <div ref="el" class="echart" :style="{ height }"></div>
</template>

<style scoped>
.echart {
  width: 100%;
}
</style>
