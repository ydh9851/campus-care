<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { knowledgeApi } from '../api'
import AppIcon from '../components/AppIcon.vue'

const items = ref([])
const categories = ref([])
const activeCat = ref('全部')
const keyword = ref('')
const loading = ref(false)
const opened = ref(null)

const total = computed(() => categories.value.reduce((sum, c) => sum + c.count, 0))

/* 分类图标。
   分类名是后端给的数据，不该在前端写死一张"名称 → 图标"的表，
   否则将来后端加一个分类，前端就会出现没有图标的白块。
   这里按分类在列表中的下标循环取图标，分类增减时图标自动跟着走。 */
const ICON_CYCLE = ['sparkles', 'clock', 'user', 'book', 'chat', 'shield', 'trend']
function catIcon(name) {
  const i = categories.value.findIndex((c) => c.name === name)
  return ICON_CYCLE[(i < 0 ? 0 : i) % ICON_CYCLE.length]
}

/** 分类标签：全部 + 后端返回的分类（带条数） */
const tabs = computed(() => [
  { name: '全部', count: total.value },
  ...categories.value,
])

const isEmpty = computed(() => !loading.value && items.value.length === 0)

async function load() {
  loading.value = true
  try {
    items.value = (await knowledgeApi.list(activeCat.value, keyword.value)) || []
  } catch (e) {
    ElMessage.error(e.message)
    items.value = []
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    categories.value = (await knowledgeApi.categories()) || []
  } catch {
    categories.value = []
  }
}

function pickCategory(name) {
  activeCat.value = name
}

/** 列表按当前摘要截断，详情弹层里看全文 —— 卡片高度才能一致。
 *  按「字」截断而不是按码元：slice 会把代理对（emoji、生僻字）切成两半，
 *  摘要末尾就会多出一个「乱码方块」。 */
function summary(text) {
  const s = (text || '').replace(/\s+/g, '')
  const chars = [...s]
  return chars.length > 68 ? `${chars.slice(0, 68).join('')}…` : s
}

function onSearch() {
  load()
}

// 防抖：Search 组件在输入过程中也会触发，300ms 内的连续输入只发一次请求
let timer = null
watch(keyword, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
})

watch(activeCat, load)

onMounted(() => {
  loadCategories()
  load()
})
</script>

<template>
  <div class="knowledge">
    <div class="page-head">
      <div>
        <div class="sec-head">
          <span class="chip sm"><AppIcon name="book" :size="14" /></span>
          <span class="caption">心理科普</span>
        </div>
        <h1>了解多一点，慌乱少一点</h1>
        <p class="hint lead">
          内容为通用心理健康科普整理，供了解与自助参考，<b>不构成医学诊断</b>。
          如果困扰持续存在，请预约校心理中心面询。
        </p>
      </div>
      <el-input
        v-model="keyword"
        class="search"
        placeholder="搜索困扰、情绪、人际关系…"
        clearable
        @keyup.enter="onSearch"
      />
    </div>

    <div class="tabs">
      <button
        v-for="t in tabs"
        :key="t.name"
        type="button"
        class="tab"
        :class="{ on: activeCat === t.name }"
        @click="pickCategory(t.name)"
      >
        {{ t.name }}
        <span class="tab-n num">{{ t.count }}</span>
      </button>
    </div>

    <div v-if="isEmpty" class="blank">
      <p>没有匹配的内容</p>
      <button type="button" class="link-btn" @click="pickCategory('全部'); keyword = ''">
        清空筛选条件
      </button>
    </div>

    <div v-else class="cards">
      <button
        v-for="(item, i) in items"
        :key="item.id"
        v-spotlight
        v-reveal="i % 4"
        type="button"
        class="card tile"
        @click="opened = item"
      >
        <span class="c-top">
          <span class="chip"><AppIcon :name="catIcon(item.category)" :size="17" /></span>
          <span class="c-cat">{{ item.category }}</span>
        </span>
        <span class="c-title">{{ item.title }}</span>
        <span class="c-text">{{ summary(item.content) }}</span>
        <span class="c-foot">
          <span class="c-src">{{ item.source }}</span>
          <span class="c-more">
            展开
            <AppIcon name="arrow" :size="13" />
          </span>
        </span>
      </button>
    </div>

    <!-- 详情：卡片里只放摘要，全文在这里读，避免网格被长短不一的内容撑乱 -->
    <el-dialog v-model="opened" :show-close="false" width="640px" class="kb-dialog" align-center>
      <template #header>
        <div class="d-head">
          <span class="c-cat">{{ opened?.category }}</span>
          <h2>{{ opened?.title }}</h2>
        </div>
      </template>
      <p class="d-body">{{ opened?.content }}</p>
      <p class="d-src">出处：{{ opened?.source }}</p>
      <template #footer>
        <button type="button" class="ghost-btn" @click="opened = null">关闭</button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.knowledge {
  height: 100%;
  overflow-y: auto;
  /* 超宽屏收窄内容，但滚动条仍贴窗口右缘（用 max-width 会把它顶到屏幕中间） */
  padding: 28px max(32px, calc((100% - 1340px) / 2)) 48px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
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

.lead {
  max-width: 620px;
  margin-top: 8px;
  line-height: 1.8;
}

.search {
  flex: none;
  width: 260px;
  padding-top: 18px;
}

/* ---------- 分类标签 ---------- */
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 22px;
}

.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 31px;
  padding: 0 13px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  transition:
    transform 0.18s var(--ease),
    border-color 0.18s var(--ease),
    color 0.18s var(--ease),
    background-color 0.18s var(--ease),
    box-shadow 0.18s var(--ease);
}

.tab:hover {
  transform: translateY(-1px);
  border-color: var(--brand-line);
  color: var(--brand);
  box-shadow: 0 6px 14px -9px rgba(44, 95, 82, 0.55);
}

/* 选中态走品牌渐变而不是纯色。纯色在浅色页上是一块"死色"，
   渐变才有一点体积感，也和按钮、图标块用的是同一支渐变。 */
.tab.on {
  background: var(--brand-grad);
  border-color: transparent;
  color: #fff;
  box-shadow: var(--glow);
}

.tab-n {
  font-size: 11px;
  color: var(--ink-4);
}

.tab.on .tab-n {
  color: rgba(255, 255, 255, 0.75);
}

/* ---------- 卡片网格 ---------- */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: 14px;
  margin-top: 20px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 18px;
  min-height: 188px;
  text-align: left;
  background: var(--panel-grad);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 2px rgba(20, 22, 26, 0.025);
  cursor: pointer;
  /* 抬起、染色、描边光晕、图标块翻实心 —— 统一交给全局的 .tile */
}

/* 图标块 + 分类标签并排：图标说"这条讲什么"，标签说"属于哪一类" */
.c-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.c-cat {
  font-size: 11px;
  color: var(--brand);
  background: var(--brand-bg);
  border: 1px solid var(--brand-line);
  border-radius: 3px;
  padding: 1px 6px;
}

.c-title {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.5;
  color: var(--ink);
}

.c-text {
  flex: 1;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--ink-3);
}

.c-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 11px;
  border-top: 1px solid var(--line);
}

.c-src {
  font-size: 11.5px;
  color: var(--ink-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.c-more {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex: none;
  font-size: 12px;
  color: var(--brand);
  transition: transform 0.24s var(--ease);
}

.card:hover .c-more {
  transform: translateX(3px);
}

/* ---------- 空状态 ---------- */
.blank {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 220px;
  color: var(--ink-3);
  font-size: 13px;
}

.link-btn {
  border: none;
  background: none;
  padding: 0;
  font-size: 13px;
  color: var(--brand);
  cursor: pointer;
}

/* ---------- 详情弹层 ---------- */
.d-head h2 {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 500;
  line-height: 1.5;
}

.d-body {
  font-size: 14px;
  line-height: 1.95;
  color: var(--ink-2);
}

.d-src {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--ink-4);
}

.ghost-btn {
  border: 1px solid var(--line-2);
  background: var(--panel);
  border-radius: var(--radius);
  height: 32px;
  padding: 0 18px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
}

.ghost-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
}
</style>
