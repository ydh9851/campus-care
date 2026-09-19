<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { profileApi } from '../api'
import AppIcon from '../components/AppIcon.vue'
import CountUp from '../components/CountUp.vue'
import RiskBadge from '../components/RiskBadge.vue'
import { RISK_LABEL, shortTime } from '../format'

const route = useRoute()
const profile = ref(null)
const loading = ref(false)

/** 无 userId 参数 = 看自己的档案 */
const targetUserId = computed(() => (route.params.userId ? Number(route.params.userId) : null))
const isSelf = computed(() => targetUserId.value === null)

async function load() {
  loading.value = true
  try {
    profile.value = isSelf.value
      ? await profileApi.me()
      : await profileApi.user(targetUserId.value)
  } catch (e) {
    ElMessage.error(e.message)
    profile.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(targetUserId, load)

const o = computed(() => profile.value?.overview || {})
const basic = computed(() => profile.value?.basic || {})

const cards = computed(() => {
  const raw = [
    { label: '咨询会话', value: o.value.conversationCount, icon: 'chat' },
    { label: '累计轮次', value: o.value.totalTurns, icon: 'trend' },
    { label: '风险工单', value: o.value.alertCount, icon: 'alert' },
    { label: '待处理', value: o.value.pendingAlertCount, icon: 'clock', tone: 'brand' },
    { label: '高危工单', value: o.value.highAlertCount, icon: 'shield', tone: 'high' },
    { label: '测评次数', value: o.value.assessmentCount, icon: 'clipboard' },
  ]
  return raw.map((c) => {
    // 只有风险相关的那两张染底色。六张卡全染色 = 什么都强调 = 没有强调。
    const risky = c.tone === 'high' || c.tone === 'med'
    return { ...c, cardClass: risky ? [c.tone, 'tinted'] : '', chipClass: risky ? c.tone : '' }
  })
})

/* ---------------- 情绪趋势（手绘 SVG，不引图表库） ----------------
   为什么不用 ECharts？单条折线用 ECharts 要引入 1MB 的库 + 一层容器尺寸适配，
   收益却只是「一张很普通的折线」。这里用 40 行 SVG 画出来，
   线更细、点更小、字更淡 —— 反而更符合这个页面的克制基调。
   等阶段 4 的看板需要环形图 / 多序列柱状图时，再引 ECharts 才是划算的。
------------------------------------------------------------------ */
const trend = computed(() => {
  // reports 是倒序（新的在前），折线要按时间正序画
  return [...(profile.value?.reports || [])]
    .reverse()
    .map((r) => ({
      score: Number(r.emotionScore ?? 0),
      time: r.createTime,
      risk: r.riskLevel,
    }))
})

const CHART = { w: 640, h: 150, padX: 34, padTop: 16, padBottom: 26 }

const trendPoints = computed(() => {
  const list = trend.value
  if (list.length === 0) return []
  const { w, h, padX, padTop, padBottom } = CHART
  const usableW = w - padX * 2
  const usableH = h - padTop - padBottom
  const stepX = list.length === 1 ? 0 : usableW / (list.length - 1)
  return list.map((p, i) => ({
    ...p,
    x: list.length === 1 ? padX + usableW / 2 : padX + stepX * i,
    y: padTop + usableH * (1 - Math.max(0, Math.min(100, p.score)) / 100),
  }))
})

const trendLine = computed(() => trendPoints.value.map((p) => `${p.x},${p.y}`).join(' '))

/** 网格线只画 0 / 50 / 100 三条，够定位就行，画满 5 条太吵 */
const gridLines = computed(() => {
  const { w, h, padX, padTop, padBottom } = CHART
  const usableH = h - padTop - padBottom
  return [100, 50, 0].map((v) => ({
    value: v,
    y: padTop + usableH * (1 - v / 100),
    x1: padX,
    x2: w - padX,
  }))
})

function dotTone(risk) {
  if (risk === 'HIGH') return 'bad'
  if (risk === 'MEDIUM') return 'mid'
  return 'ok'
}

const TIMELINE_LABEL = { ALERT: '工单', ASSESSMENT: '测评', REPORT: '报告' }

const EVENT_TONE = {
  ASSESSMENT: 'brand',
  REPORT: 'muted',
}
function eventTone(item) {
  if (item.type === 'ALERT') return dotTone(item.riskLevel)
  return EVENT_TONE[item.type] || 'muted'
}
</script>

<template>
  <div class="profile">
    <div v-if="loading && !profile" class="empty">加载中…</div>
    <div v-else-if="!profile" class="empty">没有拿到档案数据</div>

    <template v-else>
      <!-- ---------- 头部 ---------- -->
      <div class="head">
        <div class="who">
          <div class="sec-head">
            <span class="chip sm"><AppIcon name="user" :size="14" /></span>
            <span class="caption">{{ isSelf ? '我的心理档案' : '学生心理档案' }}</span>
          </div>
          <h1>
            {{ basic.realName || basic.username }}
            <span v-if="basic.studentNo" class="no num">{{ basic.studentNo }}</span>
          </h1>
          <div class="meta">
            <RiskBadge :level="o.highestRiskLevel" />
            <span class="dim">综合最高风险</span>
            <span class="sep">·</span>
            <span class="dim">注册于 {{ shortTime(basic.registerTime) }}</span>
            <template v-if="o.lastActiveTime">
              <span class="sep">·</span>
              <span class="dim">最近活动 {{ shortTime(o.lastActiveTime) }}</span>
            </template>
          </div>
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
          :class="c.cardClass"
        >
          <span class="chip sm" :class="c.chipClass">
            <AppIcon :name="c.icon" :size="15" />
          </span>
          <b class="num" :class="c.tone || ''"><CountUp :value="c.value ?? 0" /></b>
          <span class="st-l">{{ c.label }}</span>
        </div>
      </div>

      <!-- ---------- 情绪趋势 ---------- -->
      <div v-reveal class="panel block">
        <div class="block-head">
          <div class="sec-head">
            <span class="chip sm"><AppIcon name="trend" :size="14" /></span>
            <span class="caption">情绪趋势</span>
          </div>
          <span class="hint">
            来自 {{ trend.length }} 份咨询报告，越高表示情绪越积极
            <template v-if="o.latestEmotionScore !== null && o.latestEmotionScore !== undefined">
              · 最近一次 <b class="num">{{ o.latestEmotionScore }}</b>
            </template>
          </span>
        </div>

        <div v-if="!trend.length" class="empty" style="height: 110px">
          还没有咨询报告，无法绘制趋势
        </div>
        <svg v-else class="chart" :viewBox="`0 0 ${CHART.w} ${CHART.h}`" preserveAspectRatio="none">
          <g>
            <line
              v-for="g in gridLines"
              :key="g.value"
              :x1="g.x1"
              :x2="g.x2"
              :y1="g.y"
              :y2="g.y"
              class="grid"
            />
            <text v-for="g in gridLines" :key="'t' + g.value" :x="4" :y="g.y + 3.5" class="axis">
              {{ g.value }}
            </text>
          </g>

          <polyline v-if="trendPoints.length > 1" :points="trendLine" class="line" />

          <g v-for="(p, i) in trendPoints" :key="i">
            <circle :cx="p.x" :cy="p.y" r="3.2" class="dot" :class="dotTone(p.risk)" />
            <title>{{ shortTime(p.time) }} · 情绪 {{ p.score }} · {{ RISK_LABEL[p.risk] }}</title>
          </g>
        </svg>
      </div>

      <!-- ---------- 两栏 ---------- -->
      <div class="cols">
        <!-- 左：时间线 -->
        <div v-reveal class="panel block">
          <div class="block-head">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="clock" :size="14" /></span>
              <span class="caption">事件时间线</span>
            </div>
            <span class="hint">最近 {{ profile.timeline.length }} 条</span>
          </div>

          <div v-if="!profile.timeline.length" class="empty" style="height: 110px">
            暂无事件记录
          </div>
          <ol v-else class="timeline">
            <li v-for="(item, i) in profile.timeline" :key="i" class="tl-item">
              <span class="tl-rail">
                <span class="tl-dot" :class="eventTone(item)"></span>
              </span>
              <div class="tl-body">
                <div class="tl-title">
                  <span class="tl-type">{{ TIMELINE_LABEL[item.type] || item.type }}</span>
                  <span class="tl-name">{{ item.title }}</span>
                  <RiskBadge v-if="item.riskLevel && item.riskLevel !== 'LOW'" :level="item.riskLevel" />
                  <span class="num tl-time">{{ shortTime(item.time) }}</span>
                </div>
                <p class="tl-detail">{{ item.detail || '—' }}</p>
              </div>
            </li>
          </ol>
        </div>

        <!-- 右：测评 + 工单 -->
        <div class="right-col">
          <div v-reveal class="panel block">
            <div class="block-head">
              <div class="sec-head">
                <span class="chip sm"><AppIcon name="clipboard" :size="14" /></span>
                <span class="caption">测评记录</span>
              </div>
              <span class="hint">{{ profile.assessments.length }} 次</span>
            </div>
            <div v-if="!profile.assessments.length" class="empty" style="height: 80px">尚未测评</div>
            <div v-else class="rows">
              <div v-for="a in profile.assessments" :key="a.id" class="row-item">
                <div class="row-main">
                  <span class="row-title">{{ a.scaleName }}</span>
                  <span class="row-sub">
                    {{ a.severityLabel }} · <b class="num">{{ a.totalScore }}</b> 分
                    <template v-if="a.highRiskItems"> · 第 {{ a.highRiskItems }} 题</template>
                  </span>
                </div>
                <RiskBadge :level="a.riskLevel" />
                <span class="num row-time">{{ shortTime(a.createTime) }}</span>
              </div>
            </div>
          </div>

          <div v-reveal="1" class="panel block">
            <div class="block-head">
              <div class="sec-head">
                <span class="chip sm"><AppIcon name="alert" :size="14" /></span>
                <span class="caption">风险工单</span>
              </div>
              <span class="hint">{{ profile.alerts.length }} 条</span>
            </div>
            <div v-if="!profile.alerts.length" class="empty" style="height: 80px">没有风险工单</div>
            <div v-else class="rows">
              <div v-for="a in profile.alerts" :key="a.id" class="row-item">
                <div class="row-main">
                  <span class="row-title">
                    {{ a.source === 'ASSESSMENT' ? '量表预警' : '对话预警' }}
                    <span class="num row-id">#{{ a.id }}</span>
                  </span>
                  <span class="row-sub">{{ a.keywords || '—' }}</span>
                </div>
                <RiskBadge :level="a.riskLevel" />
                <span class="row-status" :class="a.status === 'PENDING' ? 'pending' : 'done'">
                  {{ a.status === 'PENDING' ? '待处理' : '已处理' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.profile {
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

.who h1 {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-top: 8px;
  font-size: var(--t-page);
  font-weight: 600;
  letter-spacing: -0.03em;
  /* 这里不能用渐变文字：h1 里还装着徽章等子元素，
     background-clip: text 会把子元素一起变透明 */
  color: var(--brand-deep);
}

.no {
  font-size: 13px;
  font-weight: 400;
  color: var(--ink-3);
}

.meta {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 10px;
  font-size: 12.5px;
}

.dim {
  color: var(--ink-3);
}

.sep {
  color: var(--ink-4);
}

/* ---------- 数字卡 ---------- */
.stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-top: 22px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.stat-card b {
  font-size: 22px;
  font-weight: 500;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.stat-card.brand b {
  color: var(--brand);
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

/* ---------- 通用块 ---------- */
.block {
  margin-top: 14px;
  padding: 16px 18px 18px;
}

.block-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.block-head .hint b {
  color: var(--ink-2);
}

/* ---------- 折线图 ---------- */
.chart {
  width: 100%;
  height: 150px;
  display: block;
}

.grid {
  stroke: var(--line);
  stroke-width: 1;
}

.axis {
  font-size: 9px;
  fill: var(--ink-4);
  font-family: var(--mono);
}

.line {
  fill: none;
  stroke: var(--brand);
  stroke-width: 1.6;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.dot {
  fill: var(--panel);
  stroke-width: 1.8;
}

.dot.ok {
  stroke: var(--brand);
}
.dot.mid {
  stroke: var(--med);
}
.dot.bad {
  stroke: var(--high);
}

/* ---------- 两栏 ---------- */
.cols {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.right-col {
  display: flex;
  flex-direction: column;
}

/* ---------- 时间线 ---------- */
.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
}

.tl-item {
  display: flex;
  gap: 12px;
}

.tl-rail {
  position: relative;
  width: 8px;
  flex: none;
  display: flex;
  justify-content: center;
}

/* 竖线用伪元素画，最后一个 item 不再往下延伸 */
.tl-rail::before {
  content: '';
  position: absolute;
  top: 12px;
  bottom: -6px;
  width: 1px;
  background: var(--line);
}

.tl-item:last-child .tl-rail::before {
  display: none;
}

.tl-dot {
  position: relative;
  margin-top: 4px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-4);
}

.tl-dot.ok {
  background: var(--brand);
}
.tl-dot.mid {
  background: var(--med);
}
.tl-dot.bad {
  background: var(--high);
}
.tl-dot.brand {
  background: var(--brand);
}
.tl-dot.muted {
  background: var(--ink-4);
}

.tl-body {
  flex: 1;
  min-width: 0;
  padding-bottom: 14px;
}

.tl-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tl-type {
  font-size: 11px;
  color: var(--ink-3);
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 0 5px;
}

.tl-name {
  font-size: 13.5px;
  color: var(--ink);
}

.tl-time {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--ink-3);
}

.tl-detail {
  margin-top: 4px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-2);
}

/* ---------- 列表行 ---------- */
.rows {
  display: flex;
  flex-direction: column;
}

.row-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  margin: 0 -8px;
  border-top: 1px solid var(--line);
  border-radius: var(--radius);
  transition:
    background-color 0.18s var(--ease),
    box-shadow 0.18s var(--ease);
}

.row-item:first-child {
  border-top: none;
}

.row-item:hover {
  background: var(--panel-2);
  box-shadow: inset 2px 0 0 var(--brand);
}

.row-main {
  flex: 1;
  min-width: 0;
}

.row-title {
  display: block;
  font-size: 13px;
  color: var(--ink);
}

.row-id {
  color: var(--ink-4);
  font-size: 11.5px;
}

.row-sub {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-sub b {
  color: var(--ink-2);
}

.row-time {
  font-size: 11.5px;
  color: var(--ink-3);
}

.row-status {
  font-size: 12px;
  flex: none;
}

.row-status.pending {
  color: var(--med);
}

.row-status.done {
  color: var(--ink-3);
}

@media (max-width: 1080px) {
  .stats {
    grid-template-columns: repeat(3, 1fr);
  }
  .cols {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
