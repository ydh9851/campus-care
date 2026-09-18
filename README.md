# CampusCare · 校园心理多 Agent 智能咨询平台

面向高校心理健康教育中心的一体化平台。学生用自然语言倾诉，系统自动完成**意图识别 → 知识库检索 → 风险研判 → 生成回复**，出现高危表达时自动生成辅导员工单并附上危机干预资源；辅导员侧提供工单工作台、学生心理档案与全局数据看板。

支持两种交互模式：一次性返回与 SSE 流式输出（逐 token 渲染，并展示每个 Agent 节点的真实耗时）。

---

## 功能

**学生端**

- 注册 / 登录（Spring Security + JWT + Redis 白名单，支持登出立即失效、单点登录）
- 多轮咨询会话，历史上下文自动携带
- 流式回复：回复逐字渲染，顶部展示意图识别、知识检索、风险研判的实时过程
- 心理测评：PHQ-9 抑郁症筛查、GAD-7 广泛性焦虑量表，含单题高危规则
- 我的心理档案：咨询 / 测评 / 工单 / 报告聚合视图与情绪趋势

**辅导员端**

- 风险工单工作台：按风险等级、处理状态筛选分页，查看原文与 AI 处置建议，填写处置备注
- 数据看板：风险分布、工单趋势、24 小时时段分布、来源构成、处置效率、重点学生排行
- 学生心理档案：一键查看某学生全部记录与事件时间线

**AI 服务**

- LangGraph 状态机编排 4 个节点，条件边按意图分流
- RAG 检索：ChromaDB 向量库 + 校园心理 FAQ 语料，回复附带出处与相似度
- 风险研判：关键词规则优先（含否定词、转述他人降级处理），LLM 负责生成处置建议
- 未配置 API Key 时自动降级为 mock，整条链路仍可跑通

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus + ECharts |
| Java 主服务 | JDK 17 · Spring Boot 3.2 · Spring Security · MyBatis-Plus · MySQL 8 · Redis |
| AI 服务 | Python 3.11+ · FastAPI · LangGraph · LangChain · ChromaDB · DeepSeek |
| 鉴权 | JWT（HS256）+ Redis token 白名单 |
| 通信 | Java ↔ Python 走 HTTP JSON，两端统一 `{code, message, data}` |

---

## 架构

```
┌──────────────┐   HTTP /api/**    ┌──────────────────────────┐
│  Vue3 前端    │ ────────────────► │  campus-care-java :8080   │
│ Element Plus │ ◄──────────────── │  鉴权 / 业务 / 落库        │
└──────────────┘   统一 Result     └───────────┬──────────────┘
                                   HTTP JSON   │
                                    ┌──────────▼───────────────┐
                                    │ campus-care-python :8000  │
                                    │  FastAPI + LangGraph      │
                                    │  意图识别 → RAG 检索 →     │
                                    │  风险研判 → 生成回复       │
                                    └──────────┬───────────────┘
                                               │ OpenAI 兼容协议
                                        ┌──────▼───────┐
                                        │ DeepSeek API  │
                                        └───────────────┘
```

Java 侧只做事务型业务与权限控制，所有 LLM / RAG / Agent 编排都在 Python 侧。这样拆的好处是 AI 调用（数秒到一分钟）不会占用 Java 的数据库连接，两侧也能独立扩容。

---

## 快速开始

```bash
# 1. 配置 DeepSeek API Key（不配也能跑，AI 会走 mock 话术）
cp .env.example campus-care-python/.env
# 编辑填入 DEEPSEEK_API_KEY

# 2. 初始化数据库 + 导入演示数据
mysql -uroot -p < sql/init.sql
mysql -uroot -p campus_care < sql/demo_data.sql

# 3. 用 docker-compose 一键启动 MySQL + Redis + 双服务
docker-compose up -d
```

不使用 Docker 的本地启动方式、常见报错处理见 **[docs/SETUP.md](docs/SETUP.md)**。

启动后：

| 入口 | 地址 |
|---|---|
| 前端 | http://localhost:5173 |
| Java 接口文档（Swagger） | http://localhost:8080/swagger-ui.html |
| Python 接口文档 | http://localhost:8000/docs |

演示账号（密码均为 `123456`）：

| 账号 | 角色 | 说明 |
|---|---|---|
| `student01` | STUDENT | 学生端全部功能 |
| `teacher01` | COUNSELOR | 工单工作台 + 数据看板 + 学生档案 |

`sql/demo_data.sql` 含 48 名学生、176 个会话、1000+ 条消息、180+ 张风险工单，覆盖 90 天时间跨度，用于演示看板与档案页。数据由 `tools/gen_demo_data.py` 生成，可重新生成：

```bash
python tools/gen_demo_data.py
mysql -uroot -p campus_care < sql/demo_data.sql
```

---

## 目录结构

```
campus-care/
├── campus-care-java/          Java 主服务
│   └── src/main/java/com/campuscare/
│       ├── common/            统一返回、全局异常、风险等级枚举
│       ├── config/            Web / Jackson / MyBatis-Plus / OpenAPI 配置
│       ├── security/          JWT 工具、认证过滤器、Security 配置
│       ├── entity/ mapper/    MyBatis-Plus 实体与 Mapper
│       ├── dto/               出入参与 Java↔Python 协议
│       ├── client/            调用 Python AI 服务
│       ├── service/           业务层
│       └── controller/        REST 接口
├── campus-care-python/        Python AI 服务
│   ├── app/agents/            意图识别 / RAG 检索 / 风险研判 / 生成回复
│   ├── app/graph/             LangGraph 状态机
│   ├── app/rag/               ChromaDB 向量库与语料加载
│   ├── app/api/               FastAPI 路由
│   ├── data/                  心理 FAQ 语料
│   └── scripts/               离线冒烟测试
├── campus-care-ui/            Vue3 前端
│   └── src/views/             登录 / 会话 / 测评 / 档案 / 工单 / 看板
├── sql/
│   ├── init.sql               建表脚本
│   └── demo_data.sql          演示数据
├── tools/
│   ├── gen_demo_data.py       演示数据生成器
│   ├── mock_ai_server.py      Mock AI 服务（替代 Python 侧联调用）
│   └── verify_chain.py        端到端回归验收脚本
├── docs/
│   ├── API.md                 接口清单
│   └── SETUP.md               启动、依赖与排错
├── docker-compose.yml
└── AI_CONTEXT.md              开发上下文（供 AI 助手读取，可删除）
```

---

## 数据模型

6 张表，均不含外键约束（一致性由应用层保证，避免高并发写入时的锁开销）。

| 表 | 说明 |
|---|---|
| `user` | 用户，`role` = STUDENT / COUNSELOR / ADMIN，密码存 BCrypt |
| `conversation` | 会话，冗余存 `risk_level`（会话最高风险）与 `turn_count`（对话轮次） |
| `message` | 消息，`role` = user / assistant，AI 回复带 `intent`、`risk_level`、`tokens` |
| `risk_alert` | 风险工单（统一工单池），`source` = CHAT / ASSESSMENT |
| `consult_report` | 咨询报告，含情绪评分与干预建议 |
| `assessment_record` | 量表测评记录，答题明细以逗号分隔存一行 |

---

## 几个实现要点

**风险等级只升不降。** 会话风险与消息风险分开存，更新时用一条 SQL 完成自增与取最大值：

```sql
UPDATE conversation
SET turn_count = turn_count + 1,
    risk_level = CASE
        WHEN #{riskLevel} = 'HIGH' THEN 'HIGH'
        WHEN #{riskLevel} = 'MEDIUM' AND risk_level <> 'HIGH' THEN 'MEDIUM'
        ELSE risk_level END
WHERE id = #{conversationId}
```

自增与取最大值都在数据库内完成，避免"先查后改"的丢失更新，也少一次往返。风险等级只升不降是安全底线：学生前面说过危险的话，后面聊轻松了也不能把记录冲掉。

**咨询接口不开事务。** 中间要调 LLM，若整个方法包在事务里，数据库连接会被占住一分钟，连接池很快被打满，连登录这类不需要 AI 的接口也会超时。因此 `ChatService` 只做编排，写操作收敛到 `ChatPersistService` 的短事务里。代价是 AI 调用失败会留下半成品数据，所以把 AI 调用排在写库之前，失败时数据库保持干净，首次咨询刚建的会话会被回滚。

**JWT + Redis 白名单。** 纯 JWT 签发后无法撤销，因此在 Redis 存一份 token 副本并要求完全一致，登出、管理员踢人、改密后下线都能立即生效，顺带实现了单点登录。代价是每请求多一次 Redis 查询。

**风险研判规则优先。** 危机识别漏判代价太大，因此用显式关键词库判定等级，并处理否定表达（"我没有想死"）与转述他人（"我朋友想死"）。LLM 只负责生成给辅导员的处置建议。高危回复的危机干预资源是硬编码的，不交给模型生成。

**量表数据驱动。** 量表定义放在 `resources/scales/*.json`，新增量表只需加一个文件并在 `SCALE_REGISTRY` 登记，Java 与前端都无需改动。除总分分级外还有单题高危规则：PHQ-9 第 9 题（自伤念头）只要不为 0 直接判 HIGH，因为总分会被其他题目稀释。

**看板聚合下推到 SQL。** 趋势、时段分布、重点学生等一律用 `GROUP BY` 在数据库完成，不把全量数据捞进内存分组。近 N 天趋势会补齐没有工单的日期，否则折线会把断点连成直线，看着像在增长。

---

## 接口

完整清单（含请求体与响应示例）见 **[docs/API.md](docs/API.md)**。

Java 主服务概览：

| 分组 | 路径前缀 | 权限 |
|---|---|---|
| 认证 | `/api/auth/**` | 登录/注册公开，其余需登录 |
| 咨询 | `/api/chat/**` | 登录用户 |
| 测评 | `/api/assessment/**` | 登录用户 |
| 心理档案 | `/api/profile/**` | `/me` 本人，`/{userId}` 仅辅导员 |
| 风险工单 | `/api/risk/alerts/**` | 仅辅导员 / 管理员 |
| 数据看板 | `/api/dashboard` | 仅辅导员 / 管理员 |
| 咨询报告 | `/api/report/**` | 登录用户 |

Python AI 服务（仅由 Java 调用）：`/api/health`、`/api/agent/chat`、`/api/agent/chat/stream`、`/api/agent/report`、`/api/agent/kb/search`、`/api/agent/kb/rebuild`、`/api/agent/graph/mermaid`。

---

## 回归验收

`tools/verify_chain.py` 覆盖整条链路，纯标准库实现，无需额外依赖：

```bash
python tools/verify_chain.py
```

覆盖内容：两端健康检查 → 登录（JWT + Redis）→ 知识查询（断言走 RAG 且命中 FAQ）→ 高危表达（断言 HIGH 并落工单）→ 会话消息落库条数与角色顺序 → 咨询报告生成 → 辅导员工单列表与学生越权 403。修改任一端口后建议执行一次。

```bash
# 前端未就绪时，可用 Mock AI 服务替换 Python 侧，独立验证 Java 链路
python tools/mock_ai_server.py
```

---

## 已知限制

- 单库单表，未引入分库分表；大数据量下会话列表与档案聚合需要改为分页查询
- 看板统计为实时 `GROUP BY`，未做预聚合或缓存，数据量再大需引入离线汇总表
- 关键词库为人工维护，覆盖面和误报率随语料变化，缺少持续评估机制
- 量表仅内置 PHQ-9 与 GAD-7，且未做答题时长、作答一致性等有效性校验
