<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dashboardApi } from '../api'
import AppIcon from '../components/AppIcon.vue'
import CountUp from '../components/CountUp.vue'
import EChart from '../components/EChart.vue'
import RiskBadge from '../components/RiskBadge.vue'
import { RISK_LABEL, shortTime } from '../format'
import { C, catAxis, legend, niceMax, tooltip, valAxis } from '../chartTheme'

const router = useRouter()
const data = ref(null)
const loading = ref(false)
const days = ref(14)
const RANGES = [7, 14, 30]

async function load() {
  loading.value = true
  try {
    data.value = await dashboardApi.get(days.value)
  } catch (e) {
    ElMessage.error(e.message)
    data.value = null
  } finally {
    loading.value = false
  }
}

function switchRange(d) {
  if (days.value === d) return
  days.value = d
  load()
}

function goProfile(userId) {
  if (userId) router.push({ name: 'profile', params: { userId } })
}

onMounted(load)

/* ---------------- 数字卡 ---------------- */
const s = computed(() => data.value?.summary || {})

const cards = computed(() => [
  { label: '累计工单', value: s.value.totalCount ?? 0, icon: 'clipboard' },
  { label: '高危工单', value: s.value.highCount ?? 0, tone: 'high', icon: 'alert' },
  { label: '待处理', value: s.value.pendingCount ?? 0, tone: 'med', icon: 'clock' },
  { label: '涉及学生', value: s.value.studentCount ?? 0, icon: 'user' },
  // 后缀和数值分开给：CountUp 只补间数字，'%' 不跟着跳
  { label: '高危占比', value: s.value.highRatio ?? 0, suffix: '%', icon: 'trend' },
])

/* ---------------- 图 1：风险等级环形 ---------------- */
const donutOption = computed(() => {
  const list = data.value?.riskDistribution || []
  const total = list.reduce((sum, item) => sum + (item.value || 0), 0)
  return {
    tooltip: { ...tooltip, trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
    title: {
      text: String(total),
      subtext: '工单总数',
      left: 'center',
      top: '39%',
      textStyle: { fontSize: 26, fontWeight: 500, color: C.ink, fontFamily: 'monospace' },
      subtextStyle: { fontSize: 11, color: C.ink3 },
    },
    series: [
      {
        type: 'pie',
        radius: ['64%', '86%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderColor: C.white, borderWidth: 2 },
        data: list.map((item) => ({
          name: RISK_LABEL[item.name] || item.name,
          value: item.value,
          itemStyle: { color: item.name === 'HIGH' ? C.high : C.med },
        })),
      },
    ],
  }
})

/* ---------------- 图 2：近 N 天趋势 ---------------- */
const trendOption = computed(() => {
  const list = data.value?.trend || []
  return {
    tooltip: { ...tooltip, trigger: 'axis' },
    legend: { ...legend, right: 0, top: 0, data: ['工单总数', '其中高危'] },
    grid: { left: 4, right: 8, top: 34, bottom: 2, containLabel: true },
    // boundaryGap:false 让折线从 y 轴贴边开始，避免左端留一段空隙
    xAxis: { ...catAxis, boundaryGap: false, data: list.map((p) => p.day.slice(5)) },
    yAxis: { ...valAxis, max: niceMax(list.map((p) => p.total)) },
    series: [
      {
        // smooth:false —— 折线不做圆滑处理。曲线会把「9 号 2 条、10 号 0 条」
        // 画成一条柔和的弧，视觉上像是在缓慢下降，实际上中间是断崖。
        name: '工单总数',
        type: 'line',
        symbol: 'circle',
        symbolSize: 5,
        data: list.map((p) => p.total),
        lineStyle: { width: 1.6, color: C.brand },
        itemStyle: { color: C.brand },
        areaStyle: { color: 'rgba(44,95,82,0.06)' },
      },
      {
        name: '其中高危',
        type: 'line',
        symbol: 'circle',
        symbolSize: 5,
        data: list.map((p) => p.high),
        lineStyle: { width: 1.6, color: C.high },
        itemStyle: { color: C.high },
      },
    ],
  }
})

/* ---------------- 图 3：24 小时时段分布 ---------------- */
const hourOption = computed(() => {
  const list = data.value?.hours || []
  const peak = data.value?.peakWindow
  // 窗口可能跨 0 点（如 22 → 01），所以用取模判断，不能直接比大小
  const inPeak = (hour) => {
    if (!peak || !peak.available) return false
    for (let i = 0; i < 3; i += 1) {
      if ((peak.startHour + i) % 24 === hour) return true
    }
    return false
  }
  return {
    tooltip: {
      ...tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(20,22,26,0.03)' } },
      formatter: (params) => `${params[0].axisValue}:00　${params[0].value} 条`,
    },
    grid: { left: 4, right: 8, top: 16, bottom: 2, containLabel: true },
    xAxis: {
      ...catAxis,
      axisLine: { show: false },
      axisLabel: { ...catAxis.axisLabel, fontSize: 10, interval: 1 },
      data: list.map((p) => String(p.hour).padStart(2, '0')),
    },
    yAxis: { ...valAxis, max: niceMax(list.map((p) => p.total)) },
    series: [
      {
        type: 'bar',
        barMaxWidth: 14,
        data: list.map((p) => ({
          value: p.total,
          itemStyle: {
            color: inPeak(p.hour) ? C.high : C.brandLine,
            borderRadius: [2, 2, 0, 0],
          },
        })),
      },
    ],
  }
})

/* ---------------- 图 4：工单来源（堆叠条） ---------------- */
const sourceOption = computed(() => {
  const list = data.value?.sourceDistribution || []
  const chat = list.find((x) => x.name === 'CHAT')?.value || 0
  const assess = list.find((x) => x.name === 'ASSESSMENT')?.value || 0
  // 数值为 0 的段不要显示标签，否则会出现「量表 0」这种噪音
  const seg = (name, color) => ({
    name,
    type: 'bar',
    stack: 's',
    barWidth: 30,
    itemStyle: { color },
    label: {
      show: true,
      color,
      fontSize: 11,
      formatter: (p) => (p.value > 0 ? `${name} ${p.value}` : ''),
    },
  })
  return {
    tooltip: { ...tooltip, trigger: 'item', formatter: '{a}：{c} 条' },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'value', show: false, max: chat + assess || 1 },
    yAxis: { type: 'category', show: false, data: [''] },
    series: [
      {
        ...seg('对话预警', C.brand),
        data: [chat],
        label: { ...seg('对话预警', C.brand).label, color: '#fff' },
      },
      {
        ...seg('量表预警', C.ink4),
        data: [assess],
        itemStyle: { color: C.ink4, borderRadius: [0, 4, 4, 0] },
        label: { ...seg('量表预警', C.ink4).label, color: C.ink2 },
      },
    ],
  }
})

const topStudents = computed(() => data.value?.topStudents || [])
const insights = computed(() => data.value?.insights || [])
</script>

<template>
  <div class="dash">
    <div v-if="loading && !data" class="empty">加载中…</div>
    <div v-else-if="!data" class="empty">没有拿到看板数据</div>

    <template v-else>
      <!-- ---------- 头部 ---------- -->
      <div class="head">
        <div>
          <div class="sec-head">
            <span class="chip sm"><AppIcon name="dashboard" :size="14" /></span>
            <span class="caption">辅导员工作台</span>
          </div>
          <h1>风险态势看板</h1>
        </div>
        <div class="head-right">
          <div class="seg">
            <button
              v-for="r in RANGES"
              :key="r"
              type="button"
              class="seg-btn"
              :class="{ on: days === r }"
              @click="switchRange(r)"
            >
              {{ r }} 天
            </button>
          </div>
          <button type="button" class="ghost" :disabled="loading" @click="load">
            {{ loading ? '刷新中…' : '刷新' }}
          </button>
        </div>
      </div>

      <!-- ---------- 数字卡 ---------- -->
      <div class="stats">
        <div
          v-for="(c, i) in cards"
          :key="c.label"
          v-spotlight
          v-reveal="i"
          class="stat-card"
          :class="[c.tone || '', c.tone ? 'tinted' : '']"
        >
          <span class="chip sm" :class="c.tone || ''">
            <AppIcon :name="c.icon" :size="15" />
          </span>
          <b class="num"><CountUp :value="c.value" :suffix="c.suffix || ''" /></b>
          <span class="st-l">{{ c.label }}</span>
        </div>
      </div>

      <!-- ---------- 结论 ----------
           看板不能只给图。辅导员要的是「我该先看谁」，
           所以把系统算出来的判断直接摆在图和数字前面。 -->
      <div v-reveal class="panel insights">
        <div class="sec-head">
          <span class="chip sm"><AppIcon name="sparkles" :size="14" /></span>
          <span class="caption">结论</span>
        </div>
        <ul>
          <li v-for="(text, i) in insights" :key="i">{{ text }}</li>
        </ul>
      </div>

      <!-- ---------- 图区 ---------- -->
      <div class="grid-2">
        <div v-reveal class="panel block wide">
          <div class="block-head">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="trend" :size="14" /></span>
              <span class="caption">近 {{ days }} 天工单趋势</span>
            </div>
            <span class="hint">按天聚合，空白日已补零</span>
          </div>
          <EChart :option="trendOption" height="230px" />
        </div>

        <div v-reveal="1" class="panel block">
          <div class="block-head">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="dashboard" :size="14" /></span>
              <span class="caption">风险等级分布</span>
            </div>
          </div>
          <EChart :option="donutOption" height="230px" />
        </div>
      </div>

      <div class="grid-2">
        <div v-reveal class="panel block wide">
          <div class="block-head">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="clock" :size="14" /></span>
              <span class="caption">24 小时时段分布</span>
            </div>
            <span class="hint">
              <template v-if="data.peakWindow?.available">
                深色为高峰窗口 {{ String(data.peakWindow.startHour).padStart(2, '0') }}:00–{{
                  String(data.peakWindow.endHour).padStart(2, '0')
                }}:00，共 {{ data.peakWindow.count }} 条（占 {{ data.peakWindow.ratio }}%）
              </template>
              <template v-else>样本不足，暂不判断高峰窗口</template>
            </span>
          </div>
          <EChart :option="hourOption" height="190px" />
        </div>

        <div v-reveal="1" class="panel block">
          <div class="block-head">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="clipboard" :size="14" /></span>
              <span class="caption">工单来源构成</span>
            </div>
          </div>
          <div class="source-wrap">
            <EChart :option="sourceOption" height="46px" />
            <p class="source-note">
              对话预警由 AI 从自然语言推测，偏「召回」；量表预警按标准计分得出，偏「精确」。
              两者共用同一个工单池，辅导员不必在两个页面之间切换。
            </p>
            <div class="handle-row">
              <div>
                <span class="caption">已处置</span>
                <b class="num">{{ data.handle?.handledCount ?? 0 }}</b>
              </div>
              <div>
                <span class="caption">平均处置时长</span>
                <b class="num">
                  {{ data.handle?.avgMinutes != null ? `${data.handle.avgMinutes} 分` : '—' }}
                </b>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ---------- 重点学生 ---------- -->
      <div v-reveal class="panel block">
        <div class="block-head">
          <div class="sec-head">
            <span class="chip sm"><AppIcon name="user" :size="14" /></span>
            <span class="caption">重点学生</span>
          </div>
          <span class="hint">按高危工单数排序，点击进入完整档案</span>
        </div>
        <div v-if="!topStudents.length" class="empty" style="height: 80px">暂无数据</div>
        <div v-else class="stu">
          <div
            v-for="stu in topStudents"
            :key="stu.userId"
            class="stu-row"
            role="button"
            tabindex="0"
            @click="goProfile(stu.userId)"
            @keydown.enter="goProfile(stu.userId)"
          >
            <span class="stu-name">
              {{ stu.realName || '未命名' }}
              <span v-if="stu.studentNo" class="stu-no num">{{ stu.studentNo }}</span>
            </span>
            <RiskBadge :level="stu.riskLevel" />
            <span class="stu-metric">
              <b class="num">{{ stu.highCount }}</b> 高危 / <b class="num">{{ stu.alertCount }}</b> 总单
            </span>
            <span class="stu-pending" :class="{ zero: stu.pendingCount === 0 }">
              待处理 {{ stu.pendingCount }}
            </span>
            <span class="num stu-time">{{ shortTime(stu.lastTime) }}</span>
            <AppIcon name="arrow" :size="15" class="stu-go" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dash {
  height: 100%;
  overflow-y: auto;
  /* 超宽屏收窄内容，但滚动条仍贴窗口右缘（用 max-width 会把它顶到屏幕中间） */
  padding: 28px max(32px, calc((100% - 1340px) / 2)) 48px;
}

/* ---------- 头部 ---------- */
.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.head h1 {
  margin-top: 8px;
  font-size: var(--t-page);
  font-weight: 600;
  letter-spacing: -0.03em;
  /* 大标题走品牌墨绿渐变：纯黑压在浅底上"太硬"，
     字尾收在品牌色上，整页的色感才是统一的 */
  background: linear-gradient(112deg, #12332c 0%, #2c5f52 70%, #3d7d6b 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  width: fit-content;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 分段控件：比 el-radio-group 更轻，也更好控制配色 */
.seg {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--panel);
}

.seg-btn {
  border: none;
  background: none;
  padding: 5px 12px;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
}

.seg-btn + .seg-btn {
  border-left: 1px solid var(--line);
}

.seg-btn.on {
  background: var(--brand-bg);
  color: var(--brand);
}

.ghost {
  padding: 6px 14px;
  font-size: 12.5px;
  color: var(--ink-2);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
}

.ghost:hover:not(:disabled) {
  border-color: var(--line-2);
  color: var(--ink);
}

.ghost:disabled {
  color: var(--ink-4);
  cursor: default;
}

/* ---------- 数字卡 ---------- */
.stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-top: 22px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.stat-card b {
  font-size: 23px;
  font-weight: 500;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.stat-card.high b {
  color: var(--high);
}
.stat-card.med b {
  color: var(--med);
}

.st-l {
  font-size: 12px;
  color: var(--ink-3);
}

/* ---------- 结论 ---------- */
.insights {
  margin-top: 14px;
  padding: 15px 18px 16px;
}

.insights ul {
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
}

.insights li {
  position: relative;
  padding: 3px 0 3px 15px;
  font-size: 13px;
  line-height: 1.75;
  color: var(--ink-2);
}

/* 用一个小方块做项目符号，比圆点更像「系统输出」 */
.insights li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 11px;
  width: 4px;
  height: 4px;
  background: var(--brand);
  border-radius: 1px;
}

/* ---------- 图区 ---------- */
.grid-2 {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr);
  gap: 14px;
  margin-top: 14px;
}

.block {
  padding: 16px 18px 14px;
}

.block-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.block-head .hint {
  font-size: 12px;
  text-align: right;
}

/* ---------- 来源块 ---------- */
.source-wrap {
  padding-top: 10px;
}

.source-note {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-3);
}

.handle-row {
  display: flex;
  gap: 34px;
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px solid var(--line);
}

.handle-row b {
  display: block;
  margin-top: 3px;
  font-size: 17px;
  font-weight: 500;
  color: var(--ink);
}

/* ---------- 重点学生 ---------- */
.stu {
  margin-top: 4px;
}

.stu-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px;
  margin: 0 -10px;
  border-top: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  transition:
    background-color 0.2s var(--ease),
    box-shadow 0.2s var(--ease);
}

.stu-row:first-child {
  border-top: none;
}

/* 悬停时左侧长出一条品牌色内影，代替"整行变灰"。
   整行变色在浅色表里很吵，一条竖线既安静又能指出"你正停在这一行"。 */
.stu-row:hover {
  background: var(--panel-2);
  box-shadow: inset 2px 0 0 var(--brand);
}

.stu-go {
  color: var(--ink-4);
  transition:
    transform 0.22s var(--ease),
    color 0.22s var(--ease);
}

.stu-row:hover .stu-go {
  color: var(--brand);
  transform: translateX(3px);
}

.stu-name {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stu-no {
  margin-left: 6px;
  font-size: 11.5px;
  color: var(--ink-3);
}

.stu-metric {
  font-size: 12.5px;
  color: var(--ink-3);
  white-space: nowrap;
}

.stu-metric b {
  color: var(--ink-2);
}

.stu-pending {
  font-size: 12.5px;
  color: var(--med);
  white-space: nowrap;
}

.stu-pending.zero {
  color: var(--ink-4);
}

.stu-time {
  font-size: 11.5px;
  color: var(--ink-3);
  white-space: nowrap;
}

@media (max-width: 1180px) {
  .stats {
    grid-template-columns: repeat(3, 1fr);
  }
  .grid-2 {
    grid-template-columns: minmax(0, 1fr);
  }
  .stu-time {
    display: none;
  }
}
</style>
