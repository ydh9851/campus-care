# 接口清单

所有接口统一返回：

```json
{ "code": 200, "message": "success", "data": {} }
```

`code` 约定：`200` 成功 · `400` 参数错误 · `401` 未登录 · `403` 无权限 · `500` 服务端异常 · `1001` 业务异常。

状态码约定：`401` / `403` 使用真实 HTTP 状态码，其余错误返回 HTTP 200 并在 body 中给出 `code`。前端可直接在拦截器里处理 401 跳登录页。

需要鉴权的接口在请求头带 `Authorization: Bearer <token>`。

---

## 一、认证 `/api/auth`

### POST /api/auth/register

注册学生账号。公开接口。

```json
{ "username": "stu1001", "password": "123456", "realName": "张三", "studentNo": "20240101", "phone": "13800000000", "email": "stu1001@campus.edu.cn" }
```

`username` 4-20 位，`password` 6-32 位，后四项选填。

### POST /api/auth/login

```json
{ "username": "student01", "password": "123456" }
```

响应 `data`：`token` / `userId` / `username` / `realName` / `role`。

登录成功后 token 会写入 Redis（`campuscare:login:token:{userId}`），TTL 与 token 有效期一致。同一账号再次登录会覆盖，旧 token 立即失效。

### POST /api/auth/logout

删除 Redis 中的 token，token 立即失效。需登录。

### GET /api/auth/me

返回当前登录用户，不含密码。需登录。

---

## 二、咨询 `/api/chat`

### POST /api/chat/consult

发起一轮咨询（一次性返回，等 AI 全部生成完）。

```json
{ "conversationId": 1, "content": "最近考试压力很大，晚上睡不着" }
```

`conversationId` 为空则新建会话，标题取首条消息前 20 字。

响应 `data`：

| 字段 | 说明 |
|---|---|
| `conversationId` | 会话 id |
| `reply` | AI 回复全文 |
| `intent` | `PSYCH_EMOTION` / `KNOWLEDGE_QUERY` / `RISK_ALERT` / `CHITCHAT` |
| `riskLevel` | `LOW` / `MEDIUM` / `HIGH` |
| `alertId` | 生成的风险工单 id，未达建单门槛时该字段不返回 |
| `ragSources` | 检索到的 FAQ 标题列表，带相似度 |
| `tokens` | 本轮消耗 token |

### POST /api/chat/consult/stream

SSE 流式咨询，请求体同上。`Content-Type: text/event-stream`，事件如下：

| 事件 | 载荷 | 说明 |
|---|---|---|
| `open` | `{conversationId}` | 会话已就绪 |
| `stage` | `{node, label, elapsedMs, detail}` | 某个 Agent 节点跑完，带真实耗时 |
| `delta` | `{text}` | 一小段回复正文 |
| `done` | 完整结论 + `alertId` + `stages` | 全部结束，**此时才落库** |
| `error` | `{message}` | 出错，这一轮不落库 |

前端收到 `done` 后应用 `done.reply` 整体覆盖已渲染内容。高危回复会在结尾追加危机干预资源，这部分不经过流式传输。

### GET /api/chat/conversations

当前用户的会话列表，按最近更新时间倒序。

### GET /api/chat/conversations/{id}/messages

某会话的完整消息记录，按时间正序。仅限会话所有者。

---

## 三、心理测评 `/api/assessment`

### GET /api/assessment/scales

量表列表（摘要，不含题目）。

### GET /api/assessment/scales/{code}

量表详情：`questions` / `options` / `levels` / `criticalItems`。前端据此渲染，不需要为量表写死界面。`code` 取 `PHQ9` 或 `GAD7`。

### POST /api/assessment/submit

```json
{ "scaleCode": "PHQ9", "answers": [1, 2, 0, 3, 1, 0, 2, 1, 0] }
```

题数与选项取值范围会做校验，不合法直接返回 400。

响应 `data`：`record`（落库的测评记录）、`maxScore`、`suggestion`（处置建议）、`alertId`（达到建单门槛时返回）。

### GET /api/assessment/records

我的测评记录，按时间倒序。

---

## 四、心理档案 `/api/profile`

### GET /api/profile/me

当前登录学生的心理档案。返回 `basic`（基本信息）、`overview`（汇总数字）、`conversations`、`assessments`、`alerts`、`reports`、`timeline`（工单/测评/报告混合时间线，最多 20 条）。

`overview.highestRiskLevel` 取会话、工单、测评三处风险的最高值。

### GET /api/profile/{userId}

查看指定学生的档案。**仅辅导员 / 管理员**，学生调用返回 HTTP 403。

---

## 五、风险工单 `/api/risk/alerts`

以下接口**仅辅导员 / 管理员**可访问。

### GET /api/risk/alerts

| 参数 | 默认 | 说明 |
|---|---|---|
| `current` | 1 | 页码 |
| `size` | 10 | 每页条数，上限 100 |
| `status` | 全部 | `PENDING` / `HANDLED` / `CLOSED` |
| `riskLevel` | 全部 | `MEDIUM` / `HIGH` |

按风险等级升序排列（HIGH 优先），同级按创建时间倒序。

响应为标准分页结构：`{records, total, size, current, pages}`。

### POST /api/risk/alerts/{id}/handle

```json
{ "remark": "已当面沟通，学生情绪平稳，约定两周后回访" }
```

只能处理 `PENDING` 状态的工单，重复处理返回业务异常。

### GET /api/risk/alerts/statistics

全局风险统计：各等级数量、待处理数、各来源数量、涉及学生数。

---

## 六、数据看板 `/api/dashboard`

**仅辅导员 / 管理员**。

| 参数 | 默认 | 范围 |
|---|---|---|
| `days` | 14 | 3~60，越界自动收敛 |
| `topLimit` | 8 | 3~20，越界自动收敛 |

响应 `data`：

| 字段 | 说明 |
|---|---|
| `summary` | 总量、各等级数量、待处理/已处理、涉及学生数、高危占比 |
| `riskDistribution` | `[{name, value}]`，环形图数据 |
| `trend` | 近 N 天按天聚合，**已补齐无数据的日期** |
| `hours` | 24 小时时段分布，长度恒为 24 |
| `peakWindow` | 最集中的 3 小时窗口，跨 0 点会回绕；样本不足时 `available=false` |
| `sourceDistribution` | `CHAT` / `ASSESSMENT` 来源构成 |
| `topStudents` | 按高危工单数排序的重点学生 |
| `handle` | 已处置数与平均处置时长（分钟） |
| `insights` | 由数据自动生成的中文结论 |

---

## 七、咨询报告 `/api/report`

### POST /api/report/{conversationId}

生成或重新生成指定会话的报告（一个会话一份，重复生成会覆盖）。由 Python 侧 LLM 总结整段会话。生成后会话状态置为已结束。

响应 `data`：`summary`、`emotionScore`（0-100，越高越积极）、`riskLevel`、`suggestion`。

### GET /api/report/{conversationId}

查询已有报告。仅限会话所有者。

---

## 八、健康检查 `/api/health`

Java 主服务健康状态，`data.pythonAi` 反映 Python 服务是否在线。Python 服务不可用时仍返回 200，仅该字段为 `OFFLINE`。

---

## 九、Python AI 服务 `:8000`

仅由 Java 主服务调用，不直接对前端暴露。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 返回 LLM 模式与向量库状态 |
| POST | `/api/agent/chat` | 跑一遍 LangGraph，一次性返回 |
| POST | `/api/agent/chat/stream` | SSE 流式版本 |
| POST | `/api/agent/report` | 会话总结成报告 |
| GET | `/api/agent/graph/mermaid` | 导出流程图源码 |
| POST | `/api/agent/kb/rebuild` | 重建向量库（修改 FAQ 语料后调用） |
| GET | `/api/agent/kb/search?q=&topK=` | 直接检索向量库，调参用 |

请求体格式（`/api/agent/chat` 与 `/stream`）：

```json
{
  "userId": 1,
  "conversationId": 1,
  "message": "最近压力很大",
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }]
}
```

返回格式与 Java 侧一致，同样为 `{code, message, data}`。
