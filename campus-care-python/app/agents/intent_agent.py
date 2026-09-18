"""Agent 1：意图识别。

先规则后模型：命中高危词直接判 RISK_ALERT（省一次调用，也避免模型漏判），
其余交给 LLM 做四分类。输出 intent + intent_reason。
"""
from __future__ import annotations

import logging

from app.agents.risk_agent import detect_keywords
from app.agents.state import AgentState
from app.llm import get_llm

logger = logging.getLogger(__name__)

INTENT_PSYCH = "PSYCH_EMOTION"      # 心理倾诉：倾诉情绪、宣泄
INTENT_KNOWLEDGE = "KNOWLEDGE_QUERY"  # 知识查询：问"怎么办""是什么"
INTENT_RISK = "RISK_ALERT"          # 高危预警
INTENT_CHITCHAT = "CHITCHAT"        # 闲聊

VALID_INTENTS = {INTENT_PSYCH, INTENT_KNOWLEDGE, INTENT_RISK, INTENT_CHITCHAT}

INTENT_SYSTEM_PROMPT = """你是校园心理咨询平台的意图识别模块。请判断学生这句话属于哪一类，只输出一个标签，不要解释。

分类标准：
- PSYCH_EMOTION：倾诉自己的情绪或处境（如"我最近很难过""压力好大"）
- KNOWLEDGE_QUERY：询问心理知识或方法（如"焦虑怎么办""怎么改善失眠"）
- RISK_ALERT：出现自杀、自残、轻生等危及生命的表达
- CHITCHAT：打招呼、闲聊、与本平台无关的问题

只允许输出以下四个词之一：PSYCH_EMOTION、KNOWLEDGE_QUERY、RISK_ALERT、CHITCHAT"""


def intent_node(state: AgentState) -> dict:
    """LangGraph 节点：识别意图"""
    message = (state.get("message") or "").strip()

    # ---- 第一道：规则快速通道 ----
    hits = detect_keywords(message)
    if hits["is_high"]:
        logger.info("意图识别命中高危规则，直接判定 RISK_ALERT")
        return {"intent": INTENT_RISK, "intent_reason": "命中高危关键词规则: " + "、".join(hits["keywords"])}

    # ---- 第二道：LLM 分类 ----
    llm = get_llm()
    text, _ = llm.chat(
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        temperature=0.0,   # 分类任务要确定性，温度拉到最低
        mock_text=_rule_based_intent(message),
    )

    intent = _parse_intent(text)
    logger.info("意图识别结果: %s", intent)
    return {"intent": intent, "intent_reason": f"LLM 判定：{text[:40]}"}


def _parse_intent(text: str) -> str:
    """从模型输出里抠出合法标签，识别不出来就兜底为心理倾诉。"""
    if not text:
        return INTENT_PSYCH
    upper = text.upper()
    for intent in VALID_INTENTS:
        if intent in upper:
            return intent
    return INTENT_PSYCH


def _rule_based_intent(message: str) -> str:
    """mock 模式下的规则兜底。

    词表直接决定 mock 模式下会不会走 RAG 分支：漏了「办法」，
    "有什么办法吗" 就会被判成 PSYCH_EMOTION，RAG 节点永远不执行。
    所以求教类词要同时收疑问式（怎么/如何）和求助式（办法/建议）。
    """
    knowledge_hints = [
        # 疑问式
        "怎么办", "怎么", "怎样", "如何", "是什么", "为什么", "吗？", "吗?", "呢？",
        # 求助式
        "办法", "方法", "建议", "技巧", "措施", "缓解", "改善", "调节", "调整",
        "治疗", "疗法", "科普", "介绍", "讲讲",
    ]
    chitchat_hints = ["你好", "在吗", "hi", "hello", "谢谢", "再见", "你是谁"]
    lower = message.lower()

    if any(h in message for h in knowledge_hints):
        return INTENT_KNOWLEDGE
    if any(h in lower for h in chitchat_hints) and len(message) <= 12:
        return INTENT_CHITCHAT
    return INTENT_PSYCH


# 路由函数：LangGraph 的条件边用它决定下一个节点
def route_by_intent(state: AgentState) -> str:
    """知识查询才去检索知识库，其余直接进风险预警。"""
    if state.get("intent") == INTENT_KNOWLEDGE:
        return "rag"
    return "risk"
