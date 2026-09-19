"""LangGraph 共享状态定义。

整个多 Agent 链路（意图识别 → RAG 检索 → 风险预警 → 生成回复）
靠这一个 TypedDict 在节点之间传数据。
"""
from typing import List, TypedDict


class RetrievedDoc(TypedDict):
    """RAG 检索命中的一条 FAQ"""
    title: str
    content: str
    category: str
    score: float
    source: str


class AgentState(TypedDict, total=False):
    # ---- 输入 ----
    user_id: int
    conversation_id: int
    message: str
    history: List[dict]

    # ---- 意图识别 Agent 产出 ----
    intent: str            # PSYCH_EMOTION / KNOWLEDGE_QUERY / RISK_ALERT / CHITCHAT
    intent_reason: str

    # ---- RAG 检索 Agent 产出 ----
    retrieved: List[RetrievedDoc]
    rag_sources: List[str]

    # ---- 风险预警 Agent 产出 ----
    risk_level: str        # LOW / MEDIUM / HIGH
    keywords: List[str]
    ai_suggestion: str

    # ---- 生成节点产出 ----
    reply: str
    tokens: int
