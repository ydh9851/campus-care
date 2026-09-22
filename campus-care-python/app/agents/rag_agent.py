"""Agent 2：RAG 知识检索。

职责：拿学生的问题去知识库里检索最相关的心理 FAQ，作为后续生成回复的依据。

检索策略由 RETRIEVAL_MODE 决定：
    hybrid（默认）—— BM25 字面 + 向量语义双路召回，RRF 融合后轻量重排。
                      语义改写的提问靠向量，专有名词/短语靠 BM25，互补。
    vector        —— 只走向量检索（旧行为，保留用于对比两套方案的召回差异）。

检出后把 doc 列表和来源标题写回 state。若检索不到，则标记无命中，
由生成节点改用通用建议，避免 LLM 凭空编造（幻觉）。
"""
from __future__ import annotations

import logging
from typing import List

from app.agents.state import AgentState, RetrievedDoc
from app.config import get_settings
from app.rag.embedding import get_embedder
from app.rag.hybrid import get_hybrid_retriever
from app.rag.store import get_store

logger = logging.getLogger(__name__)


def default_min_score() -> float:
    """相关度阈值：配置优先，否则跟随向量模型自身（哈希 0.15 / 语义 0.35）。"""
    settings = get_settings()
    if settings.retrieval_min_score is not None:
        return float(settings.retrieval_min_score)
    return float(get_embedder().min_relevant_score)


def retrieve(query: str, top_k: int | None = None, mode: str | None = None) -> List[RetrievedDoc]:
    """统一的检索入口，供节点与 /agent/kb/search 复用。

    :param mode: 临时指定检索模式（hybrid / vector），不传则用配置。
                 给调试接口用 —— 同一个问题用两种模式各查一次，好不好一眼就能对比。
    """
    settings = get_settings()
    k = top_k or settings.top_k
    mode = (mode or settings.retrieval_mode or "hybrid").lower()

    if mode == "vector":
        return get_store().search(query, top_k=k)

    return get_hybrid_retriever().search(query, top_k=k, min_score=default_min_score())


def rag_node(state: AgentState) -> dict:
    """LangGraph 节点：知识库检索"""
    query = (state.get("message") or "").strip()
    docs = retrieve(query)

    if not docs:
        logger.info("RAG 未命中，生成节点将走通用建议")
        return {"retrieved": [], "rag_sources": []}

    sources = [
        f"{d['title']}（相关度 {float(d.get('score', 0.0)):.2f}）"
        for d in docs
    ]
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
