"""LangGraph 状态机：把各 Agent 串成一条链路。

    START → 意图识别 ─┬─(知识查询)→ RAG 检索 ─┐
                      └─(其他意图)────────────┴→ 风险预警 → 生成回复 → END

用图而不是一串 if-else：分支条件显式可见，state 在节点间传递便于逐步打日志和单测，
后续加"转人工""重试"也只需加节点和边。
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.intent_agent import intent_node, route_by_intent
from app.agents.rag_agent import rag_node
from app.agents.reply_agent import generate_node
from app.agents.risk_agent import risk_node
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

# 节点名常量，避免散落魔法字符串。
# 注意节点名不能与 AgentState 的 key 重名，否则 LangGraph 编译会抛
# "'xxx' is already being used as a state key"，所以意图节点用 intent_detect。
NODE_INTENT = "intent_detect"
NODE_RAG = "rag"
NODE_RISK = "risk"
NODE_GENERATE = "generate"


def build_graph():
    """构建并编译状态机"""
    builder = StateGraph(AgentState)

    builder.add_node(NODE_INTENT, intent_node)
    builder.add_node(NODE_RAG, rag_node)
    builder.add_node(NODE_RISK, risk_node)
    builder.add_node(NODE_GENERATE, generate_node)

    builder.add_edge(START, NODE_INTENT)
    # 条件边：意图识别后按意图分流
    builder.add_conditional_edges(
        NODE_INTENT,
        route_by_intent,
        {NODE_RAG: NODE_RAG, NODE_RISK: NODE_RISK},
    )
    builder.add_edge(NODE_RAG, NODE_RISK)
    builder.add_edge(NODE_RISK, NODE_GENERATE)
    builder.add_edge(NODE_GENERATE, END)

    graph = builder.compile()
    logger.info("LangGraph 状态机编译完成")
    return graph


@lru_cache
def get_graph():
    """编译一次复用（LangGraph 的 compiled graph 是线程安全的）"""
    return build_graph()


def mermaid() -> str:
    """导出 Mermaid 流程图源码，可直接贴进 README 生成架构图"""
    try:
        return get_graph().get_graph().draw_mermaid()
    except Exception as e:  # pragma: no cover
        logger.warning("导出 Mermaid 失败: %s", e)
        return "graph TD; START-->intent; intent-->rag; intent-->risk; rag-->risk; risk-->generate; generate-->END;"
