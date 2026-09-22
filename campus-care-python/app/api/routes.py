"""FastAPI 路由：Java 主服务通过这几个接口调用 AI 能力。

统一返回 {code, message, data}，与 Java 侧 Result 完全对齐。
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from typing import List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.intent_agent import intent_node, route_by_intent
from app.agents.rag_agent import rag_node, retrieve
from app.agents.reply_agent import MOCK_REPLIES, build_messages, finalize_reply
from app.agents.risk_agent import risk_node
from app.agents.state import AgentState
from app.config import get_settings
from app.graph.builder import get_graph, mermaid
from app.llm import get_llm
from app.prompts import fill, load_prompt, prompt_versions
from app.rag.loader import load_faq
from app.rag.store import get_store
from app.safety import DISCLAIMER, needs_handoff
from app.schemas import AgentChatData, AgentChatRequest, Envelope, ReportData
from app.trace import get_trace_id, set_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


def _bind_trace(request: AgentChatRequest) -> str:
    """确定本次请求的 trace id，优先级：body 指定 > header（中间件已设）> 新生成。"""
    current = get_trace_id()
    tid = request.traceId or (current if current and current != "-" else "")
    return set_trace_id(tid)


# ---------- 健康检查 ----------
@router.get("/health")
def health():
    """供 Java 服务反向探测"""
    store = get_store()
    llm = get_llm()
    settings = get_settings()
    return Envelope.ok({
        "service": "campus-care-python",
        "status": "UP",
        "llmMode": "mock" if llm.is_mock else "deepseek",
        "models": llm.models,
        "retrievalMode": settings.retrieval_mode,
        "vectorStore": {"ready": store.ready, "docCount": store.count()},
        "promptVersions": prompt_versions(),
    })


# ---------- 一轮多 Agent 咨询 ----------
@router.post("/agent/chat")
def agent_chat(request: AgentChatRequest):
    """执行 LangGraph：意图识别 → (RAG 检索) → 风险预警 → 生成回复"""
    _bind_trace(request)
    history = [{"role": m.role, "content": m.content} for m in request.history]

    initial_state: AgentState = {
        "user_id": request.userId or 0,
        "conversation_id": request.conversationId or 0,
        "message": request.message,
        "history": history,
    }

    try:
        result = get_graph().invoke(initial_state)
    except Exception as e:
        logger.exception("LangGraph 执行失败")
        return Envelope.fail(f"AI 链路执行失败: {type(e).__name__}: {e}")

    settings = get_settings()
    risk_level = result.get("risk_level") or "LOW"
    data = AgentChatData(
        reply=result.get("reply") or "",
        intent=result.get("intent") or "PSYCH_EMOTION",
        riskLevel=risk_level,
        keywords=list(result.get("keywords") or []),
        aiSuggestion=result.get("ai_suggestion") or None,
        ragSources=list(result.get("rag_sources") or []),
        tokens=int(result.get("tokens") or 0),
        traceId=get_trace_id(),
        retrievalMode=settings.retrieval_mode,
        promptVersion=prompt_versions(),
        disclaimer=DISCLAIMER if settings.disclaimer_enabled else "",
        needHandoff=needs_handoff(risk_level),
    )
    logger.info("本轮咨询完成: intent=%s, risk=%s, tokens=%s",
                data.intent, data.riskLevel, data.tokens)
    return Envelope.ok(data)


# ---------- SSE 流式咨询 ----------
# 事件名约定，Java 侧原样透传给浏览器，改动必须两端同步。
EVENT_STAGE = "stage"   # 某个节点跑完（带真实耗时与结论）
EVENT_DELTA = "delta"   # 一小段回复正文
EVENT_DONE = "done"     # 全部结束，内含完整结论，供 Java 侧落库
EVENT_ERROR = "error"   # 出错（Java 侧收到后不落库）


def _sse(event: str, data) -> str:
    """拼一个 SSE 帧。ensure_ascii=False 保留中文原文，便于抓包和看日志。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/agent/chat/stream")
def agent_chat_stream(request: AgentChatRequest):
    """
    流式版咨询接口：每个节点跑完推 stage 事件，回复逐块推 delta，最后推 done 供 Java 落库。

    这里按 graph/builder.py 的拓扑手动依次调用节点，而不是 graph.invoke() ——
    invoke() 只在全部跑完后一次性返回，没法在节点之间插事件。
    代价是拓扑在此重复了一份，改图结构时必须同步修改。
    """
    history = [{"role": m.role, "content": m.content} for m in request.history]

    state: AgentState = {
        "user_id": request.userId or 0,
        "conversation_id": request.conversationId or 0,
        "message": request.message,
        "history": history,
    }
    trace_id = _bind_trace(request)

    def event_stream():
        # 生成器在线程池里执行，contextvar 不会自动继承请求上下文，
        # 所以这里重新写入 trace id，保证这段链路里的日志能被串起来。
        set_trace_id(trace_id)
        started_all = time.perf_counter()
        stages: List[dict] = []

        def stage_event(node: str, label: str, elapsed_ms: int, detail: dict) -> dict:
            item = {"node": node, "label": label, "elapsedMs": elapsed_ms, "detail": detail}
            stages.append(item)
            return item

        try:
            # ---------- 节点 1：意图识别 ----------
            t = time.perf_counter()
            state.update(intent_node(state))
            yield _sse(EVENT_STAGE, stage_event(
                "intent", "意图识别", int((time.perf_counter() - t) * 1000),
                {"intent": state.get("intent"), "reason": state.get("intent_reason")},
            ))

            # ---------- 条件边：只有知识查询才走 RAG ----------
            if route_by_intent(state) == "rag":
                t = time.perf_counter()
                state.update(rag_node(state))
                sources = list(state.get("rag_sources") or [])
                yield _sse(EVENT_STAGE, stage_event(
                    "rag", "知识库检索", int((time.perf_counter() - t) * 1000),
                    {"hitCount": len(sources), "sources": sources},
                ))

            # ---------- 节点 3：风险研判 ----------
            t = time.perf_counter()
            state.update(risk_node(state))
            yield _sse(EVENT_STAGE, stage_event(
                "risk", "风险研判", int((time.perf_counter() - t) * 1000),
                {"riskLevel": state.get("risk_level"),
                 "keywords": list(state.get("keywords") or [])},
            ))

            # ---------- 节点 4：生成回复（真正的流式） ----------
            t = time.perf_counter()
            intent = state.get("intent") or "PSYCH_EMOTION"
            tokens = 0
            pieces: List[str] = []

            for ev in get_llm().chat_stream(
                messages=build_messages(state),
                mock_text=MOCK_REPLIES.get(intent, MOCK_REPLIES["PSYCH_EMOTION"]),
            ):
                if ev["type"] == "delta":
                    pieces.append(ev["text"])
                    yield _sse(EVENT_DELTA, {"text": ev["text"]})
                elif ev["type"] == "usage":
                    tokens = ev["tokens"]
                elif ev["type"] == "error":
                    # 已经吐出去的字收不回来，所以直接报错并结束：
                    # Java 侧收到 error 不落库，等价于「这一轮没发生过」。
                    yield _sse(EVENT_ERROR, {"message": ev["message"]})
                    return

            # 高危时 finalize_reply 会追加危机资源，那部分没走过流式。
            # done.reply 返回完整文本，前端整体覆盖已渲染内容，不做增量补推，
            # 否则两端拼接一旦不一致就会出现重复段落。
            full_reply = finalize_reply("".join(pieces), state.get("risk_level") or "LOW")

            yield _sse(EVENT_STAGE, stage_event(
                "generate", "组织回复", int((time.perf_counter() - t) * 1000),
                {"tokens": tokens},
            ))

            settings = get_settings()
            risk_level = state.get("risk_level") or "LOW"
            yield _sse(EVENT_DONE, {
                "reply": full_reply,
                "intent": intent,
                "riskLevel": risk_level,
                "keywords": list(state.get("keywords") or []),
                "aiSuggestion": state.get("ai_suggestion") or None,
                "ragSources": list(state.get("rag_sources") or []),
                "tokens": tokens,
                "elapsedMs": int((time.perf_counter() - started_all) * 1000),
                "stages": stages,
                "traceId": get_trace_id(),
                "retrievalMode": settings.retrieval_mode,
                "promptVersion": prompt_versions(),
                "disclaimer": DISCLAIMER if settings.disclaimer_enabled else "",
                "needHandoff": needs_handoff(risk_level),
            })

        except Exception as e:
            logger.exception("流式链路执行失败")
            yield _sse(EVENT_ERROR, {"message": f"{type(e).__name__}: {e}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 前面若有 nginx，别让它缓冲 SSE
            "Connection": "keep-alive",
        },
    )


# ---------- 咨询报告：整段会话总结 ----------

@router.post("/agent/report")
def agent_report(request: AgentChatRequest):
    """把整个会话交给 LLM 总结成咨询报告（prompt 见 prompts/report.txt）"""
    _bind_trace(request)
    history = request.history or []
    dialog = "\n".join(
        f"{'学生' if m.role == 'user' else '助手'}：{m.content}" for m in history if m.content
    )
    if not dialog.strip():
        return Envelope.fail("会话内容为空，无法生成报告", code=400)

    llm = get_llm()
    fallback = _heuristic_report(dialog, history)
    text, _ = llm.chat(
        messages=[{
            "role": "user",
            "content": fill(load_prompt("report"), dialog=dialog[:6000]),
        }],
        temperature=0.2,
        mock_text=fallback.model_dump_json(),
    )

    parsed = _parse_report(text)
    return Envelope.ok(parsed or fallback)


def _parse_report(text: str) -> ReportData | None:
    """容错解析：模型有时会包着 ```json 代码块，需要先抠出 JSON 本体。"""
    import json
    import re

    if not text:
        return None
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", candidate, re.S)
    if fence:
        candidate = fence.group(1).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        obj = json.loads(candidate[start:end + 1])
    except json.JSONDecodeError:
        return None

    try:
        return ReportData(
            summary=str(obj.get("summary", ""))[:1000],
            emotionScore=max(0, min(100, int(obj.get("emotionScore", 60)))),
            riskLevel=str(obj.get("riskLevel", "LOW")).upper(),
            suggestion=str(obj.get("suggestion", ""))[:1000],
        )
    except (TypeError, ValueError):
        return None


def _heuristic_report(dialog: str, history: List[HistoryMessage]) -> ReportData:
    """规则兜底：模型不可用时，用关键词密度粗略估情绪分。"""
    from app.agents.risk_agent import HIGH_RISK_WORDS, MEDIUM_RISK_WORDS

    high = [w for w in HIGH_RISK_WORDS if w in dialog]
    medium = [w for w in MEDIUM_RISK_WORDS if w in dialog]

    # 轮数口径与 Java 侧 turn_count 一致：1 轮 = 学生 1 条 + AI 1 条，只数 user 消息。
    # 不能用换行符数量推轮数，AI 回复是多行文本，会把 2 轮算成十几轮。
    turns = sum(1 for m in history if m.role == "user") or 1

    if high:
        level, score = "HIGH", 25
    elif len(medium) >= 3:
        level, score = "MEDIUM", 45
    else:
        level, score = "LOW", 65

    return ReportData(
        summary=f"本次会话共 {turns} 轮，命中 {len(medium)} 个负面情绪关键词。",
        emotionScore=score,
        riskLevel=level,
        suggestion="建议辅导员在 24 小时内主动联系学生了解近况，必要时转介校心理中心面询。"
        if level != "LOW" else "当前无明显风险，可保持常规关注。",
    )


# ---------- 辅助接口 ----------
@router.get("/agent/graph/mermaid")
def graph_mermaid():
    """导出 LangGraph 流程图源码，贴到 README 就能渲染架构图"""
    return Envelope.ok(mermaid())


@router.post("/agent/kb/rebuild")
def rebuild_kb():
    """重建向量库（改了 data/psych_faq.json 之后调这个）"""
    try:
        count = get_store().build(force=True)
        return Envelope.ok({"docCount": count})
    except Exception as e:
        logger.exception("重建向量库失败")
        return Envelope.fail(f"重建失败: {e}")


@router.get("/agent/kb/search")
def kb_search(q: str, topK: int = 3, mode: str | None = None):
    """检索知识库，方便调参和演示 RAG 效果。

    mode 可临时指定 hybrid / vector —— 同一个问题两种模式各查一次，
    能直观看出混合检索多召回了什么（混合结果的 retrieval 字段会标出来自哪一路）。
    """
    docs: List[dict] = retrieve(q, top_k=topK, mode=mode)
    return Envelope.ok(docs)


@router.get("/agent/kb/list")
def kb_list(category: str | None = None, q: str | None = None):
    """列出知识库条目，供「心理科普」页展示。

    这里是**全量列举**，不走向量检索 —— 与 /agent/kb/search 的用途不同：
    科普页要的是「按分类浏览全部内容」，检索接口要的是「按语义找最相关的几条」。
    用检索接口做列表页会漏掉相关性低但用户想主动浏览的条目。
    """
    items = load_faq()

    if category and category != "全部":
        items = [i for i in items if i.get("category") == category]

    if q and q.strip():
        kw = q.strip().lower()
        items = [
            i for i in items
            if kw in str(i.get("title", "")).lower() or kw in str(i.get("content", "")).lower()
        ]

    return Envelope.ok({"total": len(items), "items": items})


@router.get("/agent/kb/categories")
def kb_categories():
    """分类及各自条数，供前端渲染筛选标签"""
    counter = Counter(str(i.get("category") or "通用") for i in load_faq())
    return Envelope.ok([{"name": name, "count": cnt} for name, cnt in counter.most_common()])
