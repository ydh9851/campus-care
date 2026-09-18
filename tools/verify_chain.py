"""Java ↔ Python 全链路联调验证脚本。

覆盖范围：
    ① 两端健康检查（Python 返回 LLM 模式与向量库状态）
    ② 登录拿 JWT
    ③ 知识查询 → 必须走 RAG 分支且命中 FAQ
    ④ 高危表达 → 必须判 HIGH 并落一条工单
    ⑤ 同一会话续聊 → 消息落库条数正确
    ⑥ 生成咨询报告
    ⑦ 辅导员账号读工单列表 + 学生越权返回 403

前置条件：Redis、MySQL、Java :8080、Python :8000 均已启动。

用法：python tools/verify_chain.py
只依赖标准库 urllib。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

JAVA = "http://127.0.0.1:8080"
PY = "http://127.0.0.1:8000"

STUDENT = {"username": "student01", "password": "123456"}
COUNSELOR = {"username": "teacher01", "password": "123456"}

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
    check("ragSources 非空（RAG 真的从 ChromaDB 检索到了 FAQ）", bool(sources), f"{len(sources)} 条")
    for s in sources:
        print(f"           · {s}")
    check("reply 非空", bool(data.get("reply")), (data.get("reply") or "")[:40] + " ...")

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

    print("\n" + "=" * 72)
    print(f"验证结束：通过 {_passed} 项，失败 {_failed} 项")
    print("=" * 72)
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
