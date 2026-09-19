<script setup>
import { reactive, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BrandMark from '../components/BrandMark.vue'
import CaptchaCanvas from '../components/CaptchaCanvas.vue'
import SlideVerify from '../components/SlideVerify.vue'
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
  confirmPassword: '',
  realName: '',
  studentNo: '',
  phone: '',
  email: '',
  smsCode: '',
  agree: false,
})

const captchaCode = ref('')
const captchaInput = ref('')
const captchaRef = ref(null)

const slidePassed = ref(false)
const slideRef = ref(null)

const phoneError = ref('')
const smsCountdown = ref(0)

const DEMO = [
  { username: 'student01', label: '学生' },
  { username: 'teacher01', label: '辅导员' },
]

/* ---------------- 工具 ---------------- */
function fill(username) {
  form.username = username
  form.password = '123456'
  error.value = ''
}

function resetVerify() {
  slidePassed.value = false
  slideRef.value?.reset()
  captchaInput.value = ''
  captchaRef.value?.refresh()
}

watch(mode, () => {
  error.value = ''
  phoneError.value = ''
  resetVerify()
})

/* ---------------- 校验 ---------------- */
function validatePhone(v) {
  if (!v) return ''
  if (!/^1[3-9]\d{9}$/.test(v)) return '手机号格式不正确，请输入 11 位有效号码'
  return ''
}

watch(() => form.phone, (v) => {
  phoneError.value = validatePhone(v)
})

function validateRegister() {
  if (form.username.length < 4 || form.username.length > 20) return '账号长度需在 4-20 之间'
  if (form.password.length < 6 || form.password.length > 32) return '密码长度需在 6-32 之间'
  if (form.confirmPassword !== form.password) return '两次输入的密码不一致'
  if (form.phone && phoneError.value) return phoneError.value
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) return '邮箱格式不正确'
  if (!form.agree) return '请阅读并同意用户协议与隐私政策'
  return ''
}

function validateLogin() {
  if (!form.username || !form.password) return '请填写账号和密码'
  if (!captchaInput.value) return '请输入图形验证码'
  if (captchaInput.value.toLowerCase() !== captchaCode.value.toLowerCase()) return '图形验证码错误，请重新输入'
  if (!slidePassed.value) return '请完成滑块验证'
  return ''
}

/* ---------------- 短信倒计时（UI 占位，无真实接口） ---------------- */
function sendSms() {
  if (smsCountdown.value > 0) return
  const pe = validatePhone(form.phone)
  if (pe) {
    phoneError.value = pe
    error.value = pe
    return
  }
  smsCountdown.value = 60
  error.value = ''
  const timer = setInterval(() => {
    smsCountdown.value--
    if (smsCountdown.value <= 0) clearInterval(timer)
  }, 1000)
  // TODO: 接入真实短信接口
  ElMessage.info('验证码已发送至 ' + form.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2'))
}

/* ---------------- 提交 ---------------- */
async function submit() {
  error.value = ''

  if (mode.value === 'login') {
    const msg = validateLogin()
    if (msg) {
      error.value = msg
      return
    }
  } else {
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
    await login(form.username, form.password)
    router.replace(route.query.redirect || '/home')
  } catch (e) {
    let msg = e?.message || ''
    // 把各种底层英文报错统一翻译成中文
    if (
      msg.includes('null') ||
      msg.includes('undefined') ||
      msg.includes('Cannot read') ||
      msg.includes('is not') ||
      msg.includes('of null')
    ) {
      msg = '登录异常，请检查网络连接或联系管理员'
    }
    error.value = msg || '操作失败，请稍后重试'
    // 验证失败时重置图形验证码，滑块保持（避免太烦）
    if (mode.value === 'login') {
      captchaRef.value?.refresh()
      captchaInput.value = ''
    }
  } finally {
    submitting.value = false
  }
}

/* ---------------- FAQ ---------------- */
const faqOpen = ref(false)
const faqs = [
  {
    q: '忘记密码怎么办？',
    a: '请联系学校心理健康教育中心（电话：010-12345678）或辅导员重置密码。目前暂不支持在线找回。',
  },
  {
    q: '收不到短信验证码？',
    a: '请确认手机号填写正确；检查是否被手机管家拦截；如仍无法收到，请联系管理员人工处理。',
  },
  {
    q: '账号被锁定？',
    a: '连续 5 次输入错误密码后账号将锁定 15 分钟。请稍后再试，或使用测试账号体验。',
  },
  {
    q: '我是新生，如何注册？',
    a: '新生请使用学号作为账号直接注册。注册后默认角色为学生，辅导员账号由管理员统一分配。',
  },
]
const activeFaq = ref(-1)
</script>

<template>
  <div class="login">
    <!-- ==================== 左侧：品牌区 ==================== -->
    <section class="intro">
      <div class="aura" aria-hidden="true">
        <span class="blob b1"></span>
        <span class="blob b2"></span>
        <span class="blob b3"></span>
      </div>
      <div class="dots" aria-hidden="true"></div>

      <div class="intro-inner">
        <div class="brand rise" style="--i: 0">
          <span class="brand-logo">
            <span class="brand-halo" aria-hidden="true"></span>
            <BrandMark :size="56" />
          </span>
          <span class="brand-text">
            <span class="brand-name">CampusCare</span>
            <span class="brand-sub">校园心理支持平台</span>
          </span>
        </div>

        <div class="pitch rise" style="--i: 1">
          <h1>让每一次<br />说不出口，都被接住</h1>
          <p>
            学生用自然语言倾诉，系统自动完成意图识别、知识库检索与风险研判；
            出现高危表达时生成辅导员工单，并附上危机干预资源。
          </p>
        </div>

        <ol class="points">
          <li class="rise" style="--i: 2">
            <span class="idx num">01</span>
            <span class="p-body">
              <b>多 Agent 编排</b>
              <span>意图识别、知识检索、风险预警、回复生成四节点由 LangGraph 串联</span>
            </span>
          </li>
          <li class="rise" style="--i: 3">
            <span class="idx num">02</span>
            <span class="p-body">
              <b>语义检索</b>
              <span>105 条校园心理语料入库 ChromaDB，用 BGE 向量召回并附出处</span>
            </span>
          </li>
          <li class="rise" style="--i: 4">
            <span class="idx num">03</span>
            <span class="p-body">
              <b>危机识别</b>
              <span>规则优先判定风险等级，会话风险只升不降，工单可追踪处置</span>
            </span>
          </li>
        </ol>

        <div class="foot">仅供校园心理健康教育中心内部使用</div>
      </div>
    </section>

    <!-- ==================== 右侧：表单 ==================== -->
    <section class="form-side">
      <div class="right-stack">
        <!-- 欢迎横幅 -->
        <div class="welcome-banner rise">
          <div class="w-emoji" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path>
              <path d="M8 14s1.5 2 4 2 4-2 4-2"></path>
              <line x1="9" y1="9" x2="9.01" y2="9"></line>
              <line x1="15" y1="9" x2="15.01" y2="9"></line>
            </svg>
          </div>
          <div class="w-text">
            <b>{{ mode === 'login' ? '欢迎回来' : '创建新账号' }}</b>
            <span>{{ mode === 'login' ? '登录以继续你的心理健康之旅' : '填写以下信息完成注册' }}</span>
          </div>
        </div>

        <div class="box rise">
          <div class="tabs">
            <button
              type="button"
              :class="{ on: mode === 'login' }"
              @click="mode = 'login'; error = ''"
            >
              登录
            </button>
            <button
              type="button"
              :class="{ on: mode === 'register' }"
              @click="mode = 'register'; error = ''"
            >
              注册
            </button>
          </div>

          <form @submit.prevent="submit">
            <!-- 账号 -->
            <label class="field">
              <span>账号</span>
              <input v-model.trim="form.username" autocomplete="username" placeholder="学号或工号" />
            </label>

            <!-- 密码 -->
            <label class="field">
              <span>密码</span>
              <input
                v-model="form.password"
                type="password"
                autocomplete="current-password"
                placeholder="6-32 位"
              />
            </label>

            <!-- 注册专属：确认密码 -->
            <label v-if="mode === 'register'" class="field">
              <span>确认密码</span>
              <input
                v-model="form.confirmPassword"
                type="password"
                autocomplete="new-password"
                placeholder="再次输入密码"
              />
            </label>

            <!-- 注册专属：姓名 / 学号 -->
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
            </template>

            <!-- 登录专属：图形验证码 -->
            <template v-if="mode === 'login'">
              <div class="field captcha-row">
                <span>图形验证码</span>
                <div class="captcha-line">
                  <input
                    v-model.trim="captchaInput"
                    placeholder="输入右侧验证码"
                    maxlength="6"
                    class="captcha-input"
                  />
                  <CaptchaCanvas
                    ref="captchaRef"
                    :width="100"
                    :height="38"
                    @change="(v) => (captchaCode = v)"
                  />
                </div>
              </div>

              <!-- 滑块验证 -->
              <div class="field slide-row">
                <span>安全验证</span>
                <SlideVerify
                  ref="slideRef"
                  :width="280"
                  :height="36"
                  @success="slidePassed = true"
                  @fail="slidePassed = false"
                />
              </div>
            </template>

            <!-- 注册专属：手机 / 邮箱 / 短信验证码 -->
            <template v-if="mode === 'register'">
              <div class="row">
                <label class="field" :class="{ invalid: phoneError }">
                  <span>手机</span>
                  <input
                    v-model.trim="form.phone"
                    placeholder="11 位手机号"
                    maxlength="11"
                    inputmode="numeric"
                  />
                  <span v-if="phoneError" class="field-hint">{{ phoneError }}</span>
                </label>
                <label class="field">
                  <span>邮箱</span>
                  <input v-model.trim="form.email" placeholder="选填" />
                </label>
              </div>

              <div class="field sms-row">
                <span>短信验证码</span>
                <div class="sms-line">
                  <input
                    v-model.trim="form.smsCode"
                    placeholder="6 位验证码"
                    maxlength="6"
                    inputmode="numeric"
                  />
                  <button
                    type="button"
                    class="sms-btn"
                    :disabled="smsCountdown > 0 || !form.phone"
                    @click="sendSms"
                  >
                    {{ smsCountdown > 0 ? `${smsCountdown}s 后重发` : '获取验证码' }}
                  </button>
                </div>
              </div>

              <label class="agree">
                <input v-model="form.agree" type="checkbox" />
                <span>
                  我已阅读并同意
                  <a href="#" @click.prevent>《用户协议》</a>
                  与
                  <a href="#" @click.prevent>《隐私政策》</a>
                </span>
              </label>
            </template>

            <!-- 错误提示 -->
            <p v-if="error" class="err">{{ error }}</p>

            <button class="primary" type="submit" :disabled="submitting">
              <span class="spinner" v-if="submitting" aria-hidden="true"></span>
              {{ submitting ? '处理中…' : mode === 'login' ? '登录' : '注册并登录' }}
            </button>
          </form>

          <!-- 测试账号 -->
          <div class="demo">
            <span class="caption">测试账号（点击自动填充）</span>
            <div class="demo-items">
              <button
                v-for="d in DEMO"
                :key="d.username"
                type="button"
                @click="fill(d.username)"
              >
                {{ d.label }}<code>{{ d.username }}</code>
              </button>
            </div>
          </div>
        </div>

        <!-- FAQ 折叠 -->
        <div class="faq-box rise">
          <button type="button" class="faq-toggle" @click="faqOpen = !faqOpen">
            <span>常见问题与帮助</span>
            <svg
              width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              :style="{ transform: faqOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.25s var(--ease)' }"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <div v-show="faqOpen" class="faq-list">
            <div
              v-for="(item, i) in faqs"
              :key="i"
              class="faq-item"
              :class="{ open: activeFaq === i }"
            >
              <button type="button" class="faq-q" @click="activeFaq = activeFaq === i ? -1 : i">
                <span>{{ item.q }}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
              <div v-show="activeFaq === i" class="faq-a">{{ item.a }}</div>
            </div>
          </div>
        </div>

        <!-- 安全提示 -->
        <div class="safety-tip rise">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          </svg>
          <span>本平台数据仅供校园心理健康教育中心内部使用，严格遵循隐私保护规范</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ==================== 左侧品牌区 ==================== */
.intro {
  position: relative;
  width: 52%;
  max-width: 660px;
  padding: 52px 56px 44px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(160deg, #1b3a32 0%, #10241f 56%, #0b1916 100%);
  color: #fff;
}

.aura {
  position: absolute;
  inset: -10%;
  pointer-events: none;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(64px);
  animation: drift 22s var(--ease) infinite;
}

.b1 {
  width: 420px;
  height: 420px;
  top: -120px;
  left: -110px;
  background: rgba(44, 95, 82, 0.75);
}

.b2 {
  width: 340px;
  height: 340px;
  right: -90px;
  bottom: -120px;
  background: rgba(111, 174, 156, 0.34);
  animation-duration: 28s;
  animation-delay: -8s;
}

.b3 {
  width: 260px;
  height: 260px;
  top: 44%;
  left: 52%;
  background: rgba(44, 95, 82, 0.4);
  animation-duration: 34s;
  animation-delay: -16s;
}

.dots {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: radial-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 24px 24px;
  -webkit-mask-image: radial-gradient(78% 66% at 32% 34%, #000 18%, transparent 74%);
  mask-image: radial-gradient(78% 66% at 32% 34%, #000 18%, transparent 74%);
}

.intro-inner {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ---------- 品牌 ---------- */
.brand {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand-logo {
  position: relative;
  display: inline-flex;
  color: #d9ece6;
}

.brand-halo {
  position: absolute;
  inset: -16px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(126, 190, 173, 0.32) 0%, rgba(126, 190, 173, 0) 68%);
  animation: breathe 5.5s var(--ease) infinite;
  pointer-events: none;
}

@keyframes breathe {
  0%, 100% { transform: scale(0.9); opacity: 0.5; }
  50% { transform: scale(1.14); opacity: 0.95; }
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-name {
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.05;
  background: linear-gradient(180deg, #ffffff 28%, #c9e0d9 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.brand-sub {
  font-size: 11.5px;
  letter-spacing: 0.2em;
  color: rgba(255, 255, 255, 0.42);
}

/* ---------- 标题 ---------- */
.pitch {
  margin-top: auto;
  padding-top: 56px;
}

.pitch h1 {
  font-size: 38px;
  font-weight: 600;
  letter-spacing: -0.028em;
  line-height: 1.32;
  background: linear-gradient(178deg, #ffffff 24%, rgba(255, 255, 255, 0.72) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.pitch p {
  margin-top: 18px;
  max-width: 30em;
  font-size: 13.5px;
  line-height: 1.85;
  color: rgba(255, 255, 255, 0.56);
}

/* ---------- 特性列表 ---------- */
.points {
  margin: 40px 0 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.points li {
  display: flex;
  gap: 16px;
  padding: 15px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: padding-left 0.24s var(--ease);
}

.points li:hover {
  padding-left: 6px;
}

.idx {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.34);
  padding-top: 2px;
  transition: color 0.24s var(--ease);
}

.points li:hover .idx {
  color: #7fbfae;
}

.p-body b {
  display: block;
  font-size: 13px;
  font-weight: 500;
}

.p-body span {
  font-size: 12.5px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.48);
}

.foot {
  margin-top: auto;
  padding-top: 30px;
  font-size: 11.5px;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.28);
}

/* ==================== 右侧表单区 ==================== */
.form-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  background:
    radial-gradient(760px 460px at 82% 6%, var(--brand-soft) 0%, rgba(233, 242, 239, 0) 62%),
    var(--panel);
  overflow-y: auto;
}

.right-stack {
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---------- 欢迎横幅 ---------- */
.welcome-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--lift);
}

.w-emoji {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--brand-soft);
  color: var(--brand);
}

.w-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.w-text b {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--ink);
}

.w-text span {
  font-size: 12px;
  color: var(--ink-3);
}

/* ---------- 表单卡片 ---------- */
.box {
  width: 100%;
  padding: 28px 26px 24px;
  background: rgba(255, 255, 255, 0.74);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--lift);
}

/* 登录 / 注册 切换 */
.tabs {
  display: flex;
  gap: 22px;
  margin-bottom: 22px;
}

.tabs button {
  position: relative;
  padding: 0 0 7px;
  border: none;
  background: none;
  font-size: 15px;
  color: var(--ink-3);
  cursor: pointer;
  transition: color 0.18s var(--ease);
}

.tabs button::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  border-radius: 1px;
  background: var(--brand);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.26s var(--ease-out);
}

.tabs button:hover {
  color: var(--ink-2);
}

.tabs button.on {
  color: var(--ink);
  font-weight: 500;
}

.tabs button.on::after {
  transform: scaleX(1);
}

/* ---------- 输入框 ---------- */
.field {
  display: block;
  margin-bottom: 14px;
  flex: 1;
  min-width: 0;
}

.field > span:first-child {
  display: block;
  margin-bottom: 6px;
  font-size: 12.5px;
  color: var(--ink-2);
}

.field input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  font-size: 14px;
  font-family: inherit;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line-2);
  border-radius: var(--radius);
  outline: none;
  transition:
    border-color 0.18s var(--ease),
    box-shadow 0.18s var(--ease),
    background-color 0.18s var(--ease);
}

.field input::placeholder {
  color: var(--ink-4);
}

.field input:hover {
  border-color: var(--ink-4);
}

.field input:focus {
  border-color: var(--brand);
  background: #fff;
  box-shadow: 0 0 0 3.5px rgba(44, 95, 82, 0.12);
}

.field.invalid input {
  border-color: var(--high);
  background: #fff8f7;
  box-shadow: 0 0 0 3px rgba(168, 58, 47, 0.08);
}

.field-hint {
  display: block;
  margin-top: 5px;
  font-size: 11.5px;
  color: var(--high);
}

.row {
  display: flex;
  gap: 12px;
}

/* ---------- 验证码行 ---------- */
.captcha-row {
  margin-bottom: 14px;
}

.captcha-line {
  display: flex;
  gap: 10px;
  align-items: center;
}

.captcha-input {
  flex: 1;
}

/* ---------- 滑块行 ---------- */
.slide-row {
  margin-bottom: 14px;
}

/* ---------- 短信验证码 ---------- */
.sms-row {
  margin-bottom: 14px;
}

.sms-line {
  display: flex;
  gap: 10px;
}

.sms-line input {
  flex: 1;
}

.sms-btn {
  flex: none;
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--line-2);
  border-radius: var(--radius);
  background: var(--panel);
  font-size: 12.5px;
  color: var(--brand);
  cursor: pointer;
  transition: all 0.18s var(--ease);
  white-space: nowrap;
}

.sms-btn:hover:not(:disabled) {
  border-color: var(--brand);
  background: var(--brand-soft);
}

.sms-btn:disabled {
  color: var(--ink-4);
  cursor: default;
}

/* ---------- 用户协议 ---------- */
.agree {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 2px 0 14px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-3);
  cursor: pointer;
}

.agree input {
  margin-top: 2px;
  accent-color: var(--brand);
}

.agree a {
  color: var(--brand);
  text-decoration: none;
  transition: opacity 0.18s var(--ease);
}

.agree a:hover {
  opacity: 0.8;
  text-decoration: underline;
}

/* ---------- 错误提示 ---------- */
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-4px); }
  40% { transform: translateX(4px); }
  60% { transform: translateX(-2px); }
  80% { transform: translateX(2px); }
}

.err {
  margin: 2px 0 12px;
  font-size: 12.5px;
  color: var(--high);
  animation: shake 0.36s var(--ease);
}

/* ---------- 主按钮 ---------- */
.primary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 42px;
  margin-top: 6px;
  border: none;
  border-radius: var(--radius);
  background: linear-gradient(180deg, #35695b 0%, var(--brand) 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--glow), inset 0 1px 0 rgba(255, 255, 255, 0.13);
  transition:
    transform 0.18s var(--ease),
    box-shadow 0.22s var(--ease),
    filter 0.18s var(--ease);
}

.primary:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.07);
  box-shadow: var(--lift), var(--glow);
}

.primary:active:not(:disabled) {
  transform: translateY(0);
  filter: brightness(0.98);
}

.primary:disabled {
  opacity: 0.72;
  cursor: default;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner {
  width: 13px;
  height: 13px;
  border: 1.6px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* ---------- 测试账号 ---------- */
.demo {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.demo-items {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.demo-items button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line-2);
  border-radius: 15px;
  background: var(--panel);
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
  transition:
    transform 0.18s var(--ease),
    border-color 0.18s var(--ease),
    color 0.18s var(--ease),
    box-shadow 0.18s var(--ease);
}

.demo-items button:hover {
  transform: translateY(-1px);
  border-color: var(--brand);
  color: var(--brand);
  box-shadow: 0 8px 16px -10px rgba(44, 95, 82, 0.6);
}

.demo-items code {
  font-family: var(--mono);
  font-size: 11.5px;
  color: var(--ink-3);
  transition: color 0.18s var(--ease);
}

.demo-items button:hover code {
  color: var(--brand);
}

/* ---------- FAQ ---------- */
.faq-box {
  width: 100%;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--lift);
}

.faq-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2);
  cursor: pointer;
}

.faq-list {
  margin-top: 10px;
  border-top: 1px solid var(--line);
  padding-top: 8px;
}

.faq-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.faq-q {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 0;
  border: none;
  background: none;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
  text-align: left;
  transition: color 0.18s var(--ease);
}

.faq-q:hover {
  color: var(--brand);
}

.faq-q svg {
  flex: none;
  transition: transform 0.2s var(--ease);
}

.faq-item.open .faq-q svg {
  transform: rotate(45deg);
}

.faq-a {
  padding: 0 0 10px;
  font-size: 12px;
  line-height: 1.75;
  color: var(--ink-3);
}

/* ---------- 安全提示 ---------- */
.safety-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--ink-4);
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid var(--line);
  border-radius: 10px;
}

.safety-tip svg {
  flex: none;
  color: var(--brand);
  opacity: 0.7;
}

/* ---------- 窄屏 ---------- */
@media (max-width: 900px) {
  .intro {
    display: none;
  }
  .form-side {
    padding: 24px 18px;
  }
  .right-stack {
    max-width: 100%;
  }
}
</style>
