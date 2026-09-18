<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { riskApi } from '../api'
import RiskBadge from '../components/RiskBadge.vue'
import { shortTime } from '../format'

const router = useRouter()

/** 跳到该学生的心理档案 —— 工单和档案是一条闭环：看到风险 → 看完整画像 → 决定怎么干预 */
function goProfile(userId) {
  if (!userId) return
  router.push({ name: 'profile', params: { userId } })
}

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const stats = ref({})
const query = reactive({ current: 1, size: 10, status: '', riskLevel: '' })

const STATUS_TABS = [
  { value: '', label: '全部' },
  { value: 'PENDING', label: '待处理' },
  { value: 'HANDLED', label: '已处理' },
]

const RISK_TABS = [
  { value: '', label: '全部风险' },
  { value: 'HIGH', label: '高危' },
  { value: 'MEDIUM', label: '关注' },
]

const cards = computed(() => [
  { key: 'pendingCount', label: '待处理', tone: 'brand' },
  { key: 'highCount', label: '高危', tone: 'high' },
  { key: 'mediumCount', label: '关注', tone: 'med' },
  { key: 'totalCount', label: '累计工单', tone: 'plain' },
])

function statNum(key) {
  // 后端的 SUM(CASE WHEN ...) 在没有数据时会返回 null
  return Number(stats.value?.[key] || 0)
}

async function load() {
  loading.value = true
  try {
    const page = await riskApi.page(query)
    rows.value = page?.records || []
    total.value = page?.total || 0
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = (await riskApi.statistics()) || {}
  } catch {
    stats.value = {}
  }
}

function switchTab(field, value) {
  query[field] = value
  query.current = 1
  load()
}

function onPage(p) {
  query.current = p
  load()
}

/* ---------------- 处置 ---------------- */
const drawer = reactive({ open: false, row: null, remark: '', submitting: false })

function openHandle(row) {
  drawer.row = row
  drawer.remark = ''
  drawer.open = true
}

async function submitHandle() {
  if (!drawer.remark.trim()) {
    ElMessage.warning('请填写处置备注')
    return
  }
  drawer.submitting = true
  try {
    await riskApi.handle(drawer.row.id, drawer.remark.trim())
    ElMessage.success('已标记为已处理')
    drawer.open = false
    await Promise.all([load(), loadStats()])
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    drawer.submitting = false
  }
}

onMounted(() => {
  load()
  loadStats()
})
</script>

<template>
  <div class="alerts">
    <div class="page-head">
      <div>
        <span class="caption">辅导员工作台</span>
        <h1>风险预警工单</h1>
      </div>
      <button type="button" class="ghost-btn" @click="load(); loadStats()">刷新</button>
    </div>

    <!-- 统计 -->
    <div class="stats">
      <div v-for="c in cards" :key="c.key" class="stat" :class="'tone-' + c.tone">
        <span class="caption">{{ c.label }}</span>
        <b class="num">{{ statNum(c.key) }}</b>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filters">
      <div class="seg">
        <button
          v-for="t in STATUS_TABS"
          :key="t.value"
          type="button"
          :class="{ on: query.status === t.value }"
          @click="switchTab('status', t.value)"
        >
          {{ t.label }}
        </button>
      </div>
      <div class="seg">
        <button
          v-for="t in RISK_TABS"
          :key="t.value"
          type="button"
          :class="{ on: query.riskLevel === t.value }"
          @click="switchTab('riskLevel', t.value)"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 表格 -->
    <div class="panel table-wrap">
      <el-table
        v-loading="loading"
        :data="rows"
        :row-class-name="({ row }) => 'row-' + String(row.riskLevel).toLowerCase()"
        style="width: 100%"
        size="default"
      >
        <el-table-column label="风险" width="86">
          <template #default="{ row }">
            <RiskBadge :level="row.riskLevel" />
          </template>
        </el-table-column>

        <!-- 来源：对话预警是 AI 从自然语言推测的（偏召回），
             量表预警是按标准计分算的（偏精确）。辅导员需要知道这条工单是怎么来的。 -->
        <el-table-column label="来源" width="80">
          <template #default="{ row }">
            <span class="source">{{ row.source === 'ASSESSMENT' ? '量表' : '对话' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="命中关键词" width="170">
          <template #default="{ row }">
            <span v-if="!row.keywords" class="dash">—</span>
            <span v-for="k in String(row.keywords).split(',')" :key="k" class="kw">{{ k }}</span>
          </template>
        </el-table-column>

        <el-table-column label="触发原文" min-width="240">
          <template #default="{ row }">
            <span class="quote">{{ row.content }}</span>
          </template>
        </el-table-column>

        <el-table-column label="时间" width="140">
          <template #default="{ row }">
            <span class="num time">{{ shortTime(row.createTime) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="92">
          <template #default="{ row }">
            <span class="status" :class="row.status === 'PENDING' ? 's-pending' : 's-done'">
              {{ row.status === 'PENDING' ? '待处理' : '已处理' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="118" align="right">
          <template #default="{ row }">
            <button type="button" class="link-btn" @click="goProfile(row.userId)">档案</button>
            <button
              type="button"
              class="link-btn"
              :disabled="row.status !== 'PENDING'"
              @click="openHandle(row)"
            >
              处置
            </button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="empty" style="padding: 40px 0">没有符合条件的预警工单</div>
        </template>
      </el-table>

      <div v-if="total > query.size" class="pager">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="query.size"
          :current-page="query.current"
          background
          @current-change="onPage"
        />
      </div>
    </div>

    <!-- 处置抽屉 -->
    <el-drawer v-model="drawer.open" :with-header="false" size="440px">
      <div v-if="drawer.row" class="drawer">
        <div class="drawer-head">
          <span class="caption">预警工单 #{{ drawer.row.id }}</span>
          <span class="head-right">
            <span class="source">{{ drawer.row.source === 'ASSESSMENT' ? '量表预警' : '对话预警' }}</span>
            <RiskBadge :level="drawer.row.riskLevel" />
          </span>
        </div>

        <div class="field">
          <span class="caption">触发原文</span>
          <blockquote>{{ drawer.row.content }}</blockquote>
        </div>

        <div class="field">
          <span class="caption">命中关键词</span>
          <div class="kw-row">
            <span v-for="k in String(drawer.row.keywords || '').split(',').filter(Boolean)" :key="k" class="kw">
              {{ k }}
            </span>
            <span v-if="!drawer.row.keywords" class="dash">—</span>
          </div>
        </div>

        <div class="field">
          <span class="caption">AI 处置建议</span>
          <p class="suggestion">{{ drawer.row.aiSuggestion || '—' }}</p>
        </div>

        <div class="field">
          <span class="caption">会话编号</span>
          <p class="num dim">#{{ drawer.row.conversationId }} · 学生 #{{ drawer.row.userId }}</p>
        </div>

        <template v-if="drawer.row.status === 'PENDING'">
          <div class="field">
            <span class="caption">处置备注</span>
            <textarea
              v-model="drawer.remark"
              rows="4"
              placeholder="例如：已电话联系学生，情绪稳定，约定周五面谈"
            ></textarea>
          </div>
          <button
            type="button"
            class="primary"
            :disabled="drawer.submitting"
            @click="submitHandle"
          >
            {{ drawer.submitting ? '提交中…' : '标记为已处理' }}
          </button>
        </template>

        <div v-else class="done-box">
          <span class="caption">已处理</span>
          <p>处置人 #{{ drawer.row.handlerId }}</p>
          <p>{{ drawer.row.handleRemark || '（未填写备注）' }}</p>
          <p class="num dim">{{ shortTime(drawer.row.handleTime) }}</p>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.alerts {
  height: 100%;
  overflow-y: auto;
  padding: 28px 32px 40px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.page-head h1 {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 500;
  letter-spacing: -0.01em;
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

/* ---------- 统计 ---------- */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 20px;
}

.stat {
  padding: 14px 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
}

.stat b {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  font-weight: 500;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.tone-brand b {
  color: var(--brand);
}
.tone-high b {
  color: var(--high);
}
.tone-med b {
  color: var(--med);
}
.tone-plain b {
  color: var(--ink);
}

/* ---------- 筛选 ---------- */
.filters {
  display: flex;
  gap: 12px;
  margin: 20px 0 12px;
}

/* 分段控件：比下拉框更直接，也少一次点击 */
.seg {
  display: inline-flex;
  padding: 2px;
  background: #ececee;
  border-radius: var(--radius);
}

.seg button {
  border: none;
  background: none;
  border-radius: 4px;
  padding: 5px 12px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
}

.seg button.on {
  background: var(--panel);
  color: var(--ink);
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(20, 22, 26, 0.06);
}

/* ---------- 表格 ---------- */
.table-wrap {
  overflow: hidden;
}

/* 高危行整体淡淡泛红，配合「高危排在首位」的排序，一眼就能定位 */
.table-wrap :deep(.el-table .row-high) {
  --el-table-tr-bg-color: #fdf7f6;
}

.table-wrap :deep(.el-table th.el-table__cell) {
  background: var(--panel-2);
  color: var(--ink-3);
  font-weight: 500;
  font-size: 12.5px;
}

.table-wrap :deep(.el-table td.el-table__cell) {
  border-bottom-color: var(--line);
}

.quote {
  font-size: 13px;
  color: var(--ink-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.time,
.dim {
  color: var(--ink-3);
  font-size: 12.5px;
}

.dash {
  color: var(--ink-4);
}

.kw,
.kw-row .kw {
  display: inline-block;
  margin: 0 6px 4px 0;
  padding: 1px 7px;
  font-size: 12px;
  color: var(--ink-2);
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 4px;
}

.status {
  font-size: 12.5px;
}

.s-pending {
  color: var(--med);
}

.s-done {
  color: var(--ink-3);
}

.link-btn {
  border: none;
  background: none;
  padding: 0;
  font-size: 13px;
  color: var(--brand);
  cursor: pointer;
}

.link-btn:disabled {
  color: var(--ink-4);
  cursor: default;
}

/* 两个文字按钮之间留出点击间距，避免误点 */
.link-btn + .link-btn {
  margin-left: 12px;
}

/* 来源标记：方角小标签，比胶囊更「系统字段」，也和 RiskBadge 风格统一 */
.source {
  font-size: 11.5px;
  color: var(--ink-3);
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 0 5px;
  white-space: nowrap;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
}

.pager :deep(.el-pagination.is-background .el-pager li) {
  border-radius: 4px;
}

/* ---------- 抽屉 ---------- */
.drawer {
  padding: 24px 24px 32px;
}

.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

.field {
  margin-top: 20px;
}

.field blockquote {
  margin: 8px 0 0;
  padding: 12px 14px;
  background: var(--panel-2);
  border-left: 2px solid var(--brand);
  border-radius: 0 var(--radius) var(--radius) 0;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink);
}

.field .suggestion {
  margin-top: 8px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink-2);
  white-space: pre-wrap;
}

.kw-row {
  margin-top: 8px;
}

.field textarea {
  width: 100%;
  margin-top: 8px;
  padding: 10px 12px;
  font-family: inherit;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--ink);
  border: 1px solid var(--line-2);
  border-radius: var(--radius);
  outline: none;
  resize: vertical;
}

.field textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-bg);
}

.primary {
  width: 100%;
  height: 40px;
  margin-top: 24px;
  border: none;
  border-radius: var(--radius);
  background: var(--brand);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.primary:hover:not(:disabled) {
  background: var(--brand-ink);
}

.primary:disabled {
  opacity: 0.6;
  cursor: default;
}

.done-box {
  margin-top: 20px;
  padding: 14px 16px;
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
}

.done-box p {
  margin-top: 6px;
  font-size: 13.5px;
  color: var(--ink-2);
}

@media (max-width: 900px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
