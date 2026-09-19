<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { assessmentApi } from '../api'
import AppIcon from '../components/AppIcon.vue'
import RiskBadge from '../components/RiskBadge.vue'
import { shortTime } from '../format'

const step = ref('list') // list | quiz | result
const scales = ref([])
const records = ref([])
const detail = ref(null)
const answers = ref([])
const result = ref(null)
const loading = ref(false)
const submitting = ref(false)

const answeredCount = computed(() => answers.value.filter((v) => v >= 0).length)
const totalQuestions = computed(() => detail.value?.questions?.length || 0)
const remaining = computed(() => totalQuestions.value - answeredCount.value)
const allAnswered = computed(() => totalQuestions.value > 0 && remaining.value === 0)
const progress = computed(() =>
  totalQuestions.value ? Math.round((answeredCount.value / totalQuestions.value) * 100) : 0
)

const scorePercent = computed(() => {
  if (!result.value) return 0
  const max = result.value.maxScore || 1
  return Math.min(100, Math.round(((result.value.record.totalScore || 0) / max) * 100))
})

function toneOf(level) {
  if (level === 'HIGH') return 'bad'
  if (level === 'MEDIUM') return 'mid'
  return 'ok'
}

async function loadList() {
  loading.value = true
  try {
    const [s, r] = await Promise.all([assessmentApi.scales(), assessmentApi.records()])
    scales.value = s || []
    records.value = r || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function start(code) {
  loading.value = true
  try {
    detail.value = await assessmentApi.scale(code)
    // -1 表示还没作答；不用 0 是因为 0 本身是一个合法选项
    answers.value = detail.value.questions.map(() => -1)
    step.value = 'quiz'
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function pick(index, value) {
  answers.value[index] = value
}

async function submit() {
  if (!allAnswered.value || submitting.value) return
  submitting.value = true
  try {
    result.value = await assessmentApi.submit(detail.value.code, answers.value)
    step.value = 'result'
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

function backToList() {
  step.value = 'list'
  detail.value = null
  result.value = null
  loadList()
}

function lastRecordOf(code) {
  return records.value.find((r) => r.scaleCode === code)
}

onMounted(loadList)
</script>

<template>
  <div class="assessment">
    <!-- ============ 列表 ============ -->
    <template v-if="step === 'list'">
      <div class="page-head">
        <div>
          <div class="sec-head">
            <span class="chip sm"><AppIcon name="clipboard" :size="14" /></span>
            <span class="caption">心理测评</span>
          </div>
          <h1>标准量表自评</h1>
        </div>
        <span class="hint">结果仅用于心理健康状态初筛，不构成医学诊断</span>
      </div>

      <div class="scale-grid">
        <button
          v-for="(s, i) in scales"
          :key="s.code"
          v-spotlight
          v-reveal="i"
          type="button"
          class="scale-card tile"
          @click="start(s.code)"
        >
          <span class="s-top">
            <span class="chip"><AppIcon name="clipboard" :size="17" /></span>
            <span class="s-name">{{ s.name }}</span>
          </span>
          <span class="s-intro">{{ s.intro }}</span>

          <span class="s-meta">
            <span class="num">{{ s.questionCount }} 题</span>
            <span class="meta-sep">·</span>
            <span>约 {{ Math.max(1, Math.round(s.questionCount * 0.3)) }} 分钟</span>
          </span>

          <span class="s-foot">
            <template v-if="lastRecordOf(s.code)">
              <span class="caption">上次结果</span>
              <span class="s-last">{{ lastRecordOf(s.code).severityLabel }}</span>
              <b class="num" :class="toneOf(lastRecordOf(s.code).riskLevel)">
                {{ lastRecordOf(s.code).totalScore }}
              </b>
              <span class="num dim">/{{ s.maxScore }}</span>
            </template>
            <template v-else>
              <span class="caption">尚未测评</span>
            </template>
          </span>
        </button>
      </div>

      <div class="section">
        <span class="caption">我的测评记录</span>
        <div v-if="!records.length" class="empty" style="height: 96px">还没有测评记录</div>
        <div v-else class="rec-list">
          <div v-for="r in records" :key="r.id" class="rec">
            <span class="rec-name">{{ r.scaleName }}</span>
            <RiskBadge :level="r.riskLevel" />
            <span class="rec-sev">{{ r.severityLabel }}</span>
            <span class="num rec-score">{{ r.totalScore }} 分</span>
            <span class="num rec-time">{{ shortTime(r.createTime) }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- ============ 答题 ============ -->
    <template v-else-if="step === 'quiz'">
      <div class="quiz-head">
        <button type="button" class="link-btn" @click="backToList">返回</button>
        <div class="quiz-title">
          <h1>{{ detail.name }}</h1>
          <span class="hint">{{ detail.intro }}</span>
        </div>
        <span class="num quiz-count">{{ answeredCount }} / {{ totalQuestions }}</span>
      </div>

      <div class="progress"><span :style="{ width: progress + '%' }"></span></div>

      <ol class="questions">
        <li v-for="(q, i) in detail.questions" :key="q.no" class="q">
          <div class="q-text">
            <span class="num q-no">{{ String(q.no).padStart(2, '0') }}</span>
            <span class="q-label">{{ q.text }}</span>
            <span v-if="q.critical" class="q-flag">重点关注</span>
          </div>
          <div class="opts">
            <button
              v-for="o in detail.options"
              :key="o.value"
              type="button"
              class="opt"
              :class="{ on: answers[i] === o.value }"
              @click="pick(i, o.value)"
            >
              {{ o.label }}
            </button>
          </div>
        </li>
      </ol>

      <div class="quiz-foot">
        <span class="hint">{{ detail.note }}</span>
        <button class="primary" :disabled="!allAnswered || submitting" @click="submit">
          {{ submitting ? '计分中…' : allAnswered ? '提交并查看结果' : `还有 ${remaining} 题未作答` }}
        </button>
      </div>
    </template>

    <!-- ============ 结果 ============ -->
    <template v-else>
      <div class="page-head">
        <div>
          <div class="sec-head">
            <span class="chip sm"><AppIcon name="trend" :size="14" /></span>
            <span class="caption">测评结果</span>
          </div>
          <h1>{{ result.record.scaleName }}</h1>
        </div>
        <button type="button" class="ghost-btn" @click="backToList">返回量表列表</button>
      </div>

      <div class="panel result-card">
        <div class="score-row">
          <div class="score-main">
            <span class="num score-big" :class="toneOf(result.record.riskLevel)">
              {{ result.record.totalScore }}
            </span>
            <span class="num score-max">/ {{ result.maxScore }}</span>
          </div>

          <div class="score-info">
            <div class="sev-row">
              <span class="sev-label">{{ result.record.severityLabel }}</span>
              <RiskBadge :level="result.record.riskLevel" />
            </div>
            <div class="bar">
              <div
                class="bar-fill"
                :class="toneOf(result.record.riskLevel)"
                :style="{ width: scorePercent + '%' }"
              ></div>
            </div>
            <span class="hint">得分越高表示近两周的困扰越明显</span>
          </div>
        </div>

        <div v-if="result.record.highRiskItems" class="critical-note">
          第 {{ result.record.highRiskItems }} 题的作答涉及自伤念头，已按最高等级处理
        </div>
      </div>

      <div class="panel pad">
        <span class="caption">处置建议</span>
        <p class="suggestion">{{ result.suggestion }}</p>
      </div>

      <div
        v-if="result.alertId"
        class="notice"
        :class="result.record.riskLevel === 'HIGH' ? 'notice-high' : 'notice-med'"
      >
        <span>
          本次结果已生成风险工单 <b class="num">#{{ result.alertId }}</b>，辅导员会尽快跟进
        </span>
      </div>
      <div v-else class="notice notice-plain">
        <span>本次结果未达到预警门槛，可自行查看记录</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.assessment {
  height: 100%;
  overflow-y: auto;
  /* 超宽屏收窄内容，但滚动条仍贴窗口右缘（用 max-width 会把它顶到屏幕中间） */
  padding: 28px max(32px, calc((100% - 1340px) / 2)) 48px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.page-head h1 {
  margin-top: 8px;
  font-size: var(--t-page);
  font-weight: 600;
  letter-spacing: -0.03em;
  /* 大标题走品牌墨绿渐变：纯黑压在浅底上"太硬"，
     字尾收在品牌色上，整页的色感才统一 */
  background: linear-gradient(112deg, #12332c 0%, #2c5f52 70%, #3d7d6b 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  width: fit-content;
}

.meta-sep {
  color: var(--ink-4);
}

.ghost-btn {
  border: 1px solid var(--line-2);
  background: var(--panel);
  border-radius: var(--radius);
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
}

.ghost-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
}

.link-btn {
  border: none;
  background: none;
  padding: 0;
  font-size: 13px;
  color: var(--brand);
  cursor: pointer;
}

/* ---------- 量表卡片 ---------- */
.scale-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
  margin-top: 22px;
}

.scale-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 9px;
  padding: 18px 18px 16px;
  text-align: left;
  background: var(--panel-grad);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 2px rgba(20, 22, 26, 0.025);
  cursor: pointer;
  /* 抬起、染色、描边光晕、图标块翻实心 —— 统一交给全局的 .tile */
}

/* 图标块 + 量表名同行，量表名才不会被图标块挤成两行 */
.s-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.s-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--ink);
}

.s-intro {
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-3);
  min-height: 42px;
}

.s-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-3);
}

.s-foot {
  display: flex;
  align-items: baseline;
  gap: 7px;
  margin-top: 6px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.s-last {
  font-size: 13px;
  color: var(--ink-2);
}

.s-foot b {
  font-size: 17px;
  font-weight: 500;
  line-height: 1;
}

.s-foot .dim {
  font-size: 12px;
  color: var(--ink-4);
}

.tone-ok,
.ok {
  color: var(--brand);
}
.mid {
  color: var(--med);
}
.bad {
  color: var(--high);
}

/* ---------- 记录 ---------- */
.section {
  margin-top: 34px;
}

.rec-list {
  margin-top: 12px;
  background: var(--panel-grad);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(20, 22, 26, 0.025);
}

.rec {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 16px;
  font-size: 13px;
  border-bottom: 1px solid var(--line);
  transition:
    background-color 0.18s var(--ease),
    box-shadow 0.18s var(--ease);
}

/* 左侧一条品牌色内影，代替整行变色 —— 和历史记录那种浅色表更配 */
.rec:hover {
  background: var(--panel-2);
  box-shadow: inset 2px 0 0 var(--brand);
}

.rec:last-child {
  border-bottom: none;
}

.rec-name {
  min-width: 180px;
  color: var(--ink);
}

.rec-sev {
  color: var(--ink-2);
}

.rec-score {
  color: var(--ink-2);
}

.rec-time {
  margin-left: auto;
  color: var(--ink-3);
  font-size: 12.5px;
}

/* ---------- 答题 ---------- */
.quiz-head {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.quiz-title {
  flex: 1;
}

.quiz-title h1 {
  font-size: 18px;
  font-weight: 500;
}

.quiz-title .hint {
  display: block;
  margin-top: 4px;
  line-height: 1.7;
}

.quiz-count {
  font-size: 13px;
  color: var(--ink-3);
  padding-top: 4px;
}

.progress {
  height: 3px;
  margin: 18px 0 26px;
  background: var(--line);
  border-radius: 2px;
  overflow: hidden;
}

.progress span {
  display: block;
  height: 100%;
  background: var(--brand-grad);
  border-radius: 2px;
  transition: width 0.3s var(--ease-out);
}

.questions {
  margin: 0;
  padding: 0;
  list-style: none;
}

.q {
  padding: 18px 0;
  border-bottom: 1px solid var(--line);
}

.q:first-child {
  padding-top: 0;
}

.q-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.q-no {
  font-size: 12px;
  color: var(--ink-4);
}

.q-label {
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink);
}

/* 高危题加一个轻标记，提醒学生这题会被单独关注 —— 不做视觉惊吓，只做提示 */
.q-flag {
  flex: none;
  font-size: 11px;
  color: var(--med);
  background: var(--med-bg);
  border-radius: 3px;
  padding: 1px 6px;
}

.opts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 24px;
}

.opt {
  border: 1px solid var(--line-2);
  background: var(--panel);
  border-radius: var(--radius);
  padding: 6px 14px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  transition:
    transform 0.16s var(--ease),
    border-color 0.16s var(--ease),
    color 0.16s var(--ease),
    background-color 0.16s var(--ease),
    box-shadow 0.16s var(--ease);
}

.opt:hover {
  transform: translateY(-1px);
  border-color: var(--brand-line);
  background: var(--brand-soft);
  color: var(--brand);
}

/* 选中态带一点品牌色光晕：答题时"有没有点中"必须一眼可辨 */
.opt.on {
  background: var(--brand-grad);
  border-color: transparent;
  color: #fff;
  box-shadow: var(--glow);
}

.quiz-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-top: 26px;
}

.primary {
  flex: none;
  height: 40px;
  padding: 0 24px;
  border: none;
  border-radius: var(--radius);
  background: var(--brand-grad);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--glow);
  transition:
    transform 0.18s var(--ease),
    filter 0.18s var(--ease),
    box-shadow 0.22s var(--ease);
}

.primary:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.06);
  box-shadow: var(--lift), var(--glow);
}

.primary:disabled {
  background: var(--line-2);
  cursor: default;
}

/* ---------- 结果 ---------- */
.result-card {
  position: relative;
  overflow: hidden;
  margin-top: 22px;
  padding: 24px;
  /* 右上角一团品牌光：分数卡是结果页的主角，值得比别的卡片多一层光 */
  background:
    radial-gradient(380px 200px at 102% -24%, rgba(44, 95, 82, 0.1) 0%, rgba(44, 95, 82, 0) 70%),
    var(--panel-grad);
}

.score-row {
  display: flex;
  align-items: center;
  gap: 28px;
}

.score-main {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex: none;
}

.score-big {
  font-size: 44px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.03em;
}

.score-max {
  font-size: 14px;
  color: var(--ink-3);
}

.score-info {
  flex: 1;
  min-width: 0;
}

.sev-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.sev-label {
  font-size: 15px;
  color: var(--ink);
}

.bar {
  height: 4px;
  background: var(--line);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.bar-fill {
  height: 100%;
  border-radius: 2px;
}

.bar-fill.ok {
  background: var(--brand);
}
.bar-fill.mid {
  background: var(--med);
}
.bar-fill.bad {
  background: var(--high);
}

.critical-note {
  margin-top: 20px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--high);
  background: var(--high-bg);
  border-radius: var(--radius);
}

.pad {
  margin-top: 14px;
  padding: 18px 20px;
}

.suggestion {
  margin-top: 10px;
  font-size: 13.5px;
  line-height: 1.85;
  color: var(--ink-2);
  white-space: pre-wrap;
}

.notice {
  margin-top: 14px;
  padding: 11px 16px;
  border-radius: var(--radius);
  font-size: 13px;
}

.notice-high {
  background: var(--high-bg);
  border: 1px solid #f0d8d4;
  color: var(--high);
}

.notice-med {
  background: var(--med-bg);
  border: 1px solid #efe2c8;
  color: var(--med);
}

.notice-plain {
  background: var(--panel-2);
  border: 1px solid var(--line);
  color: var(--ink-3);
}
</style>
