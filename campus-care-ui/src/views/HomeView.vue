<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dashboardApi, knowledgeApi, profileApi } from '../api'
import { currentUser, isCounselor } from '../auth'
import AppIcon from '../components/AppIcon.vue'
import BrandMark from '../components/BrandMark.vue'
import CountUp from '../components/CountUp.vue'
import RiskBadge from '../components/RiskBadge.vue'
import { shortTime } from '../format'

const router = useRouter()

const profile = ref(null)
const board = ref(null)
const tips = ref([])
const loading = ref(true)

const name = computed(() => currentUser.value?.realName || currentUser.value?.username || '同学')
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  if (h < 23) return '晚上好'
  return '夜深了'
})
const todayText = computed(() => {
  const d = new Date()
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 周${week}`
})

/**
 * 标题拆成逐字入场的片段。
 * 中文按「词」拆会拆错，按「字」拆又太碎 —— 所以只拆名字，
 * 问候语整段先落。名字太长（学号形式的用户名）就整段出现，
 * 否则 52ms × 十几个字会拖成慢动作。
 *
 * 拆字必须用展开运算符 [...s]，不能用 s.split('')：
 * split 按 UTF-16 码元切分，会把代理对（emoji、生僻字）劈成两半，
 * 每一半都不能独立显示 —— 页面上就是一个「乱码方块」。
 */
const heroWords = computed(() => {
  const n = String(name.value)
  const chars = [...n]
  if (chars.length > 6) return [{ text: `${greeting.value}，${n}` }]
  return [
    { text: `${greeting.value}，`, greet: true },
    ...chars.map((ch) => ({ text: ch })),
  ]
})

/* ---------------- 学生视角 ---------------- */

const overview = computed(() => profile.value?.overview || {})
const riskLevel = computed(() => overview.value.highestRiskLevel || 'LOW')

/** 状态一句话：把「最高风险等级」翻译成人话，只给数字学生看不懂 */
const riskNote = computed(() => {
  if (!profile.value) return ''
  const o = overview.value
  if (!o.conversationCount && !o.assessmentCount) {
    return '还没有记录，从一次倾诉或一份测评开始'
  }
  if (o.highestRiskLevel === 'HIGH') return '近期记录中出现过需要关注的表达，辅导员已可看到'
  if (o.highestRiskLevel === 'MEDIUM') return '近期状态有些起伏，建议保持规律作息并留意情绪'
  return '当前状态平稳，继续保持'
})

const timeline = computed(() => (profile.value?.timeline || []).slice(0, 4))

const timelineLabel = { ALERT: '风险工单', ASSESSMENT: '心理测评', REPORT: '咨询报告' }

/** 今日贴士：按「天」取模而不是随机 —— 同一天内刷新页面不会变来变去 */
const tip = computed(() => {
  if (!tips.value.length) return null
  const dayIndex = Math.floor(Date.now() / 86400000) % tips.value.length
  return tips.value[dayIndex]
})

/* ---------------- 辅导员视角 ---------------- */

const summary = computed(() => board.value?.summary || {})
const insights = computed(() => (board.value?.insights || []).slice(0, 4))
const topStudents = computed(() => (board.value?.topStudents || []).slice(0, 5))

/* ---------------- 快捷入口 ---------------- */

const quicks = computed(() => {
  if (isCounselor.value) {
    return [
      { label: '预警工单', desc: '查看并处置学生风险工单，高危优先', to: { name: 'alerts' }, icon: 'alert' },
      { label: '数据看板', desc: '全局风险态势与时段规律', to: { name: 'dashboard' }, icon: 'dashboard' },
      { label: '学生档案', desc: '按工单进入完整记录', to: { name: 'alerts' }, icon: 'folder' },
      { label: '心理科普', desc: '沟通时可引用的内容', to: { name: 'knowledge' }, icon: 'book' },
    ]
  }
  return [
    { label: '开始倾诉', desc: '随时说说现在的心情，可以匿名', to: { name: 'chat' }, icon: 'chat' },
    { label: '心理测评', desc: 'PHQ-9 / GAD-7 标准量表自评', to: { name: 'assessment' }, icon: 'clipboard' },
    { label: '我的档案', desc: '咨询、测评、工单的完整记录', to: { name: 'profile' }, icon: 'folder' },
    { label: '心理科普', desc: '睡眠、焦虑、人际关系', to: { name: 'knowledge' }, icon: 'book' },
  ]
})

/* ---------------- 数字概览 ----------------
   学生和辅导员原本是两段几乎重复的模板。
   收成一份数据后：模板只剩 10 行，而且能自然地拿到下标 i ——
   逐张卡的入场延迟就是靠它。 */
const statCards = computed(() => {
  if (isCounselor.value) {
    return [
      { label: '累计工单', value: summary.value.totalCount || 0, icon: 'clipboard' },
      { label: '其中高危', value: summary.value.highCount || 0, icon: 'alert', tone: 'high' },
      { label: '待处理', value: summary.value.pendingCount || 0, icon: 'clock', tone: 'med' },
      { label: '涉及学生', value: summary.value.studentCount || 0, icon: 'user' },
    ]
  }
  const score = overview.value.latestEmotionScore
  return [
    { label: '咨询会话', value: overview.value.conversationCount || 0, icon: 'chat' },
    { label: '累计对话轮次', value: overview.value.totalTurns || 0, icon: 'trend' },
    { label: '测评次数', value: overview.value.assessmentCount || 0, icon: 'clipboard' },
    {
      label: '最近情绪分',
      value: score ?? '—',
      icon: 'sparkles',
      tone: riskLevel.value === 'HIGH' ? 'high' : '',
    },
  ]
})

function go(item) {
  router.push(item.to)
}

function goProfile(userId) {
  if (userId) router.push({ name: 'profile', params: { userId } })
}

async function load() {
  loading.value = true
  try {
    // 贴士是次要内容，失败不该影响整个首页，所以单独兜住
    knowledgeApi
      .list()
      .then((list) => {
        tips.value = (list || []).filter((i) => i.content)
      })
      .catch(() => {
        tips.value = []
      })

    if (isCounselor.value) {
      board.value = await dashboardApi.get(14, 6)
    } else {
      profile.value = await profileApi.me()
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="home">
    <!-- ================= Loading 骨架屏 ================= -->
    <template v-if="loading">
      <section class="hero tile skeleton-hero">
        <div class="hero-left">
          <div class="skeleton" style="width: 120px; height: 14px; margin-bottom: 14px;"></div>
          <div class="skeleton" style="width: 70%; height: 36px; margin-bottom: 10px;"></div>
          <div class="skeleton" style="width: 55%; height: 14px;"></div>
        </div>
        <div class="hero-right" style="text-align: right;">
          <div class="skeleton" style="width: 60px; height: 12px; margin-left: auto; margin-bottom: 10px;"></div>
          <div class="skeleton" style="width: 80px; height: 26px; margin-left: auto; margin-bottom: 8px;"></div>
          <div class="skeleton" style="width: 120px; height: 12px; margin-left: auto;"></div>
        </div>
      </section>
      <section class="quicks">
        <div v-for="i in 4" :key="i" class="quick tile" :class="{ featured: i === 1 }">
          <div class="q-top">
            <div class="skeleton chip" style="width: 34px; height: 34px; border-radius: 9px;"></div>
            <div class="skeleton" style="width: 24px; height: 12px;"></div>
          </div>
          <div class="skeleton" style="width: 60%; height: 16px; margin-top: 6px;"></div>
          <div class="skeleton" style="width: 80%; height: 12px; margin-top: 8px;"></div>
        </div>
      </section>
      <section class="stats">
        <div v-for="i in 4" :key="i" class="stat-card" style="padding: 15px 17px;">
          <div class="skeleton chip" style="width: 27px; height: 27px; border-radius: 7px;"></div>
          <div class="skeleton" style="width: 40px; height: 26px; margin-top: 10px;"></div>
          <div class="skeleton" style="width: 70px; height: 12px; margin-top: 8px;"></div>
        </div>
      </section>
      <section class="cols">
        <div class="panel pad" style="min-height: 180px;">
          <div class="skeleton" style="width: 100px; height: 14px; margin-bottom: 16px;"></div>
          <div v-for="i in 3" :key="i" class="skeleton" style="width: 85%; height: 12px; margin-bottom: 14px;"></div>
        </div>
        <div class="panel pad side" style="min-height: 180px;">
          <div class="skeleton" style="width: 110px; height: 14px; margin-bottom: 16px;"></div>
          <div v-for="i in 3" :key="i" class="skeleton" style="width: 75%; height: 12px; margin-bottom: 14px;"></div>
        </div>
      </section>
    </template>

    <!-- ================= 真实内容 ================= -->
    <template v-else>
      <!-- ================= 问候 ================= -->
      <section v-tilt="2.5" v-reveal class="hero tile">
        <span class="hero-mark" aria-hidden="true"><BrandMark :size="260" /></span>
        <span class="hero-dots" aria-hidden="true"></span>

        <div class="hero-left">
          <div class="hero-eyebrow">
            <span class="chip sm">
              <AppIcon :name="isCounselor ? 'dashboard' : 'shield'" :size="14" />
            </span>
            <span class="caption">{{ todayText }}</span>
          </div>
          <h1>
            <span
              v-for="(w, i) in heroWords"
              :key="i"
              class="word"
              :class="{ greet: w.greet }"
              :style="{ '--w': i + 1 }"
            >{{ w.text }}</span>
          </h1>
          <p class="hero-sub">
            {{
              isCounselor
                ? '这里是你的工作台，先看有没有需要处理的工单。'
                : '这里是你的私人空间。说什么都可以，不会有人随意翻看。'
            }}
          </p>
        </div>

        <div class="hero-right">
          <span class="caption">综合状态</span>
          <div class="risk-row">
            <RiskBadge v-if="isCounselor" :level="summary.highCount > 0 ? 'HIGH' : 'LOW'" />
            <RiskBadge v-else :level="riskLevel" />
          </div>
          <p class="risk-note">
            {{
              isCounselor
                ? `当前 ${summary.pendingCount || 0} 条待处理工单`
                : riskNote
            }}
          </p>
        </div>
      </section>

      <!-- ================= 快捷入口（Bento） ================= -->
      <section class="quicks">
        <button
          v-for="(q, i) in quicks"
          :key="q.label"
          v-spotlight
          v-reveal="i"
          type="button"
          class="quick tile"
          :class="{ featured: i === 0 }"
          @click="go(q)"
        >
          <span class="q-top">
            <span class="chip" :class="{ lg: i === 0 }">
              <AppIcon :name="q.icon" :size="i === 0 ? 21 : 17" />
            </span>
            <span class="q-no num">{{ String(i + 1).padStart(2, '0') }}</span>
          </span>
          <span class="q-title">{{ q.label }}</span>
          <span class="q-desc">{{ q.desc }}</span>
          <span class="q-go">
            进入
            <AppIcon name="arrow" :size="13" />
          </span>
          <span v-if="i === 0" class="q-mark" aria-hidden="true"><BrandMark :size="160" /></span>
        </button>
      </section>

      <!-- ================= 数字概览 ================= -->
      <section v-if="isCounselor || profile" class="stats">
        <div
          v-for="(c, i) in statCards"
          :key="c.label"
          v-spotlight
          v-reveal="i"
          class="stat-card"
          :class="c.tone ? `${c.tone} tinted` : ''"
        >
          <span class="chip sm" :class="c.tone">
            <AppIcon :name="c.icon" :size="15" />
          </span>
          <b class="st-n num" :class="c.tone"><CountUp :value="c.value" /></b>
          <span class="st-l">{{ c.label }}</span>
        </div>
      </section>

      <!-- ================= 两栏主体 ================= -->
      <section class="cols">
        <!-- 左栏 -->
        <div v-reveal class="panel pad">
          <template v-if="isCounselor">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="sparkles" :size="14" /></span>
              <span class="caption">今天的结论</span>
            </div>
            <ul v-if="insights.length" class="insights">
              <li v-for="(text, i) in insights" :key="i">{{ text }}</li>
            </ul>
            <div v-else class="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              <p>暂无统计数据</p>
              <span class="empty-hint">当有足够的学生咨询记录后，系统会自动生成分析结论</span>
            </div>
          </template>

          <template v-else>
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="clock" :size="14" /></span>
              <span class="caption">最近动态</span>
            </div>
            <div v-if="!timeline.length" class="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              <p>还没有记录</p>
              <span class="empty-hint">去做一次测评或开始一次倾诉吧</span>
            </div>
            <ul v-else class="tl">
              <li v-for="(it, i) in timeline" :key="i" class="tl-item">
                <span class="tl-type">{{ timelineLabel[it.type] || it.type }}</span>
                <span class="tl-title">{{ it.title }}</span>
                <span class="tl-time num">{{ shortTime(it.time) }}</span>
              </li>
            </ul>
          </template>
        </div>

        <!-- 右栏 -->
        <div v-reveal="1" class="panel pad side">
          <template v-if="isCounselor">
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="user" :size="14" /></span>
              <span class="caption">重点学生</span>
            </div>
            <div v-if="!topStudents.length" class="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
              <p>暂无重点学生数据</p>
              <span class="empty-hint">系统会根据风险等级自动识别需要关注的学生</span>
            </div>
            <ul v-else class="tops">
              <li
                v-for="s in topStudents"
                :key="s.userId"
                class="top"
                @click="goProfile(s.userId)"
              >
                <span class="t-name">{{ s.realName || s.studentNo || `学生 #${s.userId}` }}</span>
                <span class="t-meta">
                  <span class="num">{{ s.alertCount }}</span> 条工单
                  <template v-if="s.highCount > 0">
                    · <b class="num high">{{ s.highCount }}</b> 高危
                  </template>
                </span>
              </li>
            </ul>
          </template>

          <template v-else>
            <div class="sec-head">
              <span class="chip sm"><AppIcon name="sparkles" :size="14" /></span>
              <span class="caption">今日心理小贴士</span>
            </div>
            <template v-if="tip">
              <h3 class="tip-title">{{ tip.title }}</h3>
              <p class="tip-text">{{ tip.content }}</p>
              <span class="tip-src">{{ tip.source }}</span>
            </template>
            <div v-else class="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 20h9"></path>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
              </svg>
              <p>内容加载中…</p>
            </div>
          </template>
        </div>
      </section>

      <!-- ================= 危机资源（仅学生） ================= -->
      <section v-if="!isCounselor" v-reveal class="crisis">
        <div class="cr-left">
          <div class="sec-head">
            <span class="chip sm high"><AppIcon name="phone" :size="14" /></span>
            <span class="caption">需要马上找人聊聊？</span>
          </div>
          <p class="cr-text">
            如果此刻感到难以承受，不必独自撑着。以下资源 24 小时可用。
          </p>
        </div>
        <div class="cr-right">
          <div class="hot">
            <span class="hot-name">全国心理援助热线</span>
            <span class="hot-num num">400-161-9995</span>
          </div>
          <div class="hot">
            <span class="hot-name">北京心理危机干预中心</span>
            <span class="hot-num num">010-82951332</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.home {
  height: 100%;
  overflow-y: auto;
  /* 超宽屏上把内容居中收窄，但滚动条仍然贴在窗口右缘 ——
     如果改用 max-width + margin:auto，滚动容器跟着变窄，
     滚动条会跑到屏幕中间，看起来像 bug。
     padding-inline 上的 max() 正好能做到"内容收窄、容器不变"。 */
  padding: 28px max(32px, calc((100% - 1340px) / 2)) 56px;
}

/* ---------- 问候区 ---------- */
.hero {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  padding: 30px 32px 32px;
  border: 1px solid var(--brand-line);
  border-radius: var(--radius-lg);
  /* 三层叠出来：左上角一团品牌光 + 右下角一层柔影 + 斜向主渐变。
     比单色块"平涂"有光感，但三层全部派生自墨绿，不会跑出色系。 */
  background:
    radial-gradient(460px 280px at 4% -40%, rgba(44, 95, 82, 0.2) 0%, rgba(44, 95, 82, 0) 70%),
    radial-gradient(560px 340px at 110% 128%, rgba(44, 95, 82, 0.1) 0%, rgba(44, 95, 82, 0) 66%),
    linear-gradient(118deg, #e7f2ee 0%, #f2f8f6 46%, #f7fafb 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 2px rgba(20, 22, 26, 0.03),
    0 24px 48px -36px rgba(44, 95, 82, 0.5);
  /* 内联 transform 由 v-tilt 写，这里只负责把过渡定好 ——
     少了这条，鼠标一动整块面会"瞬移" */
  transition:
    transform 0.4s var(--ease-out),
    border-color 0.3s var(--ease),
    box-shadow 0.3s var(--ease);
  transform-style: preserve-3d;
}

/* 放大的品牌标识压在最底层当水印。透明度压到 5%，只在余光里存在；
   一旦调到 15% 以上就变成"贴图"，反而廉价。 */
.hero-mark {
  position: absolute;
  right: -56px;
  top: -44px;
  color: var(--brand);
  opacity: 0.05;
  pointer-events: none;
}

/* 点阵纹理：给平面加一层材质。用 mask 从右向左淡出，不出现硬边界 */
.hero-dots {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: radial-gradient(rgba(44, 95, 82, 0.18) 1px, transparent 1px);
  background-size: 18px 18px;
  -webkit-mask-image: radial-gradient(64% 130% at 90% 38%, #000 0%, transparent 74%);
  mask-image: radial-gradient(64% 130% at 90% 38%, #000 0%, transparent 74%);
  opacity: 0.7;
}

.hero-left,
.hero-right {
  position: relative;
  /* 3D 倾斜时内容跟着面板走，但不要被面板的阴影层面吃掉 */
  transform: translateZ(24px);
}

.hero-eyebrow {
  display: flex;
  align-items: center;
  gap: 9px;
}

.hero h1 {
  margin-top: 10px;
  font-size: var(--t-hero);
  font-weight: 600;
  line-height: 1.16;
  letter-spacing: -0.035em;
  /* 这里【不能】用「渐变文字」（background-clip: text）。
     标题里的每个字都是一个带 transform/opacity 动画的 span，
     动画会把它们各自提升为独立的合成层；父元素的渐变底色于是被
     逐层重复裁剪一遍，屏幕上就叠成一团重影 —— 看上去就是乱码。
     改用同色相的两档字色来还原那支渐变的走向：
     问候语深、名字浅，从左到右「深 → 浅」。 */
  color: var(--brand);
}

/* 问候语再深一档。原来那支 112° 渐变就是从深压到浅，
   现在只是把它量化成两级，色相仍然是同一个墨绿。 */
.hero h1 .greet {
  color: var(--brand-deep);
  font-weight: 500;
}

.hero-sub {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.75;
  color: var(--ink-2);
}

.hero-right {
  flex: none;
  text-align: right;
}

.risk-row {
  margin-top: 8px;
}

.risk-note {
  margin-top: 8px;
  max-width: 260px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-2);
}

/* ---------- 快捷入口 ---------- */
.quicks {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.quick {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
  padding: 18px;
  text-align: left;
  background: var(--panel-grad);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 2px rgba(20, 22, 26, 0.03);
  cursor: pointer;
  /* 抬起、染色、聚光、描边光晕、图标块翻实心 —— 统一交给 .tile */
}

/* 主角卡：横跨 2×2 */
.quick.featured {
  grid-column: span 2;
  grid-row: span 2;
  gap: 11px;
  padding: 24px;
  background:
    radial-gradient(340px 240px at 104% -10%, rgba(44, 95, 82, 0.12) 0%, rgba(44, 95, 82, 0) 70%),
    var(--panel-grad);
}

/* 图标块 + 序号分列两端：左边回答"这是什么"，右边回答"第几个" */
.q-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 4px;
}

/* 序号用等宽小字，比图标更安静，也符合整站的编辑感 */
.q-no {
  font-size: 11px;
  color: var(--ink-4);
  transition: color 0.22s var(--ease);
}

.quick:hover .q-no {
  color: var(--brand);
}

.q-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--ink);
  transition: color 0.22s var(--ease);
}

.quick:hover .q-title {
  color: var(--brand-ink);
}

/* 主角卡的标题放大到 24px：面积的层级必须由字号呼应，
   否则"大卡片配小标题"只会显得空 */
.quick.featured .q-title {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.q-desc {
  flex: 1;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-3);
}

.quick.featured .q-desc {
  font-size: 13.5px;
  line-height: 1.8;
  max-width: 26ch;
}

.q-go {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 5px;
  font-size: 12px;
  color: var(--brand);
  transition: transform 0.26s var(--ease);
}

.quick.featured .q-go {
  font-size: 13px;
}

/* 箭头跟着卡片一起往右挪一下，指向性更明确 */
.quick:hover .q-go {
  transform: translateX(4px);
}

/* 主角卡角落压一枚放大的品牌标识，悬停时轻微放大并转一点 */
.q-mark {
  position: absolute;
  right: -40px;
  bottom: -36px;
  color: var(--brand);
  opacity: 0.045;
  pointer-events: none;
  transition:
    opacity 0.4s var(--ease),
    transform 0.6s var(--ease-out);
}

.quick.featured:hover .q-mark {
  opacity: 0.085;
  transform: scale(1.06) rotate(-8deg);
}

/* ---------- 数字概览 ---------- */
.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.st-n {
  font-size: 26px;
  font-weight: 500;
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--ink);
}

.st-n.high {
  color: var(--high);
}

.st-n.med {
  color: var(--med);
}

.st-l {
  font-size: 12px;
  color: var(--ink-3);
}

/* ---------- 两栏 ---------- */
.cols {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.pad {
  padding: 20px 22px;
}

.blank-line {
  margin-top: 14px;
  font-size: 13px;
  color: var(--ink-3);
}

/* ---------- 空状态 ---------- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 16px;
  text-align: center;
  color: var(--ink-4);
}
.empty-state svg {
  margin-bottom: 10px;
  color: var(--ink-4);
  opacity: 0.5;
}
.empty-state p {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--ink-3);
  margin-bottom: 4px;
}
.empty-state .empty-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-4);
  max-width: 24ch;
}

/* 结论列表 */
.insights {
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.insights li {
  position: relative;
  padding-left: 16px;
  margin-bottom: 9px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink-2);
}

.insights li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--brand);
}

/* 时间线 */
.tl {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.tl-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}

.tl-item:last-child {
  border-bottom: none;
}

.tl-type {
  flex: none;
  font-size: 11px;
  color: var(--ink-3);
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 0 5px;
}

.tl-title {
  flex: 1;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tl-time {
  flex: none;
  font-size: 12px;
  color: var(--ink-4);
}

/* 小贴士 */
.side {
  display: flex;
  flex-direction: column;
}

.tip-title {
  margin-top: 12px;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.5;
}

.tip-text {
  flex: 1;
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.9;
  color: var(--ink-2);
}

.tip-src {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 11.5px;
  color: var(--ink-4);
}

/* 重点学生 */
.tops {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 8px;
  margin: 0 -8px;
  border-bottom: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  transition:
    background-color 0.18s var(--ease),
    box-shadow 0.18s var(--ease);
}

.top:last-child {
  border-bottom: none;
}

/* 悬停时左侧长出一条品牌色内影，比整行变色安静 */
.top:hover {
  background: var(--panel-2);
  box-shadow: inset 2px 0 0 var(--brand);
}

.top:hover .t-name {
  color: var(--brand);
}

.t-name {
  font-size: 13.5px;
  color: var(--ink);
  transition: color 0.18s var(--ease);
}

.t-meta {
  flex: none;
  font-size: 12px;
  color: var(--ink-3);
}

.high {
  color: var(--high);
}

/* ---------- 危机资源 ---------- */
.crisis {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  margin-top: 16px;
  padding: 20px 24px;
  background: linear-gradient(116deg, #fff8f7 0%, var(--panel-2) 48%, #fbfdfc 100%);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

/* 左侧一条 2px 暖色竖条：全站唯一出现暖色的地方，只用在危机资源上。
   语义上说得通 —— 它是紧急出口，不该和普通卡片一样安静。 */
.crisis::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(
    180deg,
    rgba(168, 58, 47, 0) 0%,
    rgba(168, 58, 47, 0.5) 50%,
    rgba(168, 58, 47, 0) 100%
  );
}

.cr-left {
  position: relative;
}

.cr-text {
  margin-top: 7px;
  font-size: 12.5px;
  color: var(--ink-3);
}

.cr-right {
  position: relative;
  display: flex;
  gap: 12px;
}

/* 热线号码做成能"抬起来"的小卡：紧急时手会抖，可点击的反馈必须给足 */
.hot {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 9px 15px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition:
    transform 0.22s var(--ease),
    border-color 0.22s var(--ease),
    box-shadow 0.22s var(--ease);
}

.hot:hover {
  transform: translateY(-2px);
  border-color: #e8d2ce;
  box-shadow: var(--lift);
}

.hot-name {
  font-size: 11.5px;
  color: var(--ink-3);
}

.hot-num {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--high);
}

/* ---------- 窄屏 ----------
   Bento 到窄屏必须塌回两列再从单列，否则 2×2 的主卡会被压成一条 */
@media (max-width: 1080px) {
  .home {
    padding: 22px 20px 44px;
  }

  .quicks {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quick.featured {
    grid-column: span 2;
    grid-row: span 1;
  }

  .cols,
  .stats {
    grid-template-columns: 1fr;
  }

  .hero,
  .crisis {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-right {
    text-align: left;
  }
}

@media (max-width: 720px) {
  .quicks {
    grid-template-columns: 1fr;
  }

  .quick.featured {
    grid-column: span 1;
  }

  .cr-right {
    flex-direction: column;
    width: 100%;
  }
}
</style>
