"""LangGraph 共享状态定义。

整个多 Agent 链路（意图识别 → RAG 检索 → 风险预警 → 生成回复）
靠这一个 TypedDict 在节点之间传数据。
"""
from typing import List, TypedDict


class RetrievedDoc(TypedDict, total=False):
    """RAG 检索命中的一条 FAQ。

    除内容字段外，还带检索过程信息：
      score       最终相关度（0~1），用于展示与阈值过滤
      id          语料 id，混合检索靠它对齐「向量路」和「BM25 路」
      retrieval   该条来自哪一路：vector / bm25 / both
      fusion      RRF 融合分（很小，仅调试用）
      coverage    查询词在正文里的覆盖率（轻量重排的依据）
      rerankScore 轻量重排后的排序分
    """
    id: str
    title: str
    content: str
    category: str
    score: float
    source: str
    retrieval: str
    fusion: float
    coverage: float
    rerankScore: float


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
