<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../auth'
import { authApi } from '../api'

const router = useRouter()
const route = useRoute()

const mode = ref('login') // login | register
const submitting = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
  realName: '',
  studentNo: '',
  phone: '',
  email: '',
})

const DEMO = [
  { username: 'student01', label: '学生' },
  { username: 'teacher01', label: '辅导员' },
]

function fill(username) {
  form.username = username
  form.password = '123456'
  error.value = ''
}

/** 注册页的字段校验，和后端 RegisterRequest 的注解保持一致 */
function validateRegister() {
  if (form.username.length < 4 || form.username.length > 20) return '账号长度需在 4-20 之间'
  if (form.password.length < 6 || form.password.length > 32) return '密码长度需在 6-32 之间'
  if (form.phone && !/^1[3-9]\d{9}$/.test(form.phone)) return '手机号格式不正确'
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) return '邮箱格式不正确'
  return ''
}

async function submit() {
  error.value = ''
  if (!form.username || !form.password) {
    error.value = '请填写账号和密码'
    return
  }
  if (mode.value === 'register') {
    const msg = validateRegister()
    if (msg) {
      error.value = msg
      return
    }
  }

  submitting.value = true
  try {
    if (mode.value === 'register') {
      await authApi.register({
        username: form.username,
        password: form.password,
        realName: form.realName || null,
        studentNo: form.studentNo || null,
        phone: form.phone || null,
        email: form.email || null,
      })
      ElMessage.success('注册成功，正在为你登录')
    }
    const user = await login(form.username, form.password)
    const target =
      route.query.redirect ||
      (user.role === 'COUNSELOR' || user.role === 'ADMIN' ? '/alerts' : '/chat')
    router.replace(target)
  } catch (e) {
    error.value = e.message || '操作失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login">
    <!-- 左侧：产品定位 -->
    <section class="intro">
      <div class="brand">
        <span class="mark" aria-hidden="true"></span>
        <span class="brand-name">CampusCare</span>
      </div>

      <div class="pitch">
        <h1>校园心理支持平台</h1>
        <p>
          学生自然语言倾诉，系统自动完成意图识别、知识库检索与风险研判；
          出现高危表达时生成辅导员工单，并附上危机干预资源。
        </p>
      </div>

      <ol class="points">
        <li>
          <span class="idx">01</span>
          <div>
            <b>多 Agent 编排</b>
            <span>意图识别、知识检索、风险预警、回复生成四节点由 LangGraph 串联</span>
          </div>
        </li>
        <li>
          <span class="idx">02</span>
          <div>
            <b>知识库检索</b>
            <span>24 条校园心理 FAQ 入库 ChromaDB，回复带出处与相似度</span>
          </div>
        </li>
        <li>
          <span class="idx">03</span>
          <div>
            <b>危机识别</b>
            <span>规则优先判定风险等级，会话风险只升不降，工单可追踪处置</span>
          </div>
        </li>
        </ol>

        <div class="foot">仅供校园心理健康教育中心内部使用</div>
        </section>

    <!-- 右侧：表单 -->
    <section class="form-side">
      <div class="box">
        <div class="tabs">
          <button type="button" :class="{ on: mode === 'login' }" @click="mode = 'login'; error = ''">
            登录
          </button>
          <button type="button" :class="{ on: mode === 'register' }" @click="mode = 'register'; error = ''">
            注册
          </button>
        </div>

        <form @submit.prevent="submit">
          <label class="field">
            <span>账号</span>
            <input v-model.trim="form.username" autocomplete="username" placeholder="学号或工号" />
          </label>

          <label class="field">
            <span>密码</span>
            <input
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              placeholder="6-32 位"
            />
          </label>

          <template v-if="mode === 'register'">
            <div class="row">
              <label class="field">
                <span>姓名</span>
                <input v-model.trim="form.realName" placeholder="选填" />
              </label>
              <label class="field">
                <span>学号</span>
                <input v-model.trim="form.studentNo" placeholder="选填" />
              </label>
            </div>
            <div class="row">
              <label class="field">
                <span>手机</span>
                <input v-model.trim="form.phone" placeholder="选填" />
              </label>
              <label class="field">
                <span>邮箱</span>
                <input v-model.trim="form.email" placeholder="选填" />
              </label>
            </div>
          </template>

          <p v-if="error" class="err">{{ error }}</p>

          <button class="primary" type="submit" :disabled="submitting">
            {{ submitting ? '处理中…' : mode === 'login' ? '登录' : '注册并登录' }}
          </button>
        </form>

        <div class="demo">
          <span class="caption">测试账号</span>
          <div class="demo-items">
            <button
              v-for="d in DEMO"
              :key="d.username"
              type="button"
              @click="fill(d.username)"
            >
              {{ d.label }} <code>{{ d.username }}</code>
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  height: 100%;
  background: var(--panel);
}

/* ---------- 左 ---------- */
.intro {
  width: 52%;
  max-width: 640px;
  padding: 48px 56px;
  display: flex;
  flex-direction: column;
  background: var(--ink);
  color: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mark {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: #6fae9c;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.pitch {
  margin-top: auto;
  padding-top: 40px;
}

.pitch h1 {
  font-size: 30px;
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.3;
}

.pitch p {
  margin-top: 14px;
  max-width: 30em;
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.62);
}

.points {
  margin: 40px 0 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.points li {
  display: flex;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.idx {
  font-family: var(--mono);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.38);
  padding-top: 2px;
}

.points b {
  display: block;
  font-size: 13px;
  font-weight: 500;
}

.points div span {
  font-size: 12.5px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.5);
}

.foot {
  margin-top: auto;
  padding-top: 32px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.32);
}

/* ---------- 右 ---------- */
.form-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  background: var(--panel);
}

.box {
  width: 100%;
  max-width: 340px;
}

.tabs {
  display: flex;
  gap: 20px;
  margin-bottom: 28px;
}

.tabs button {
  padding: 0 0 6px;
  border: none;
  background: none;
  font-size: 15px;
  color: var(--ink-3);
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tabs button.on {
  color: var(--ink);
  font-weight: 500;
  border-bottom-color: var(--brand);
}

.field {
  display: block;
  margin-bottom: 16px;
  flex: 1;
  min-width: 0;
}

.field > span {
  display: block;
  margin-bottom: 6px;
  font-size: 12.5px;
  color: var(--ink-2);
}

.field input {
  width: 100%;
  height: 38px;
  padding: 0 12px;
  font-size: 14px;
  font-family: inherit;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line-2);
  border-radius: var(--radius);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.field input::placeholder {
  color: var(--ink-4);
}

.field input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-bg);
}

.row {
  display: flex;
  gap: 12px;
}

.err {
  margin: 4px 0 12px;
  font-size: 12.5px;
  color: var(--high);
}

.primary {
  width: 100%;
  height: 40px;
  margin-top: 8px;
  border: none;
  border-radius: var(--radius);
  background: var(--brand);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.primary:hover:not(:disabled) {
  background: var(--brand-ink);
}

.primary:disabled {
  opacity: 0.6;
  cursor: default;
}

.demo {
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.demo-items {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}

.demo-items button {
  border: none;
  background: none;
  padding: 0;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
}

.demo-items button:hover {
  color: var(--brand);
}

.demo-items code {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--ink-3);
}

@media (max-width: 900px) {
  .intro {
    display: none;
  }
}
</style>
