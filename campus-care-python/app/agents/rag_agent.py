"""Agent 2：RAG 知识检索。

职责：拿学生的问题去 ChromaDB 里检索最相关的心理 FAQ，作为后续生成回复的依据。
检出后把 doc 列表和来源标题写回 state。若检索不到，则标记无命中，
由生成节点改用通用建议，避免 LLM 凭空编造（幻觉）。
"""
from __future__ import annotations

import logging

from app.agents.state import AgentState
from app.rag.store import get_store

logger = logging.getLogger(__name__)


def rag_node(state: AgentState) -> dict:
    """LangGraph 节点：向量检索"""
    query = (state.get("message") or "").strip()
    store = get_store()

    docs = store.search(query)

    if not docs:
        logger.info("RAG 未命中，生成节点将走通用建议")
        return {"retrieved": [], "rag_sources": []}

    sources = [f"{d['title']}（相似度 {d['score']:.2f}）" for d in docs]
    logger.info("RAG 命中 %d 条: %s", len(docs), [d["title"] for d in docs])
    return {"retrieved": docs, "rag_sources": sources}


def build_context(docs: list) -> str:
    """把检索结果拼成给 LLM 看的上下文块。"""
    if not docs:
        return ""
    blocks = []
    for i, doc in enumerate(docs, 1):
        blocks.append(
            f"[资料{i}] 主题：{doc['title']}（分类：{doc['category']}）\n{doc['content']}"
        )
    return "\n\n".join(blocks)
