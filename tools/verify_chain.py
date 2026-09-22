"""Java ↔ Python 全链路联调验证脚本。

覆盖范围：
    ① 两端健康检查（Python 返回 LLM 模式与向量库状态）
    ② 登录拿 JWT
    ③ 知识查询 → 必须走 RAG 分支且命中 FAQ
    ④ 高危表达 → 必须判 HIGH 并落一条工单
    ⑤ 同一会话续聊 → 消息落库条数正确
    ⑥ 生成咨询报告
    ⑦ 辅导员账号读工单列表 + 学生越权返回 403
    ⑧ 心理科普：条目 / 分类 / 分类过滤 / 关键词过滤
    ⑨ 心理测评：量表列表 → 取题 → 作答 → 计分与风险联动
    ⑩ 心理档案：聚合视图 + 三处取最高的证据 + 越权 403
    ⑪ 数据看板：趋势补零、时段 24 点、结论非空 + 越权 403
    ⑫ 访问审计：查阅他人档案必须留痕，且审计日志仅管理员可见
    ⑬ traceId：响应头回写、上游 id 复用、不同请求不重复

前置条件：Redis、MySQL、Java :8080、Python :8000 均已启动。

用法：python tools/verify_chain.py
只依赖标准库 urllib。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

JAVA = "http://127.0.0.1:8080"
PY = "http://127.0.0.1:8000"

STUDENT = {"username": "student01", "password": "123456"}
COUNSELOR = {"username": "teacher01", "password": "123456"}
ADMIN = {"username": "admin", "password": "123456"}

_passed = 0
_failed = 0

# 步骤 1 探测到的 LLM 模式，后续步骤据此决定断言强度（mock 模式下不能要求 tokens > 0）
_llm_mode = "mock"


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def call(url: str, method: str = "GET", payload=None, token: str | None = None, timeout: int = 180):
    """发一个 JSON 请求，返回 (HTTP 状态码, 解析后的 body)。

    刻意不抛异常：联调脚本要能"看到失败原因"，而不是第一处出错就崩掉。
    4xx/5xx 也把响应体取回来，交给调用方断言。
    """
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # 连不上、超时等
        return -1, f"{type(e).__name__}: {e}"


def check(title: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {title}" + (f"  ({detail})" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {title}" + (f"  ({detail})" if detail else ""))


def section(no: int, title: str) -> None:
    print(f"\n{'-' * 72}\n{no}. {title}\n{'-' * 72}")


def unwrap(body):
    """取 {code,message,data} 里的 data（两端协议一致，所以可以共用）。"""
    if isinstance(body, dict) and body.get("code") == 200:
        return body.get("data")
    return None


def fetch_trace_header(path: str = "/api/health", trace_id: str | None = None):
    """请求 Java 并取回响应头里的 X-Trace-Id，返回 (状态码, traceId)。

    单独写一个函数而不是复用 call()：call() 的契约是「返回状态码 + body」，
    为了读一个响应头把它改成三元组，二十多处调用点全得跟着改 —— 不划算。
    """
    req = urllib.request.Request(JAVA + path)
    if trace_id:
        req.add_header("X-Trace-Id", trace_id)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers.get("X-Trace-Id")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("X-Trace-Id")
    except Exception:  # 连不上 / 超时
        return -1, None


# ------------------------------------------------------------------
# 各步骤
# ------------------------------------------------------------------
def step1_python_health() -> None:
    global _llm_mode
    section(1, "Python AI 服务健康检查 :8000")
    status, body = call(f"{PY}/api/health")
    check("GET /api/health 可达", status == 200, f"HTTP {status}")
    data = unwrap(body) or {}
    check("status == UP", data.get("status") == "UP", str(data.get("status")))
    store = data.get("vectorStore") or {}
    check("向量库 ready", bool(store.get("ready")), f"docCount={store.get('docCount')}")
    _llm_mode = data.get("llmMode") or "mock"
    print(f"         LLM 模式: {_llm_mode}"
          f"（mock = 未配 DEEPSEEK_API_KEY，链路照样通；deepseek = 会真调模型）")


def step2_java_health() -> None:
    section(2, "Java 主服务健康检查 :8080")
    status, body = call(f"{JAVA}/api/health")
    check("GET /api/health 可达", status == 200, f"HTTP {status}")
    data = unwrap(body) or {}
    check("Java status == UP", data.get("status") == "UP", str(data.get("status")))
    # 这个字段是 Java 真去 HTTP 调了 Python 才有的，等于反向验证了两端连通
    check("pythonAi == ONLINE", data.get("pythonAi") == "ONLINE", str(data.get("pythonAi")))


def login(account: dict) -> str:
    status, body = call(f"{JAVA}/api/auth/login", "POST", account)
    data = unwrap(body) or {}
    return data.get("token") or data.get("accessToken") or ""


def step3_login() -> str:
    section(3, "登录鉴权（JWT + Redis）")
    token = login(STUDENT)
    check("student01 登录成功并拿到 token", bool(token), f"token 长度={len(token)}")
    if token:
        status, body = call(f"{JAVA}/api/auth/me", token=token)
        data = unwrap(body) or {}
        check("GET /api/auth/me 返回当前用户", data.get("username") == "student01", str(data.get("username")))
    return token


def step4_consult_rag(token: str) -> int | None:
    section(4, "核心链路：知识查询 → 必须走 RAG 检索分支")
    question = "我一到考试周就焦虑得睡不着，有什么办法吗？"
    print(f"         学生输入: {question}")
    status, body = call(f"{JAVA}/api/chat/consult", "POST", {"content": question}, token)
    check("POST /api/chat/consult 返回 200", status == 200, f"HTTP {status}")
    data = unwrap(body) or {}
    if not data:
        print(f"         响应体: {str(body)[:300]}")
        return None

    check("intent == KNOWLEDGE_QUERY（证明意图节点把分支导向了 RAG）",
          data.get("intent") == "KNOWLEDGE_QUERY", str(data.get("intent")))
    sources = data.get("ragSources") or []
    check("ragSources 非空（RAG 真的检索到了 FAQ）", bool(sources), f"{len(sources)} 条")
    for s in sources:
        print(f"           · {s}")
    check("reply 非空", bool(data.get("reply")), (data.get("reply") or "")[:40] + " ...")
    # 混合检索上线后新增：这几个字段必须能一路透传到前端，
    # 少一个接口不会报错，但前端会静默退化（不显示免责声明 / 拿不到 traceId）。
    check("retrievalMode 合法（hybrid / vector）",
          data.get("retrievalMode") in ("hybrid", "vector"), str(data.get("retrievalMode")))
    check("traceId 非空（Java 生成、Python 回显，两端日志可按它对齐）",
          bool(data.get("traceId")), str(data.get("traceId")))
    check("disclaimer 非空（合规兜底）", bool(data.get("disclaimer")))

    # 【关键】配了 Key 之后必须盯住这一项：
    # llm.py 里 LLMClient.is_mock 只看"客户端建没建出来"，所以 Key 填错/余额不足时
    # /api/health 照样报 deepseek，HTTP 也照样 200，只是 except 分支把回复悄悄换成了
    # mock 话术、tokens 返回 0 —— 光看 reply 非空完全发现不了。tokens 才是铁证。
    tokens = data.get("tokens") or 0
    if _llm_mode == "deepseek":
        check("tokens > 0（证明真的调用了 DeepSeek，而非静默降级成 mock）", tokens > 0, f"tokens={tokens}")
        check("回复不是 mock 内置话术", "mock 模式" not in (data.get("reply") or ""))
    else:
        print(f"         [跳过] 当前是 mock 模式，tokens 恒为 0，无法据此判断真实调用")

    print(f"         AI 回复: {(data.get('reply') or '')[:100]} ...")
    return data.get("conversationId")


def step5_consult_risk(token: str, conversation_id: int) -> int | None:
    section(5, "风险预警链路：高危表达 → HIGH + 落预警工单")
    text = "我觉得活着没意义，想结束生命"
    print(f"         学生输入: {text}")
    status, body = call(f"{JAVA}/api/chat/consult", "POST",
                        {"conversationId": conversation_id, "content": text}, token)
    check("同会话续聊返回 200", status == 200, f"HTTP {status}")
    data = unwrap(body) or {}
    if not data:
        print(f"         响应体: {str(body)[:300]}")
        return None

    check("intent == RISK_ALERT", data.get("intent") == "RISK_ALERT", str(data.get("intent")))
    check("riskLevel == HIGH", data.get("riskLevel") == "HIGH", str(data.get("riskLevel")))
    check("落库生成预警工单 alertId", bool(data.get("alertId")), f"alertId={data.get('alertId')}")
    check("高危回复自动附带危机干预热线", "400-161-9995" in (data.get("reply") or ""))
    check("高危请求 needHandoff == true（前端据此展示人工入口）", data.get("needHandoff") is True)
    check("高危回复附带人工求助引导", "希望和真人聊聊" in (data.get("reply") or ""))
    check("traceId 非空", bool(data.get("traceId")), str(data.get("traceId")))
    print(f"         AI 回复: {(data.get('reply') or '')[:100]} ...")
    return data.get("alertId")


def step6_messages(token: str, conversation_id: int) -> None:
    section(6, "会话消息落库校验")
    status, body = call(f"{JAVA}/api/chat/conversations/{conversation_id}/messages", token=token)
    check("GET 会话消息返回 200", status == 200, f"HTTP {status}")
    messages = unwrap(body) or []
    # 两轮咨询 = 学生 2 条 + AI 2 条
    check("消息条数 == 4（2 轮：学生+AI 各 2 条）", len(messages) == 4, f"实际 {len(messages)} 条")
    roles = [m.get("role") for m in messages]
    check("角色顺序为 user/assistant 交替", roles == ["user", "assistant", "user", "assistant"], str(roles))
    last = messages[-1] if messages else {}
    check("最后一条 AI 消息带意图与风险等级",
          bool(last.get("intent")) and bool(last.get("riskLevel")),
          f"intent={last.get('intent')}, riskLevel={last.get('riskLevel')}")


def step7_report(token: str, conversation_id: int) -> None:
    section(7, "咨询报告生成（LLM 总结整段会话）")
    status, body = call(f"{JAVA}/api/report/{conversation_id}", "POST", token=token)
    check("POST /api/report/{id} 返回 200", status == 200, f"HTTP {status}")
    data = unwrap(body) or {}
    if not data:
        print(f"         响应体: {str(body)[:300]}")
        return
    check("emotionScore 在 0-100 区间",
          isinstance(data.get("emotionScore"), int) and 0 <= data["emotionScore"] <= 100,
          f"emotionScore={data.get('emotionScore')}")
    check("riskLevel 合法", data.get("riskLevel") in ("LOW", "MEDIUM", "HIGH"), str(data.get("riskLevel")))
    check("summary 非空", bool(data.get("summary")))
    check("suggestion 非空", bool(data.get("suggestion")))

    if _llm_mode == "deepseek":
        # 规则兜底摘要的固定开头是"本次会话共 N 轮，命中 M 个负面情绪关键词"。
        # 一旦出现这个格式，说明 LLM 返回的 JSON 没解析成功（_parse_report 返回 None 走了兜底），
        # 而不是"模型总结得不好"——这是需要立刻排查的信号。
        check("报告由真实 LLM 生成（非 _heuristic_report 规则兜底）",
              not str(data.get("summary") or "").startswith("本次会话共"))
    print(f"         摘要: {data.get('summary')}")
    print(f"         情绪分: {data.get('emotionScore')}  风险: {data.get('riskLevel')}")
    print(f"         建议: {str(data.get('suggestion'))[:80]} ...")


def step8_risk_alerts() -> None:
    section(8, "辅导员视角：预警列表（角色鉴权）")
    token = login(COUNSELOR)
    check("teacher01（COUNSELOR）登录成功", bool(token))

    status, body = call(f"{JAVA}/api/risk/alerts?current=1&size=5", token=token)
    check("GET /api/risk/alerts 返回 200", status == 200, f"HTTP {status}")
    data = unwrap(body) or {}
    records = data.get("records") or []
    check("预警列表非空", len(records) > 0, f"{len(records)} 条 / 共 {data.get('total')}")
    if records:
        top = records[0]
        print(f"         最新预警: riskLevel={top.get('riskLevel')}, status={top.get('status')}, "
              f"keywords={top.get('keywords')}")

    # 学生账号访问辅导员接口必须 403，这是 Spring Security 的强制要求
    student_token = login(STUDENT)
    status, _ = call(f"{JAVA}/api/risk/alerts", token=student_token)
    check("student01 访问预警接口被拒 403（越权防护生效）", status == 403, f"HTTP {status}")


def step9_knowledge(token: str) -> None:
    section(9, "心理科普：知识库浏览与过滤")
    status, body = call(f"{JAVA}/api/knowledge", token=token)
    check("GET /api/knowledge 返回 200", status == 200, f"HTTP {status}")
    items = unwrap(body) or []
    check("条目数 > 100（语料已从 24 条扩充）", len(items) > 100, f"{len(items)} 条")
    if items:
        first = items[0]
        check("条目字段完整（id/category/title/content/source）",
              all(first.get(k) for k in ("id", "category", "title", "content", "source")),
              str(first.get("title", "")))

    status, body = call(f"{JAVA}/api/knowledge/categories", token=token)
    cats = unwrap(body) or []
    check("GET /api/knowledge/categories 返回 200 且非空", status == 200 and len(cats) > 0,
          f"{len(cats)} 个分类")
    total = sum(int(c.get("count") or 0) for c in cats)
    # 分类统计与全量条目必须对得上，否则说明两侧过滤口径不一致。
    # 额外要求 total > 0：两个空集合当然相等，那是没有意义的假通过。
    check("各分类条数之和 == 条目总数（且不为空）", total == len(items) and total > 0,
          f"{total} vs {len(items)}")

    if cats:
        target = cats[0].get("name")
        expected = int(cats[0].get("count") or 0)
        status, body = call(f"{JAVA}/api/knowledge?category={urllib.parse.quote(str(target))}", token=token)
        hit = unwrap(body) or []
        check(f"按分类过滤生效（{target}）", len(hit) == expected, f"{len(hit)} 条 / 期望 {expected}")
        check("过滤结果的分类全都一致", all(i.get("category") == target for i in hit))

    status, body = call(f"{JAVA}/api/knowledge?q={urllib.parse.quote('焦虑')}", token=token)
    hit = unwrap(body) or []
    check("关键词过滤生效且确实缩小了范围", 0 < len(hit) < len(items), f"命中 {len(hit)} 条")


def step10_assessment(token: str) -> None:
    section(10, "心理测评：量表作答与计分联动")
    status, body = call(f"{JAVA}/api/assessment/scales", token=token)
    scales = unwrap(body) or []
    check("GET /api/assessment/scales 返回 200 且非空", status == 200 and len(scales) > 0,
          f"{len(scales)} 个量表")

    code = next((s.get("code") for s in scales if "PHQ" in str(s.get("code", "")).upper()), None)
    code = code or (scales[0].get("code") if scales else None)
    if not code:
        check("能取到一个可作答的量表", False)
        return

    status, body = call(f"{JAVA}/api/assessment/scales/{code}", token=token)
    detail = unwrap(body) or {}
    questions = detail.get("questions") or []
    check(f"GET /api/assessment/scales/{code} 返回题目与选项",
          status == 200 and len(questions) > 0 and bool(detail.get("options")),
          f"{len(questions)} 题")

    if not questions:
        return

    # 全部选 0（"完全没有"）→ 最低分、最低风险，不影响任何人的预警状态。
    # 4/5 分切档、PHQ-9 第 9 题单题高危这些边界逻辑交给单元测试，
    # 在联调脚本里反复构造高危作答只会把演示数据搞脏。
    status, body = call(f"{JAVA}/api/assessment/submit", "POST",
                        {"scaleCode": code, "answers": [0] * len(questions)}, token)
    result = unwrap(body) or {}
    check("POST /api/assessment/submit 返回 200", status == 200, f"HTTP {status}")
    record = result.get("record") or {}
    check("全 0 作答 → totalScore == 0", record.get("totalScore") == 0, str(record.get("totalScore")))
    check("全 0 作答 → riskLevel == LOW", record.get("riskLevel") == "LOW", str(record.get("riskLevel")))
    check("未达建单门槛 → 不返回 alertId", not result.get("alertId"), str(result.get("alertId")))
    check("返回分级标签与处置建议",
          bool(record.get("severityLabel")) and bool(result.get("suggestion")),
          str(record.get("severityLabel")))

    status, body = call(f"{JAVA}/api/assessment/records", token=token)
    records = unwrap(body) or []
    check("GET /api/assessment/records 能看到刚提交的记录", len(records) > 0, f"{len(records)} 条")


def step11_profile(token: str) -> None:
    section(11, "学生心理档案：聚合视图与越权防护")
    status, body = call(f"{JAVA}/api/profile/me", token=token)
    profile = unwrap(body) or {}
    check("GET /api/profile/me 返回 200", status == 200, f"HTTP {status}")
    check("含 basic 与 overview 两段",
          bool(profile.get("basic")) and bool(profile.get("overview")))

    ov = profile.get("overview") or {}
    check("overview.highestRiskLevel 取值合法",
          ov.get("highestRiskLevel") in ("LOW", "MEDIUM", "HIGH"), str(ov.get("highestRiskLevel")))
    # 第 5 步刚聊过高危内容，档案里的"综合最高风险"必须跟着升上去 ——
    # 这正是「会话 / 工单 / 测评三处取最高」生效的证据。
    check("会话已产生 HIGH → 档案综合最高风险也是 HIGH",
          ov.get("highestRiskLevel") == "HIGH", str(ov.get("highestRiskLevel")))

    timeline = profile.get("timeline") or []
    check("timeline 非空且带事件类型",
          bool(timeline) and bool(timeline[0].get("type")), f"{len(timeline)} 条")

    status, _ = call(f"{JAVA}/api/profile/1", token=token)
    check("student01 查看他人档案被拒 403（@PreAuthorize 生效）", status == 403, f"HTTP {status}")


def step12_dashboard() -> None:
    section(12, "辅导员数据看板：聚合口径与角色鉴权")
    token = login(COUNSELOR)
    check("teacher01（COUNSELOR）登录成功", bool(token))

    status, body = call(f"{JAVA}/api/dashboard?days=14&topLimit=5", token=token)
    board = unwrap(body) or {}
    check("GET /api/dashboard 返回 200", status == 200, f"HTTP {status}")

    summary = board.get("summary") or {}
    check("summary 含累计工单与高危数",
          int(summary.get("totalCount") or 0) > 0 and summary.get("highCount") is not None,
          f"累计 {summary.get('totalCount')} / 高危 {summary.get('highCount')}")

    trend = board.get("trend") or []
    # 没有工单的日子必须补 0，否则折线会把断点连成直线，看着像在增长
    check("趋势补齐成连续 14 天（不是只返回有数据的天）", len(trend) == 14, f"{len(trend)} 天")
    if trend:
        days = [t.get("day") for t in trend]
        check("趋势日期严格递增且无重复",
              days == sorted(days) and len(set(days)) == len(days), f"{days[0]} ~ {days[-1]}")

    hours = board.get("hours") or []
    check("时段分布恒为 24 个小时点", len(hours) == 24, f"{len(hours)} 个")

    insights = board.get("insights") or []
    check("insights 非空（看板要给结论，不能只给图）", bool(insights), f"{len(insights)} 条")
    for line in insights[:3]:
        print(f"           · {line}")

    peak = board.get("peakWindow") or {}
    if peak.get("available"):
        check("peakWindow 的起止小时合法",
              0 <= int(peak.get("startHour") or 0) < 24 and 0 <= int(peak.get("endHour") or 0) < 24,
              f"{peak.get('startHour')}:00 ~ {peak.get('endHour')}:00（占 {peak.get('ratio')}%）")

    status, _ = call(f"{JAVA}/api/dashboard", token=login(STUDENT))
    check("student01 访问看板被拒 403", status == 403, f"HTTP {status}")


def step13_audit() -> None:
    section(13, "访问审计：敏感数据查阅留痕")
    counselor = login(COUNSELOR)
    status, _ = call(f"{JAVA}/api/profile/1", token=counselor)
    check("teacher01 查看学生 1 的档案返回 200", status == 200, f"HTTP {status}")

    admin = login(ADMIN)
    check("admin（ADMIN）登录成功", bool(admin))
    if not admin:
        return

    status, body = call(
        f"{JAVA}/api/audit/logs?current=1&size=5&targetType=USER&targetId=1", token=admin)
    check("管理员可查询审计日志", status == 200, f"HTTP {status}")
    page = unwrap(body) or {}
    records = page.get("records") or []
    check("刚才那次查阅已经留痕", len(records) > 0, f"{len(records)} 条")

    if records:
        latest = records[0]
        check("动作类型为 VIEW_PROFILE", latest.get("action") == "VIEW_PROFILE", str(latest.get("action")))
        check("记录了操作人 id 与账号（账号冗余存，改名后仍可读）",
              latest.get("operatorId") is not None and bool(latest.get("operatorName")),
              f"{latest.get('operatorName')}(#{latest.get('operatorId')})")
        check("记录了来源 IP", bool(latest.get("ip")), str(latest.get("ip")))
        print(f"         最新审计: {latest.get('operatorName')} "
              f"{latest.get('action')} {latest.get('targetType')}#{latest.get('targetId')} "
              f"from {latest.get('ip')}")

    # 审计日志记录的是「哪个辅导员看了哪个学生」，本身也是敏感数据。
    # 对辅导员开放等于给了他们互相监视的能力，反而会让人不敢正常用系统。
    status, _ = call(f"{JAVA}/api/audit/logs", token=login(STUDENT))
    check("student01 访问审计日志被拒 403", status == 403, f"HTTP {status}")
    status, _ = call(f"{JAVA}/api/audit/logs", token=login(COUNSELOR))
    check("teacher01 访问审计日志被拒 403（辅导员也不能看）", status == 403, f"HTTP {status}")


def step14_trace_id() -> None:
    """traceId 链路：响应头必须回写，且上游带了的要复用。

    这三条断言看着琐碎，但每一个都对应一种「静默失效」：
    没回写响应头 → 前端报障时给不出 id；没复用上游 id → 跨系统链路断成两截；
    写死成常量 → 所有请求的日志混在一起，等于没有追踪。
    """
    section(14, "traceId：响应头回写与上游复用")

    status, trace_id = fetch_trace_header()
    check("Java 响应头回写 X-Trace-Id", status == 200 and bool(trace_id), f"{trace_id}")
    check("traceId 为 16 位（与 Python 侧口径一致）",
          bool(trace_id) and len(trace_id) == 16,
          f"{trace_id}")

    _, second = fetch_trace_header()
    check("不同请求的 traceId 不重复（不是写死的常量）",
          bool(trace_id) and second != trace_id,
          f"{trace_id} → {second}")

    # 上游（网关 / 前端）自带的 id 必须原样复用，否则跨系统就是两条断开的链路
    upstream = "0123456789abcdef"
    _, echoed = fetch_trace_header(trace_id=upstream)
    check("复用上游传入的 X-Trace-Id", echoed == upstream, f"{echoed}")


def main() -> int:
    print("=" * 72)
    print("CampusCare  Java ↔ Python 全链路联调验证")
    print("=" * 72)

    step1_python_health()
    step2_java_health()

    token = step3_login()
    if not token:
        print("\n[中止] 登录失败，后面的链路无法继续。请检查 Redis / MySQL / Java 是否正常。")
        return 1

    conversation_id = step4_consult_rag(token)
    if not conversation_id:
        print("\n[中止] 首轮咨询失败，后面的链路无法继续。")
        return 1

    step5_consult_risk(token, conversation_id)
    step6_messages(token, conversation_id)
    step7_report(token, conversation_id)
    step8_risk_alerts()

    # 第 8 步为了验证越权，又登录了一次 student01。
    # 本系统的 token 白名单是【单点登录】语义 —— 同一账号重新登录会让旧 token 立刻失效，
    # 所以这里必须重新取一次，否则 ⑨⑩⑪ 会整段 401。
    # （这个坑值得留着当文档：任何"重新登录"的代码都会把别处持有的 token 踢掉。）
    token = login(STUDENT)

    step9_knowledge(token)
    step10_assessment(token)
    step11_profile(token)
    step12_dashboard()
    step13_audit()
    step14_trace_id()

    print("\n" + "=" * 72)
    print(f"验证结束：通过 {_passed} 项，失败 {_failed} 项")
    print("=" * 72)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
