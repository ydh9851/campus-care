# 启动与排错

## 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| JDK | 17 | Spring Boot 3.2 支持 17 / 21，不要用更高版本编译 |
| Maven | 3.8+ | |
| MySQL | 8.0 | 需支持 `utf8mb4` |
| Redis | 5.0+ | 只用到 SET / GET / DELETE，低版本也可 |
| Python | 3.11+ | AI 服务 |
| Node.js | 18+ | 前端 |

Redis 是**强依赖**：登录成功后 token 会写入 Redis，未启动时登录接口会直接失败。

---

## 启动顺序

**Redis → Python AI 服务 → Java 主服务 → 前端**

Java 服务启动时会连接 MySQL 与 Redis；Python 服务启动时会构建向量库，第一次启动会慢几秒。

---

## 方式一：docker-compose

```bash
cp .env.example .env
# 编辑 .env 填入 MYSQL_ROOT_PASSWORD 与 DEEPSEEK_API_KEY
docker-compose up -d
```

MySQL 首次启动会自动执行 `sql/init.sql`。演示数据需手动导入：

```bash
docker exec -i campus-care-mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" campus_care < sql/demo_data.sql
```

---

## 方式二：本地启动（Windows）

### 1. 数据库

```cmd
mysql -uroot -p < sql\init.sql
mysql -uroot -p campus_care < sql\demo_data.sql
```

`init.sql` 第一行是 `DROP DATABASE IF EXISTS campus_care`，会清空已有数据。已有数据时不要重复执行，只需导入 `demo_data.sql`（它同样会先清空业务表）。

### 2. Redis

```cmd
redis-server.exe
```

Windows 下 Redis 通常以进程方式运行而非系统服务，关闭窗口即停止，重启电脑后不会自动启动，需要重新拉起。

### 3. Python AI 服务

```cmd
cd campus-care-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
python -m uvicorn main:app --port 8000
```

不配置 `DEEPSEEK_API_KEY` 也能启动，此时走 mock 话术，链路可正常跑通，只是回复不是真实模型生成的。

依赖安装说明：`chroma-hnswlib` 必须锁 `0.7.5`，`0.7.6` 在 Windows + Python 3.12 下没有预编译包，会要求安装 MSVC 编译器。

### 4. Java 主服务

```cmd
cd campus-care-java
mvn clean package -DskipTests
java -jar target\campus-care-java-1.0.0.jar
```

或直接 `mvn spring-boot:run`。

### 5. 前端

```cmd
cd campus-care-ui
npm install
npm run dev
```

---

## 配置说明

Java 侧配置在 `campus-care-java/src/main/resources/application.yml`，数据库连接使用占位符加默认值的写法：

```yaml
url: jdbc:mysql://${MYSQL_HOST:localhost}:${MYSQL_PORT:3306}/campus_care
password: ${MYSQL_PASSWORD:123456}
```

部署时设置对应环境变量即可覆盖，无需改代码。

Python 侧配置在 `campus-care-python/.env`，参考 `.env.example`。`DEEPSEEK_API_KEY` 为空或以 `sk-xxxx` 开头时视为未配置，自动降级为 mock。

---

## 排错

**`java -version` 显示的版本不是 17**

Maven 优先使用 `JAVA_HOME`，PATH 中的 `java` 不影响构建。若版本仍不对，检查 `JAVA_HOME` 是否指向 JDK 17 目录。

**启动报 Lombok 相关的编译错误**

JDK 版本过高。Lombok 1.18.32 不支持 JDK 21 以上，需切换到 JDK 17。

**登录报错或登录后所有请求 401**

Redis 未启动，或启动了但进程已退出。用 `redis-cli ping` 确认返回 `PONG`。

**`mvn clean package` 报无法删除 jar**

上一次启动的 Java 进程还在运行，Windows 下会锁住 jar 文件。先结束进程再重新编译。

**AI 回复很呆、像是固定话术**

配置了 Key 但调用失败时，`llm.py` 会静默降级为 mock 并返回 0 token。判断依据是响应中的 `tokens` 是否大于 0：为 0 说明没真正调用到模型。`/api/health` 的 `llmMode` 仅反映 Key 是否非空，不能作为依据。

**前端中文显示乱码**

后端返回的 JSON 未显式声明 charset，部分客户端会按 ISO-8859-1 解码。浏览器与 `curl` 正常，属客户端工具问题。

**ChromaDB 启动时刷 telemetry 报错日志**

0.5.4 的已知问题，`anonymized_telemetry=False` 也无法完全屏蔽，不影响功能。

**用 PowerShell 调接口报 JSON 解析错误**

PowerShell 5.1 向原生程序传参时会吞掉内层双引号。改用 `Invoke-RestMethod` 并在 body 中传对象：

```powershell
Invoke-RestMethod -Uri 'http://localhost:8080/api/auth/login' -Method Post `
  -ContentType 'application/json' `
  -Body (@{username='student01';password='123456'} | ConvertTo-Json)
```

若 `Invoke-WebRequest` 抛 `NullReferenceException`，加 `-UseBasicParsing`。

---

## 回归验收

```bash
python tools/verify_chain.py
```

脚本会依次校验：两端健康检查、登录与 Redis 白名单、知识查询是否真正走 RAG、高危表达是否落工单、会话消息条数与角色顺序、报告生成、角色越权拦截。修改任一服务后建议执行一次。

Python 服务未就绪时，可用 Mock 服务替代，独立验证 Java 侧链路：

```bash
python tools/mock_ai_server.py
```

Mock 服务监听 8000 端口，协议与真实服务一致，毫秒级返回且不消耗 token。关键词约定：含 `失眠 / 压力 / 焦虑 / 睡不着` 返回 MEDIUM，含 `活着没意思 / 不想活 / 自杀 / 自残` 返回 HIGH，其余 LOW。
