/**
 * ECharts 主题：把站点的 CSS 变量翻译成图表能用的常量。
 *
 * 为什么不直接用 ECharts 自带的 'light' 主题？
 * 自带主题的配色是「图表库默认配色」（蓝紫橙绿），和这个站点的墨绿 + 灰阶体系冲突，
 * 一眼就能看出「图是第三方库默认渲染的」。手工对齐的代价只有几十行。
 *
 * 阶段 3 的档案页情绪折线是手绘 SVG（单条折线不值得引 ECharts）；
 * 这里引入 ECharts 是因为需要环形图、双序列折线、堆叠条 —— 手绘成本开始不划算了。
 */
export const C = {
  brand: '#2c5f52',
  brandLine: '#cfe0da',
  high: '#a83a2f',
  med: '#96691d',
  low: '#6b7280',
  line: '#e7e7ea',
  ink: '#14161a',
  ink2: '#565b66',
  ink3: '#8a8f9a',
  ink4: '#b4b8c0',
  white: '#ffffff',
}

const FONT =
  '"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,sans-serif'
const MONO = 'ui-monospace,SFMono-Regular,Consolas,monospace'

/** 统一的 tooltip —— ECharts 默认的白底 + 黑阴影和站点风格冲突 */
export const tooltip = {
  backgroundColor: '#fff',
  borderColor: C.line,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: C.ink, fontSize: 12, fontFamily: FONT },
  extraCssText: 'box-shadow:0 6px 20px rgba(20,22,26,.08);border-radius:6px;',
}

/** 类目轴：去掉刻度，轴线只留一条淡线 */
export const catAxis = {
  type: 'category',
  axisTick: { show: false },
  axisLine: { lineStyle: { color: C.line } },
  axisLabel: { color: C.ink3, fontSize: 11, fontFamily: MONO },
}

/** 数值轴：干掉轴线，只留虚线分割线 —— 用最少的墨水表达刻度 */
export const valAxis = {
  type: 'value',
  minInterval: 1,
  axisTick: { show: false },
  axisLine: { show: false },
  axisLabel: { color: C.ink3, fontSize: 11, fontFamily: MONO },
  splitLine: { lineStyle: { color: C.line, type: [3, 3] } },
}

export const legend = {
  icon: 'roundRect',
  itemWidth: 8,
  itemHeight: 8,
  itemGap: 14,
  textStyle: { color: C.ink2, fontSize: 12, fontFamily: FONT },
}

/** 数字轴最大值至少给到 n，避免「只有 1 条工单」时柱子顶到天花板 */
export function niceMax(values) {
  const max = Math.max(0, ...values)
  return max <= 4 ? 4 : Math.ceil(max * 1.15)
}
