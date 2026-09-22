<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { chatApi, consultStream, reportApi } from '../api'
import AppIcon from '../components/AppIcon.vue'
import RiskBadge from '../components/RiskBadge.vue'
import { formatReply, hhmm, INTENT_LABEL, RISK_LABEL, shortTime } from '../format'

const conversations = ref([])
const messages = ref([])
const currentId = ref(null)
const draft = ref('')
const sending = ref(false)
const loadingList = ref(false)
const loadingMessages = ref(false)
const alertNotice = ref(null)
const threadEl = ref(null)

let liveTimer = null

const report = ref(null)
const reportVisible = ref(false)
const reportLoading = ref(false)

const current = computed(() => conversations.value.find((c) => c.id === currentId.value))

/* ---------------- 数据加载 ---------------- */
async function loadConversations() {
  loadingList.value = true
  try {
    conversations.value = (await chatApi.conversations()) || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loadingList.value = false
  }
}

async function loadMessages(id) {
  if (!id) {
    messages.value = []
    return
  }
  loadingMessages.value = true
  try {
    messages.value = (await chatApi.messages(id)) || []
    scrollToBottom()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loadingMessages.value = false
  }
}

function selectConversation(id) {
  if (id === currentId.value) return
  currentId.value = id
  alertNotice.value = null
  loadMessages(id)
}

function newConversation() {
  currentId.value = null
  messages.value = []
  alertNotice.value = null
}

onMounted(async () => {
  await loadConversations()
  if (conversations.value.length) {
    selectConversation(conversations.value[0].id)
  }
})

onUnmounted(() => {
  if (liveTimer) clearInterval(liveTimer)
})

/* ---------------- 工具 ---------------- */
function scrollToBottom() {
  nextTick(() => {
    if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
  })
}

/** 把 stage 事件里 detail 转成一行可读的说明 */
function stageDetail(stage) {
  const d = stage.detail || {}
  switch (stage.node) {
    case 'intent':
      return INTENT_LABEL[d.intent] || d.intent || ''
    case 'rag':
      return `命中 ${d.hitCount ?? 0} 条`
    case 'risk':
      return [RISK_LABEL[d.riskLevel] || d.riskLevel, (d.keywords || []).join('、')]
        .filter(Boolean)
        .join(' · ')
    case 'generate':
      return `${d.tokens || 0} tokens`
    default:
      return ''
  }
}

/** 进行中时，下一行该显示什么 */
function pendingLabel(m) {
  if (!m.stages || !m.stages.length) return '连接 AI 服务'
  if (m.content) return '组织回复'
  return '处理中'
}

/* ---------------- 发消息（SSE 流式） ---------------- */
async function send() {
  const text = draft.value.trim()
  if (!text || sending.value) return

  const conversationId = currentId.value
  const isNewConversation = !conversationId
  const userMsgId = `u-${Date.now()}`
  const assistantId = `a-${Date.now() + 1}`

  // 用户消息先乐观展示；AI 那条先占位，delta 到了就往里追加
  messages.value.push({ id: userMsgId, role: 'user', content: text, createTime: '' })
  messages.value.push({
    id: assistantId,
    role: 'assistant',
    content: '',
    createTime: '',
    streaming: true,
    stages: [],
    liveSeconds: 0,
    tokens: 0,
    ragSources: [],
  })

  draft.value = ''
  sending.value = true
  scrollToBottom()

  const live = () => messages.value.find((m) => m.id === assistantId)
  const startedAt = performance.now()
  liveTimer = setInterval(() => {
    const m = live()
    if (m) m.liveSeconds = (performance.now() - startedAt) / 1000
  }, 100)

  let failure = null

  try {
    await consultStream(
      conversationId ? { conversationId, content: text } : { content: text },
      {
        onEvent: (event, data) => {
          const m = live()
          if (!m) return

          if (event === 'open') {
            m.conversationId = data.conversationId
          } else if (event === 'stage') {
            // 真实节点事件：带该节点的真实耗时
            m.stages.push(data)
            scrollToBottom()
          } else if (event === 'delta') {
            m.content += data.text || ''
            scrollToBottom()
          } else if (event === 'done') {
            // 以服务端的完整文本为准做一次覆盖：
            // 高危风险时后端会给回复追加危机资源，那一段没有走过 delta。
            m.content = data.reply || m.content
            m.intent = data.intent
            m.riskLevel = data.riskLevel
            m.tokens = data.tokens
            m.ragSources = data.ragSources || []
            m.elapsed = ((data.elapsedMs || 0) / 1000).toFixed(1)
            m.stages = data.stages || m.stages
            m.disclaimer = data.disclaimer || ''
            m.needHandoff = !!data.needHandoff
            m.streaming = false
            if (data.alertId) {
              alertNotice.value = {
                id: data.alertId,
                level: data.riskLevel,
                needHandoff: !!data.needHandoff,
              }
            }
            if (isNewConversation) currentId.value = data.conversationId
          } else if (event === 'error') {
            failure = new Error(data.message || 'AI 服务异常')
          }
        },
      }
    )
  } catch (e) {
    failure = e
  } finally {
    if (liveTimer) {
      clearInterval(liveTimer)
      liveTimer = null
    }
    sending.value = false
  }

  if (failure) {
    // 流式失败时后端不会落库（落库发生在 done 事件之后），
    // 所以这里把两条本地消息都撤掉，让界面和数据库保持一致，并把输入还给用户。
    messages.value = messages.value.filter((m) => m.id !== userMsgId && m.id !== assistantId)
    draft.value = text
    ElMessage.error(failure.message)
    return
  }

  await loadConversations()
  scrollToBottom()
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

/* ---------------- 咨询报告 ---------------- */
async function openReport() {
  if (!currentId.value) {
    ElMessage.info('先发起一次咨询才能生成报告')
    return
  }
  reportLoading.value = true
  try {
    report.value = await reportApi.generate(currentId.value)
    reportVisible.value = true
    await loadConversations()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    reportLoading.value = false
  }
}

function scoreTone(score) {
  if (score >= 60) return 'ok'
  if (score >= 40) return 'mid'
  return 'bad'
}
</script>

<template>
  <div class="chat">
    <!-- 左：会话列表 -->
    <aside class="side">
      <div class="side-head">
        <div class="sec-head">
          <span class="chip sm"><AppIcon name="chat" :size="14" /></span>
          <span class="caption">我的会话</span>
        </div>
        <button type="button" class="new-btn" title="新建咨询" @click="newConversation">
          <AppIcon name="chat" :size="13" />
          新建
        </button>
      </div>

      <div class="conv-list">
        <div v-if="loadingList && !conversations.length" class="empty">加载中…</div>
        <div v-else-if="!conversations.length" class="empty">还没有咨询记录</div>

        <button
          v-for="c in conversations"
          :key="c.id"
          type="button"
          class="conv"
          :class="{ on: c.id === currentId }"
          @click="selectConversation(c.id)"
        >
          <span class="conv-title">{{ c.title || '新的咨询' }}</span>
          <span class="conv-meta">
            <RiskBadge :level="c.riskLevel" />
            <span class="num">{{ c.turnCount || 0 }} 轮</span>
            <span class="time">{{ hhmm(c.updateTime || c.createTime) }}</span>
          </span>
        </button>
      </div>
    </aside>

    <!-- 右：对话区 -->
    <section class="main">
      <header class="main-head">
        <div class="head-left">
          <h2>{{ current?.title || '新的咨询' }}</h2>
          <RiskBadge v-if="current" :level="current.riskLevel" />
        </div>
        <button type="button" class="ghost-btn" :disabled="reportLoading" @click="openReport">
          <AppIcon name="clipboard" :size="14" />
          <span>{{ reportLoading ? '生成中…' : '咨询报告' }}</span>
        </button>
      </header>

      <div ref="threadEl" class="thread">
        <div v-if="loadingMessages" class="empty">加载中…</div>
        <div v-else-if="!messages.length" class="empty">
          说点什么吧，比如「最近总是失眠，有什么办法吗」
        </div>

        <div v-for="m in messages" :key="m.id" class="row" :class="m.role">
          <template v-if="m.role === 'user'">
            <div class="bubble">{{ m.content }}</div>
          </template>

          <template v-else-if="m.role === 'assistant'">
            <div class="reply">
              <!-- ① 进行中：每个 Agent 节点跑完就出现一行，带真实耗时 -->
              <div v-if="m.streaming" class="trace-live">
                <div class="trace-head">
                  <span class="spinner" aria-hidden="true"></span>
                  <span class="trace-title">正在思考</span>
                  <span class="num trace-time">{{ m.liveSeconds.toFixed(1) }}s</span>
                </div>

                <ol class="stage-list">
                  <li v-for="s in m.stages" :key="s.node" class="stage">
                    <span class="dot done"></span>
                    <span class="stage-name">{{ s.label }}</span>
                    <span class="num stage-ms">{{ (s.elapsedMs / 1000).toFixed(2) }}s</span>
                    <span class="stage-detail">{{ stageDetail(s) }}</span>
                  </li>
                  <li class="stage">
                    <span class="dot now"></span>
                    <span class="stage-name pending">{{ pendingLabel(m) }}</span>
                    <span class="stage-detail">进行中</span>
                  </li>
                </ol>

                <div class="bar-indeterminate"><span></span></div>
              </div>

              <!-- ② 已完成 / 历史消息：收起成一个小三角，展开是分析明细 -->
              <details v-else-if="m.intent || m.tokens" class="trace">
                <summary>
                  <span class="trace-title">{{ m.stages && m.stages.length ? '思考过程' : '本次分析' }}</span>
                  <span v-if="m.elapsed" class="num trace-time">{{ m.elapsed }}s</span>
                  <span class="meta-sep">·</span>
                  <span class="trace-tag">{{ INTENT_LABEL[m.intent] || m.intent || '—' }}</span>
                  <template v-if="m.tokens">
                    <span class="meta-sep">·</span>
                    <span class="num trace-time">{{ m.tokens }} tokens</span>
                  </template>
                </summary>

                <div class="trace-body">
                  <!-- 有真实阶段明细就画时间线 -->
                  <ol v-if="m.stages && m.stages.length" class="stage-list">
                    <li v-for="s in m.stages" :key="s.node" class="stage">
                      <span class="dot done"></span>
                      <span class="stage-name">{{ s.label }}</span>
                      <span class="num stage-ms">{{ (s.elapsedMs / 1000).toFixed(2) }}s</span>
                      <span class="stage-detail">{{ stageDetail(s) }}</span>
                    </li>
                  </ol>

                  <!-- 历史消息没有阶段明细（message 表不存这些），退化成摘要 -->
                  <dl v-else class="trace-kv">
                    <div>
                      <dt>意图判定</dt>
                      <dd>{{ INTENT_LABEL[m.intent] || m.intent || '—' }}</dd>
                    </div>
                    <div>
                      <dt>风险等级</dt>
                      <dd><RiskBadge v-if="m.riskLevel" :level="m.riskLevel" /><span v-else>—</span></dd>
                    </div>
                    <div>
                      <dt>消耗</dt>
                      <dd class="num">{{ m.tokens || 0 }} tokens</dd>
                    </div>
                    <div>
                      <dt>说明</dt>
                      <dd class="dim">历史记录不保存各节点耗时</dd>
                    </div>
                  </dl>
                </div>
              </details>

              <div v-if="m.content" class="reply-body" v-html="formatReply(m.content)"></div>

              <p v-if="m.ragSources && m.ragSources.length" class="sources">
                <span class="caption">知识库命中</span>
                <span v-for="(s, i) in m.ragSources" :key="i" class="src">{{ s }}</span>
              </p>

              <!-- 合规兜底：AI 回复不构成医学诊断。视觉做轻，不抢正文注意力 -->
              <p v-if="m.disclaimer" class="disclaimer">{{ m.disclaimer }}</p>
            </div>
          </template>
        </div>
      </div>

      <!-- 高危提示条：工单已建；needHandoff 时给出可直接拨打的求助入口 -->
      <div
        v-if="alertNotice"
        class="notice"
        :class="alertNotice.level === 'HIGH' ? 'notice-high' : 'notice-med'"
      >
        <div class="notice-main">
          <span>
            已生成风险预警工单 <b class="num">#{{ alertNotice.id }}</b>，辅导员会尽快跟进。
          </span>
          <!-- 「转人工」的真入口。此前这里只有一句「已附上人工求助入口」的文案，
               但页面上没有任何可点的东西 —— 学生想求助其实无路可走。
               做成 tel: 链接而不是一串号码：危机场景里让一个已经很难受的人
               自己抄下电话再找拨号盘，等于没有入口。 -->
          <div v-if="alertNotice.needHandoff" class="handoff">
            <span class="handoff-tip">现在就想找人聊聊，可以直接打：</span>
            <a class="handoff-link" href="tel:4001619995">
              全国心理援助热线 <b>400-161-9995</b>
            </a>
            <a class="handoff-link" href="tel:01082951332">
              北京心理危机干预中心 <b>010-82951332</b>
            </a>
          </div>
        </div>
        <button type="button" @click="alertNotice = null">知道了</button>
      </div>

      <div class="composer">
        <textarea
          v-model="draft"
          rows="1"
          placeholder="输入你想说的话，Enter 发送，Shift + Enter 换行"
          :disabled="sending"
          @keydown="onKeydown"
        ></textarea>
        <button type="button" class="send" :disabled="sending || !draft.trim()" @click="send">
          发送
        </button>
      </div>
    </section>

    <!-- 报告弹窗 -->
    <el-dialog v-model="reportVisible" title="咨询报告" width="560px">
      <div v-if="report" class="report">
        <div class="report-row">
          <span class="caption">情绪评分</span>
          <div class="score">
            <span class="num score-num" :class="scoreTone(report.emotionScore)">
              {{ report.emotionScore }}
            </span>
            <div class="bar">
              <div
                class="bar-fill"
                :class="scoreTone(report.emotionScore)"
                :style="{ width: Math.max(0, Math.min(100, report.emotionScore || 0)) + '%' }"
              ></div>
            </div>
          </div>
        </div>

        <div class="report-row">
          <span class="caption">综合风险</span>
          <RiskBadge :level="report.riskLevel" />
        </div>

        <div class="report-block">
          <span class="caption">对话摘要</span>
          <p>{{ report.summary || '—' }}</p>
        </div>

        <div class="report-block">
          <span class="caption">干预建议</span>
          <p>{{ report.suggestion || '—' }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  height: 100%;
  background: var(--panel);
}

/* ---------- 左侧会话列表 ---------- */
.side {
  width: 248px;
  flex: none;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--line);
  background: var(--panel-2);
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 12px 0 16px;
  flex: none;
}

.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line-2);
  background: var(--panel);
  border-radius: 4px;
  padding: 3px 10px;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
  transition:
    transform 0.18s var(--ease),
    border-color 0.18s var(--ease),
    color 0.18s var(--ease),
    background-color 0.18s var(--ease);
}

.new-btn:hover {
  transform: translateY(-1px);
  border-color: var(--brand-line);
  background: var(--brand-soft);
  color: var(--brand);
}

.new-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
}

.conv-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.conv {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 10px 10px 12px;
  margin-bottom: 2px;
  border: none;
  border-left: 2px solid transparent;
  border-radius: 0 var(--radius) var(--radius) 0;
  background: none;
  cursor: pointer;
  transition:
    background-color 0.18s var(--ease),
    border-color 0.18s var(--ease);
}

.conv:hover {
  background: var(--panel-2);
}

/* 选中项用浅绿底 + 左侧品牌色竖条。
   原来用纯白 —— 在浅灰侧栏里其实跳不出来，浅绿才有"选中了"的归属感。 */
.conv.on {
  background: var(--brand-soft);
  border-left-color: var(--brand);
}

.conv-title {
  display: block;
  font-size: 13.5px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--ink-3);
}

.time {
  margin-left: auto;
  font-family: var(--mono);
}

/* ---------- 右侧 ---------- */
.main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* 对话区底纹：一层从上往下淡出的点阵。
   一大片纯白的消息区没有任何材质，看起来像"还没加载完"。
   底纹垫在内容下面（z-index: 0），不跟着消息滚动 ——
   读起来像一张压在纸下的纹理纸，而不是会动的壁纸。 */
.main::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image: radial-gradient(rgba(44, 95, 82, 0.085) 1px, transparent 1px);
  background-size: 20px 20px;
  -webkit-mask-image: radial-gradient(80% 72% at 50% 0%, #000 0%, transparent 80%);
  mask-image: radial-gradient(80% 72% at 50% 0%, #000 0%, transparent 80%);
}

.main > * {
  position: relative;
  z-index: 1;
}

.main-head {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 56px;
  padding: 0 24px;
  flex: none;
  /* 玻璃：消息往上滚时会从下面透出来。
     和全站顶栏用同一种材质 —— 材质不统一，"高级感"立刻散架。 */
  background: rgba(255, 255, 255, 0.72);
  -webkit-backdrop-filter: blur(14px) saturate(180%);
  backdrop-filter: blur(14px) saturate(180%);
  border-bottom: 1px solid var(--line);
  box-shadow: inset 0 1px 0 var(--glass-line);
}

.head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.head-left h2 {
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line-2);
  border-radius: var(--radius);
  background: var(--panel);
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  transition:
    transform 0.18s var(--ease),
    border-color 0.18s var(--ease),
    color 0.18s var(--ease),
    box-shadow 0.18s var(--ease);
}

.ghost-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--brand-line);
  color: var(--brand);
  box-shadow: 0 8px 16px -12px rgba(44, 95, 82, 0.6);
}

.ghost-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

/* ---------- 消息流 ---------- */
.thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 28px 24px 8px;
}

.row {
  margin-bottom: 24px;
}

.row.user {
  display: flex;
  justify-content: flex-end;
}

/* 学生消息用气泡；AI 回复不用气泡，靠左侧细线区分 —— 视觉噪音更小 */
.bubble {
  max-width: 74%;
  padding: 9px 13px;
  background: var(--brand-bg);
  border: 1px solid var(--brand-line);
  border-radius: var(--radius-lg) var(--radius-lg) 2px var(--radius-lg);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.reply {
  max-width: 82%;
  padding-left: 14px;
  border-left: 2px solid var(--line-2);
}

.meta-sep {
  color: var(--ink-4);
}

.reply-body {
  font-size: 14px;
  line-height: 1.85;
  color: var(--ink);
  word-break: break-word;
}

.reply-body :deep(strong) {
  font-weight: 600;
}

/* ---------- 思考过程面板 ---------- */
.trace {
  margin-bottom: 8px;
}

.trace summary {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: var(--ink-3);
  cursor: pointer;
  user-select: none;
  list-style-position: inside;
}

.trace summary:hover {
  color: var(--ink-2);
}

.trace-title {
  color: var(--ink-2);
}

.trace-time {
  font-size: 12px;
  color: var(--ink-3);
}

.trace-tag {
  color: var(--ink-2);
}

.trace-body {
  margin: 8px 0 0;
  padding: 10px 14px;
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.trace-live {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel-2);
}

.trace-head {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: var(--ink-2);
}

/* 节点时间线 */
.stage-list {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.trace-body .stage-list {
  margin-top: 0;
}

.stage {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  font-size: 12.5px;
}

.dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
}

.dot.done {
  background: var(--brand);
}

/* 进行中的点做呼吸效果，表示「还没完」 */
.dot.now {
  background: var(--brand);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.35;
    transform: scale(0.8);
  }
}

.stage-name {
  color: var(--ink-2);
  width: 68px;
  flex: none;
}

.stage-name.pending {
  color: var(--ink-3);
}

.stage-ms {
  color: var(--ink-3);
  font-size: 11.5px;
  width: 46px;
  flex: none;
  text-align: right;
}

.stage-detail {
  color: var(--ink-3);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 历史消息的摘要表 */
.trace-kv {
  margin: 0;
}

.trace-kv > div {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  font-size: 12.5px;
}

.trace-kv dt {
  width: 56px;
  flex: none;
  color: var(--ink-3);
}

.trace-kv dd {
  margin: 0;
  color: var(--ink-2);
  display: flex;
  align-items: center;
}

.trace-kv .dim {
  color: var(--ink-4);
}

/* 转圈 */
.spinner {
  width: 12px;
  height: 12px;
  flex: none;
  border: 1.5px solid var(--brand-line);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 不确定进度条：只表达「在跑」 */
.bar-indeterminate {
  position: relative;
  height: 2px;
  margin-top: 10px;
  background: var(--line);
  border-radius: 1px;
  overflow: hidden;
}

.bar-indeterminate span {
  position: absolute;
  top: 0;
  height: 100%;
  width: 35%;
  background: var(--brand);
  border-radius: 1px;
  animation: slide 1.4s ease-in-out infinite;
}

@keyframes slide {
  0% {
    left: -35%;
  }
  100% {
    left: 100%;
  }
}

/* 知识库命中 */
.sources {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.src {
  font-size: 12px;
  color: var(--ink-2);
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 7px;
}

/* 免责声明：法律与伦理上的必要兜底，视觉上刻意弱化 ——
   用最浅的灰、不加边框，避免和正文抢注意力。 */
.disclaimer {
  margin-top: 10px;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--ink-4);
}

/* ---------- 提示条 ---------- */
.notice {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: 0 24px;
  padding: 9px 14px;
  border-radius: var(--radius);
  font-size: 13px;
}

.notice-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 「转人工」入口：needHandoff 时才出现。
   用 currentColor 描边而不是固定色，好让高危/中危两种提示条各自沿用自己那套配色。 */
.handoff {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.handoff-tip {
  opacity: 0.8;
}

.handoff-link {
  color: inherit;
  text-decoration: none;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 2px 10px;
  opacity: 0.9;
}

.handoff-link:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.55);
}

.handoff-link b {
  font-weight: 600;
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

.notice button {
  flex: none;
  border: none;
  background: none;
  font-size: 12.5px;
  color: inherit;
  opacity: 0.75;
  cursor: pointer;
}

.notice button:hover {
  opacity: 1;
}

/* ---------- 输入区 ---------- */
.composer {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  flex: none;
}

.composer textarea {
  flex: 1;
  min-height: 42px;
  max-height: 160px;
  padding: 11px 14px;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line-2);
  border-radius: var(--radius-lg);
  outline: none;
  resize: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.composer textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-bg);
}

.send {
  flex: none;
  height: 42px;
  padding: 0 22px;
  border: none;
  border-radius: var(--radius-lg);
  background: var(--brand);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.send:hover:not(:disabled) {
  background: var(--brand-ink);
}

.send:disabled {
  background: var(--line-2);
  color: #fff;
  cursor: default;
}

/* ---------- 报告 ---------- */
.report-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}

.report-row .caption {
  width: 64px;
  flex: none;
}

.score {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.score-num {
  font-size: 20px;
  line-height: 1;
}

.score-num.ok {
  color: var(--brand);
}
.score-num.mid {
  color: var(--med);
}
.score-num.bad {
  color: var(--high);
}

.bar {
  flex: 1;
  height: 4px;
  background: var(--line);
  border-radius: 2px;
  overflow: hidden;
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

.report-block {
  padding: 16px 0 4px;
}

.report-block p {
  margin-top: 8px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink-2);
  white-space: pre-wrap;
}
</style>
