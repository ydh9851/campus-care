/**
 * 接口层。
 *
 * 后端的返回约定（见 Java 侧 GlobalExceptionHandler）：
 *   ① 401 / 403 使用【真实的 HTTP 状态码】，前端在拦截器里统一处理
 *   ② 其余错误统一 HTTP 200 + body 里的 code
 *        code: 200 成功 / 400 参数校验 / 1001 业务异常 / 500 系统异常
 *
 * 所以这里必须同时判断 res.status 和 data.code，少一个就会漏错。
 */

const TOKEN_KEY = 'campuscare.token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** 带 code 的业务错误，方便调用方按 code 分支处理 */
export class ApiError extends Error {
  constructor(message, code) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

/** 未登录时的回调，由 auth.js 注入（避免这里反向依赖路由） */
let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let res
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('无法连接后端服务，请确认 Java 服务已在 8080 启动', 0)
  }

  // 401：token 失效或被登出（后端删了 Redis 白名单）
  if (res.status === 401) {
    clearToken()
    onUnauthorized()
    throw new ApiError('登录已过期，请重新登录', 401)
  }
  if (res.status === 403) {
    throw new ApiError('没有权限访问该资源', 403)
  }

  const text = await res.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      throw new ApiError('服务端返回了非 JSON 内容', res.status)
    }
  }

  if (payload && payload.code !== 200) {
    throw new ApiError(payload.message || '请求失败', payload.code)
  }
  return payload ? payload.data : null
}

/* ---------------- 认证 ---------------- */
export const authApi = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password }, auth: false }),
  register: (form) => request('/auth/register', { method: 'POST', body: form, auth: false }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
}

/* ---------------- 咨询 ---------------- */
export const chatApi = {
  consult: (payload) => request('/chat/consult', { method: 'POST', body: payload }),
  conversations: () => request('/chat/conversations'),
  messages: (conversationId) => request(`/chat/conversations/${conversationId}/messages`),
}

/* ---------------- 风险预警（辅导员） ---------------- */
export const riskApi = {
  page: ({ current = 1, size = 10, status = '', riskLevel = '' } = {}) => {
    const qs = new URLSearchParams({ current, size })
    if (status) qs.set('status', status)
    if (riskLevel) qs.set('riskLevel', riskLevel)
    return request(`/risk/alerts?${qs}`)
  },
  handle: (alertId, remark) =>
    request(`/risk/alerts/${alertId}/handle`, { method: 'POST', body: { remark } }),
  statistics: () => request('/risk/alerts/statistics'),
}

/* ---------------- 咨询报告 ---------------- */
export const reportApi = {
  generate: (conversationId) =>
    request(`/report/${conversationId}`, { method: 'POST' }),
  get: (conversationId) => request(`/report/${conversationId}`),
}

/* ---------------- 心理测评 ---------------- */
export const assessmentApi = {
  scales: () => request('/assessment/scales'),
  scale: (code) => request(`/assessment/scales/${code}`),
  submit: (scaleCode, answers) =>
    request('/assessment/submit', { method: 'POST', body: { scaleCode, answers } }),
  records: () => request('/assessment/records'),
}

/* ---------------- 心理档案 ---------------- */
export const profileApi = {
  /** 我的档案 */
  me: () => request('/profile/me'),
  /** 查看某学生的档案（仅辅导员/管理员，学生调用会 403） */
  user: (userId) => request(`/profile/${userId}`),
}

/* ---------------- 数据看板（仅辅导员/管理员） ---------------- */
export const dashboardApi = {
  get: (days = 14, topLimit = 8) => request(`/dashboard?days=${days}&topLimit=${topLimit}`),
}

/* ================================================================
   SSE 流式咨询
   ================================================================ */

/**
 * 解析一个 SSE 帧（形如 "event:delta\ndata:{...}"）。
 *
 * 注意两点：
 *   1. 字符串方法是 "event:" 而不是 "event: "。按 SSE 规范，冒号后的空格是可选的，
 *      Spring 的 SseEmitter 就不加空格，所以一律 trim 后再用。
 *   2. 多行 data: 按规范应该用 \n 连接，但本协议每个事件只发一行 JSON，
 *      这里用 "" 连接可以避免把换行插进 JSON 里导致解析失败。
 */
function parseSseFrame(raw) {
  let event = 'message'
  const dataLines = []
  for (const line of raw.split('\n')) {
    const text = line.replace(/\r$/, '')
    if (text.startsWith('event:')) event = text.slice(6).trim()
    else if (text.startsWith('data:')) dataLines.push(text.slice(5).trim())
  }
  if (!dataLines.length) return null
  return { event, data: dataLines.join('') }
}

function safeJson(text) {
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

/**
 * 流式发咨询。
 *
 * 为什么用 fetch + ReadableStream，而不是浏览器原生的 EventSource？
 * 因为 EventSource 有两个硬限制：只能 GET、不能带自定义请求头。
 * 而我们需要 POST 请求体，还需要带 Authorization: Bearer <token>。
 * 所以自己读响应流、自己解析 SSE 帧。
 *
 * @param onEvent 回调 (eventName, payload)
 */
export async function consultStream(payload, { onEvent, signal } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch('/api/chat/consult/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError('无法连接后端服务，请确认 Java 服务已在 8080 启动', 0)
  }

  if (res.status === 401) {
    clearToken()
    onUnauthorized()
    throw new ApiError('登录已过期，请重新登录', 401)
  }
  if (res.status === 403) {
    throw new ApiError('没有权限访问该资源', 403)
  }
  if (!res.ok || !res.body) {
    throw new ApiError(`流式连接建立失败（HTTP ${res.status}）`, res.status)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 帧之间用空行分隔，可能一次读到多个帧，也可能只读到半个
    let cut
    while ((cut = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, cut)
      buffer = buffer.slice(cut + 2)
      const parsed = parseSseFrame(frame)
      if (parsed && onEvent) onEvent(parsed.event, safeJson(parsed.data))
    }
  }
}
