"""生成节点：链路的收口，把前面各 Agent 的结论合成一句人话。

按意图决定说话方式，有 RAG 结果就要求"只依据资料回答"，
高风险回复强制附上真实求助资源 + 人工入口。

prompt 全部外置在 prompts/ 下（reply_base.txt / reply_style.json），
这里的 MOCK_REPLIES 不是 prompt 而是「没配 Key 时的兜底话术」，所以留在代码里。
"""
from __future__ import annotations

import logging

from app.agents.rag_agent import build_context
from app.agents.risk_agent import CRISIS_RESOURCES
from app.agents.state import AgentState
from app.llm import get_llm
from app.prompts import load_json_prompt, load_prompt
from app.safety import apply_safety

logger = logging.getLogger(__name__)

MOCK_REPLIES = {
    "PSYCH_EMOTION": "听到你这么说，我能感觉到你这段时间确实挺不容易的。愿意多讲讲是什么让你最难受吗？如果现在很难受，可以先试着深呼吸几次，喝口温水，给自己十分钟什么都不做。",
    "KNOWLEDGE_QUERY": "（mock 模式）我没有配置真实模型，但根据知识库的通用建议：先把问题拆小，从最容易做到的一件小事开始；保持规律作息；如果持续两周以上影响生活，建议预约学校心理中心的免费咨询。",
    "RISK_ALERT": "谢谢你愿意说出来，这需要很大的勇气。你现在承受的痛苦是真实的，但你不需要一个人扛。请现在就联系学校心理中心或拨打下面的热线，会有人陪你一起度过。",
    "CHITCHAT": "你好，我是 CampusCare 的心理支持助手。今天过得怎么样？有什么想聊的都可以跟我说。",
}


def build_messages(state: AgentState) -> list:
    """组装送给 LLM 的 messages。流式与非流式共用，避免 system prompt 各写一份。"""
    message = state.get("message") or ""
    intent = state.get("intent") or "PSYCH_EMOTION"
    docs = state.get("retrieved") or []
    history = state.get("history") or []

    # ---- 1. 组装 system prompt ----
    style_map = load_json_prompt("reply_style")
    style = style_map.get(intent) or style_map.get("PSYCH_EMOTION", "")
    system_parts = [load_prompt("reply_base"), style]

    context = build_context(docs)
    if context:
        system_parts.append("【参考资料】\n" + context)
    else:
        system_parts.append("【参考资料】无。请基于通用心理健康常识回答，不要编造具体数据或研究结论。")

    # ---- 2. 组装 messages：历史 + 本轮 ----
    messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for item in history[:-1] if history and history[-1].get("content") == message else history:
        role = item.get("role")
        if role in ("user", "assistant") and item.get("content"):
            messages.append({"role": role, "content": item["content"]})
    messages.append({"role": "user", "content": message})
    return messages


def finalize_reply(reply: str, risk_level: str) -> str:
    """
    收尾：高危回复强制附上真实求助资源 + 人工入口。
    这段硬编码而不交给模型生成，因为它不能出错，模型可能遗漏或被诱导绕过。
    """
    text = (reply or "").strip()
    if risk_level == "HIGH":
        logger.warning("高危会话生成回复，附带危机干预资源")
        text = (
            f"{text}\n\n"
            "——\n"
            "以下资源请立刻使用，任何时候都有效：\n"
            f"{CRISIS_RESOURCES}"
        ).strip()
    return apply_safety(text, risk_level)


def generate_node(state: AgentState) -> dict:
    """LangGraph 节点：生成最终回复（非流式）"""
    intent = state.get("intent") or "PSYCH_EMOTION"

    reply, tokens = get_llm().chat(
        messages=build_messages(state),
        mock_text=MOCK_REPLIES.get(intent, MOCK_REPLIES["PSYCH_EMOTION"]),
    )

    return {
        "reply": finalize_reply(reply, state.get("risk_level") or "LOW"),
        "tokens": tokens,
    }
