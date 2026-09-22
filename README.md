# CampusCare · 校园心理多 Agent 智能咨询平台

[![CI](https://github.com/ydh9851/campus-care/actions/workflows/ci.yml/badge.svg)](https://github.com/ydh9851/campus-care/actions/workflows/ci.yml)

## 项目简介

面向高校心理健康教育中心的一体化平台。学生用自然语言倾诉，系统自动完成 **意图识别 → 知识库检索 → 风险研判 → 生成回复**；出现高危表达时自动生成辅导员工单并附上危机干预资源，辅导员侧提供工单工作台、学生心理档案与全局数据看板。

- **技术栈**：Vue 3 + Element Plus（前端）· Spring Boot 3.2 + MySQL + Redis（Java 主服务）· FastAPI + LangGraph + ChromaDB + DeepSeek（Python AI 服务）
- **两种交互模式**：一次性返回与 SSE 流式输出（逐 token 渲染，并展示每个 Agent 节点的真实耗时）
- **没 Key 也能跑**：未配置 DeepSeek API Key 时整条链路自动降级为 mock，本地调试与 CI 都不消耗额度

> **v2 目标形态见 [docs/TARGET.md](docs/TARGET.md)**（AegisCare 多 Agent 平台的目标效果与验收基线）。
> 本 README 描述的是当前仓库**现状**；涉及「要做什么、做到什么程度」以 TARGET.md 为准。

> ⚠️ **免责声明与使用边界**
> 本项目的心理知识库由通用心理健康科普整理而成，AI 回复仅供情绪支持与科普，
> **不构成医学诊断或治疗建议，也不能替代专业心理医生或咨询师**。
> 项目定位是课程与求职演示；正式投入校园场景前，必须由具备资质的专业人员审核
> 语料、风险规则与危机干预流程。出现危机情况请立即联系专业人员或使用文中热线。

---

## 功能

**学生端**

- 首页工作台：按时段问候、状态一句话、四个快捷入口、最近动态、每日心理小贴士与危机资源
- 注册 / 登录（Spring Security + JWT + Redis 白名单，支持登出立即失效、单点登录；登录页含 Canvas 图形验证码与滑块拼图人机校验）
- 多轮咨询会话，历史上下文自动携带
- 流式回复：回复逐字渲染，顶部展示意图识别、知识检索、风险研判的实时过程
- 心理测评：PHQ-9 抑郁症筛查、GAD-7 广泛性焦虑量表，含单题高危规则
- 心理科普：105 条语料按 11 个分类浏览与关键词搜索，与 RAG 检索共用同一份数据
- 我的心理档案：咨询 / 测评 / 工单 / 报告聚合视图与情绪趋势

**辅导员端**

- 首页工作台：待处理 / 高危 / 涉及学生概览、系统自动结论、重点学生一键进档案
- 风险工单工作台：按风险等级、处理状态筛选分页，查看原文与 AI 处置建议，填写处置备注
- 数据看板：风险分布、工单趋势、24 小时时段分布、来源构成、处置效率、重点学生排行
- 学生心理档案：一键查看某学生全部记录与事件时间线

**合规**

- 访问审计：辅导员每次查阅他人心理档案、处置工单都会留痕（操作人 / 动作 / 对象 / IP），
  日志仅管理员可查 —— 心理数据属于敏感个人信息，必须能回答「谁在什么时候看过这个学生」

**AI 服务**

- LangGraph 状态机编排 4 个节点，条件边按意图分流
- RAG 检索：BM25 字面 + 向量语义双路召回 → RRF 融合 → 轻量重排，回复附带出处与相关度
- 风险研判：关键词规则优先（含否定词、转述他人降级处理），LLM 负责生成处置建议
- Prompt 外置在 `prompts/`，按内容哈希生成版本号并随响应返回，能回答「这次用的是哪一版文案」
- traceId 贯穿 Java ↔ Python ↔ 前端：一次咨询跨两个服务、四个节点，两端日志可按同一个 id 对齐
- 安全护栏：回复带免责声明（会话页展示），高危会话强制附加真实求助资源与人工入口（不交给模型生成）
- LLM 可靠性：指数退避重试 + 总时间预算 + 多模型回退链
- 未配置 API Key 时自动降级为 mock，整条链路仍可跑通

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus + ECharts |
| Java 主服务 | JDK 17 · Spring Boot 3.2 · Spring Security · MyBatis-Plus · MySQL 8 · Redis |
| AI 服务 | Python 3.11+ · FastAPI · LangGraph · LangChain · ChromaDB · 混合检索（BM25 + RRF）· DeepSeek |
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

### 方式一：本地运行（推荐，无需 Docker）

适合本机已装好 JDK / Maven / Node / Python / MySQL / Redis 的情况，也方便打断点调试。

#### 环境要求
| 依赖 | 版本 | 说明 |
|---|---|---|
| JDK | 17 | 不要用 21+（Lombok 1.18.32 不支持高版本 JDK） |
| Maven | 3.8+ | 构建 / 运行 Java |
| Node.js | 18+（CI 用 20） | 前端 |
| Python | 3.11+ | AI 服务，建议 3.11 / 3.12 |
| MySQL | 8.0 | 数据库，需 `utf8mb4` |
| Redis | 5.0+ | **登录强依赖**：JWT 会话存 Redis，没起动登录直接失败 |

> 不想在本机装 MySQL / Redis？可以只拿 Docker 起这两个中间件（见方式二下方「仅用 Docker 跑中间件」）。

#### 1. 克隆
```bash
git clone https://github.com/ydh9851/campus-care.git campus-care
cd campus-care
```

#### 2. 数据库（MySQL）
建库并执行建表脚本（`init.sql` 内含 `DROP/CREATE campus_care`）：
```bash
mysql -uroot -p < sql/init.sql
```
导入演示数据（49 名学生、180+ 工单、90 天跨度，用于看板 / 档案页；可选）：
```bash
mysql -uroot -p campus_care < sql/demo_data.sql
```
> 若你的 MySQL 口令不是项目默认值 `123456`，二选一：① 启动 Java 前设环境变量 `MYSQL_PASSWORD=你的口令`；② 改 `campus-care-java/src/main/resources/application.yml` 的 `password`。

#### 3. Redis
- macOS：`brew install redis && brew services start redis`
- Linux：`sudo apt install redis-server && sudo systemctl start redis`
- Windows：装 [Memurai](https://www.memurai.com/)（Redis 的 Windows 发行版），或在 WSL 里 `sudo apt install redis-server`
启动后 `redis-cli ping` 应返回 `PONG`。

#### 4. Python AI 服务
```bash
cd campus-care-python
python -m venv .venv
source .venv/bin/activate        # Windows：.venv\Scripts\activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/   # 国内可加镜像
cp .env.example .env             # 可选：填入 DEEPSEEK_API_KEY，不填则整条链路走 mock
uvicorn main:app --reload --port 8000
```
> 检索默认用 `bge` 中文语义向量：首次会联网下载 `BAAI/bge-small-zh-v1.5` 并安装 torch（约 2GB，CPU 可跑但稍慢）。若无网络 / 不想装重依赖，在 `.env` 里设 `EMBEDDING_PROVIDER=local_hash` 退化为零依赖字面匹配（检索质量下降）。检索默认走 `RETRIEVAL_MODE=hybrid`（BM25 + 向量双路召回后 RRF 融合），即使向量模型不可用也会自动退化为纯 BM25，不会整条链路失败。未配 Key 时 `llmMode=mock`，回复为内置话术，链路仍可跑通。

#### 5. Java 主服务
```bash
cd campus-care-java
mvn spring-boot:run             # 或 mvn clean package -DskipTests && java -jar target/campus-care-java-1.0.0.jar
```
默认 8080；可用环境变量 `MYSQL_HOST/MYSQL_PORT/MYSQL_PASSWORD`、`REDIS_HOST/REDIS_PORT`、`PYTHON_AI_URL`、`JWT_SECRET` 覆盖默认值。

#### 6. 前端
```bash
cd campus-care-ui
npm install
npm run dev                     # 开发服务器 http://localhost:5173
```
> 生产构建：`npm run build`，产物在 `dist/`，需用 Nginx 等反代把 `/api` 转到 Java:8080（开发服务器的代理仅在 `npm run dev` 生效）。

**启动顺序必须是 Redis → Python → Java → 前端**：Java 启动即连 MySQL/Redis，Python 启动即建向量库，顺序反了会连不上。

### 方式二：Docker Compose 一键
适合不想在本机装一堆中间件的场景，一条命令起 MySQL + Redis + Python + Java：
```bash
cp .env.example .env           # docker-compose 读取根目录 .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（可空，走 mock）
docker-compose up -d
```
`sql/init.sql` 由容器首次启动自动执行；演示数据需手动导入（容器名 `campuscare-mysql`，密码以 `.env` 的 `MYSQL_ROOT_PASSWORD` 为准，默认 `root`）：
```bash
docker exec -i campuscare-mysql mysql -uroot -proot campus_care < sql/demo_data.sql
```
> 国内拉取 Docker Hub 镜像慢 / 被墙时，给 Docker Desktop 配一个镜像加速器（如 `https://docker.m.daocloud.io`）再 `up`。

**仅用 Docker 跑中间件**（本地跑 Java/Python/前端时）：
```bash
docker run -d --name cc-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=123456 -e MYSQL_DATABASE=campus_care mysql:8.0 --character-set-server=utf8mb4 --collation-server=utf8mb4_general_ci
docker run -d --name cc-redis -p 6379:6379 redis:7-alpine
```
然后按方式一的第 4/5/6 步在本地起 Python / Java / 前端即可（端口与本地默认一致）。

本地依赖的完整步骤与常见报错处理见 **[docs/SETUP.md](docs/SETUP.md)**。

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

`sql/demo_data.sql` 含 49 名学生、176 个会话、1000+ 条消息、180+ 张风险工单，覆盖 90 天时间跨度，用于演示看板与档案页。数据由 `tools/gen_demo_data.py` 生成（固定随机种子，条数可复现），可重新生成：

```bash
python tools/gen_demo_data.py
mysql -uroot -p campus_care < sql/demo_data.sql
```

---

## 目录结构

```
campus-care/
├── campus-care-java/          Java 主服务
│   ├── src/main/java/com/campuscare/
│       ├── common/            统一返回、全局异常、风险等级枚举
│       ├── config/            Web / Jackson / MyBatis-Plus / OpenAPI 配置
│       ├── security/          JWT 工具、认证过滤器、Security 配置
│       ├── entity/ mapper/    MyBatis-Plus 实体与 Mapper
│       ├── dto/               出入参与 Java↔Python 协议
│       ├── client/            调用 Python AI 服务
│       ├── service/           业务层
│       └── controller/        REST 接口
│   └── src/test/java/         单元测试：测评计分与档位边界
├── campus-care-python/        Python AI 服务
│   ├── app/agents/            意图识别 / RAG 检索 / 风险研判 / 生成回复
│   ├── app/graph/             LangGraph 状态机
│   ├── app/rag/               ChromaDB 向量库 + BM25/RRF 混合检索
│   ├── app/prompts.py         prompt 外置加载与版本管理
│   ├── app/trace.py           链路追踪（trace id 贯穿 Java↔Python）
│   ├── app/safety.py          免责声明与转人工护栏
│   ├── app/api/               FastAPI 路由
│   ├── prompts/               外置 prompt 文本（意图 / 回复 / 报告 / 风险建议）
│   ├── data/                  心理 FAQ 语料 + 风险研判评估集
│   ├── tests/                 pytest 单测（Mock 模式，离线可跑）
│   └── scripts/               冒烟测试 / 检索评估 / 风险评估 / 语料校验
├── campus-care-ui/            Vue3 前端
│   └── src/views/             登录 / 首页 / 会话 / 测评 / 科普 / 档案 / 工单 / 看板
├── .github/workflows/         CI：Java 测试 + Python 单测与评估 + 前端构建 + 语料校验
├── sql/
│   ├── init.sql               建表脚本（7 张表）
│   └── demo_data.sql          演示数据
├── tools/
│   ├── gen_demo_data.py       演示数据生成器
│   ├── mock_ai_server.py      Mock AI 服务（替代 Python 侧联调用）
│   └── verify_chain.py        端到端回归验收脚本
├── docs/
│   ├── API.md                 接口清单
│   └── SETUP.md               启动、依赖与排错
└── docker-compose.yml
```

---

## 数据模型

7 张表，均不含外键约束（一致性由应用层保证，避免高并发写入时的锁开销）。

| 表 | 说明 |
|---|---|
| `user` | 用户，`role` = STUDENT / COUNSELOR / ADMIN，密码存 BCrypt |
| `conversation` | 会话，冗余存 `risk_level`（会话最高风险）与 `turn_count`（对话轮次） |
| `message` | 消息，`role` = user / assistant，AI 回复带 `intent`、`risk_level`、`tokens` |
| `risk_alert` | 风险工单（统一工单池），`source` = CHAT / ASSESSMENT |
| `consult_report` | 咨询报告，含情绪评分与干预建议 |
| `assessment_record` | 量表测评记录，答题明细以逗号分隔存一行 |
| `access_log` | 敏感数据访问审计，只记查阅与处置动作，不记普通业务写入 |

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
| 心理科普 | `/api/knowledge/**` | 登录用户 |
| 访问审计 | `/api/audit/**` | **仅管理员** |
| 咨询报告 | `/api/report/**` | 登录用户 |

Python AI 服务（仅由 Java 调用）：`/api/health`、`/api/agent/chat`、`/api/agent/chat/stream`、`/api/agent/report`、`/api/agent/kb/search`（支持 `mode=hybrid/vector` 对比）、`/api/agent/kb/list`、`/api/agent/kb/categories`、`/api/agent/kb/rebuild`、`/api/agent/graph/mermaid`。

---

## 回归验收

`tools/verify_chain.py` 覆盖整条链路，纯标准库实现，无需额外依赖：

```bash
python tools/verify_chain.py
```

覆盖 **13 组共 73 项断言**：两端健康检查 → 登录（JWT + Redis）→ 知识查询（断言走 RAG 且命中 FAQ）→ 高危表达（断言 HIGH 并落工单）→ 会话消息落库条数与角色顺序 → 咨询报告生成 → 辅导员工单列表与学生越权 403 → 心理科普（分类过滤 / 关键词过滤）→ 心理测评（作答与计分联动）→ 心理档案（三处取最高、越权 403）→ 数据看板（趋势补零、时段 24 点、结论非空）→ 访问审计（查阅留痕、日志仅管理员可见）。修改任一端口后建议执行一次。

Java 侧另有 **23 项单元测试**，覆盖测评计分的档位边界（4/5、9/10、14/15、19/20 四组切档）与 PHQ-9 第 9 题单题高危规则 —— 这是全项目唯一「算错会害人」的逻辑：

```bash
cd campus-care-java
mvn test
```

Python AI 服务侧有 **39 项 pytest 单测**（Mock 模式，不联网、不消耗额度），以及两套离线质量评估：

```bash
cd campus-care-python
python -m pytest -q                                                    # 39 项单测
python scripts/eval_retrieval.py --mode hybrid --provider local_hash   # 检索质量
python scripts/eval_risk.py                                            # 风险研判质量
```

检索评估用 24 条人工标注的口语化提问（刻意避开 FAQ 标题原词），对比三种模式。以下是零依赖降级路径 `local_hash` 的实测值：

| 检索模式 | Recall@1 | Recall@3 | MRR |
|---|---|---|---|
| 纯向量 | 33.3% | 45.8% | 0.406 |
| 纯 BM25 | 29.2% | 54.2% | 0.460 |
| **混合检索（默认）** | **41.7%** | **62.5%** | **0.536** |

双路融合在 R@1 / R@3 / MRR 上全面超过任一单路 —— 语义改写靠向量、专有名词靠 BM25，正是混合检索的意义所在。线上默认的 `bge` 语义向量指标会更高。

风险评估用 34 条带标注样本（覆盖否定表达、转述他人、口语化高危词、知识型提问），输出各类 Precision / Recall / F1 与危机召回率。当前实测 Macro-F1 1.000、HIGH 召回率 1.000。

CI（`.github/workflows/ci.yml`）会跑 `mvn test`、Python 单测与两套评估（卡 Recall@3 / MRR / Macro-F1 / 危机召回率阈值）、前端构建与语料结构校验；上表需要完整四件套的端到端脚本留在本地执行。

```bash
# 前端未就绪时，可用 Mock AI 服务替换 Python 侧，独立验证 Java 链路
python tools/mock_ai_server.py
```

---

## 已知限制

- 单库单表，未引入分库分表；大数据量下会话列表与档案聚合需要改为分页查询
- 看板统计为实时 `GROUP BY`，未做预聚合或缓存，数据量再大需引入离线汇总表
- 关键词库为人工维护，覆盖面和误报率随语料变化；已配 34 条标注集做回归，但样本规模仍偏小，不足以支撑统计意义上的准确率结论
- 量表仅内置 PHQ-9 与 GAD-7，且未做答题时长、作答一致性等有效性校验
- 前端未做 Element Plus 按需引入，`element` chunk 约 940 kB（gzip 300 kB）；
  ECharts 已通过路由懒加载只在数据看板下载，但首屏 vendor 仍有压缩空间
- 访问审计只落库、不做保留期管理，长期运行需要归档或按时间分区
- 前端无单元测试（vitest）；Java 与 Python 的覆盖集中在核心逻辑，不是全量覆盖
- RAG 检索质量依赖 `EMBEDDING_PROVIDER`：默认 `bge` 语义向量（需安装 torch ≈2GB 并首次联网下载 `BAAI/bge-small-zh-v1.5`），可设 `local_hash` 退化为零依赖字面匹配（仅字面特征、无语义）；未配置 DeepSeek Key 时整条链路走 mock。已有离线评估指标（见「回归验收」），但标注集规模（检索 24 条 / 风险 34 条）仍偏小
- 重排目前是零依赖的启发式打分（融合分 + 覆盖率），未引入 cross-encoder 模型；接口层已预留扩展点，替换 `HybridRetriever._rerank` 即可

## 待改进 / 路线图

按优先级，适合作为简历里「我在持续打磨」的抓手：

1. ~~**测试覆盖**~~（部分完成）：Python 侧已补 39 项单测并接入 CI；剩余前端（组件 / 接口）单测，以及把 `tools/verify_chain.py`（73 断言）接入 CI。
2. ~~**RAG 质量**~~（部分完成）：已实现 BM25 + 向量混合检索与离线评估脚本（Recall@1/3/5、MRR），实测优于任一单路；剩余扩大标注集与 FAQ 语料规模。
3. **风险研判**：已建立 34 条标注集与评估脚本（P/R/F1 + 危机召回率）并接入 CI；下一步引入脱敏真实语料扩充标注规模，持续跟踪误报率。
4. **数据合规**：心理数据明文存储，需补充保留期与删除策略；访问审计日志应支持按时间归档 / 分区。
5. **生产就绪**：反向代理 + HTTPS、JWT 续期与限流、SSE 断线续传、AI 调用熔断（Python 挂掉时避免用户输入丢失）。
6. **移动端适配**：学生主要用手机访问，当前前端未做移动端布局优化。
7. **可观测性**：Python 侧已贯穿 traceId 与 prompt 版本号；剩余接入 actuator / metrics，以及 Java 侧 traceId 透传。
