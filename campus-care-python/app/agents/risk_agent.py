"""Agent 3：风险预警。

规则优先、模型兜底：危机识别漏判代价太大，所以用显式关键词库 + 否定词判定等级，
LLM 只负责生成给辅导员的处置建议。

  HIGH   自杀/自残/轻生等明确表达，必须立即人工介入
  MEDIUM 强烈负面情绪词（绝望、崩溃、撑不住等），需要关注
  LOW    其余
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List

from app.agents.state import AgentState
from app.llm import get_llm

logger = logging.getLogger(__name__)

# ---------------- 关键词库 ----------------

HIGH_RISK_WORDS: List[str] = [
    "自杀", "自尽", "想死", "去死", "不想活", "活不下去", "轻生", "结束生命", "了结自己",
    "自残", "自伤", "割腕", "割手", "跳楼", "跳河", "上吊", "烧炭", "吞药", "安眠药自杀",
    "遗书", "遗言", "交代后事", "解脱了", "消失掉", "永远睡过去", "再也不醒",
]

MEDIUM_RISK_WORDS: List[str] = [
    "抑郁", "焦虑", "崩溃", "绝望", "没意义", "毫无意义", "撑不住", "熬不下去", "痛苦的活着",
    "失眠", "睡不着", "整夜睡不着", "想哭", "一直哭", "压力好大", "压力太大", "活着好累",
    "好累", "很累", "自我否定", "一无是处", "废物", "不想说话", "社交恐惧", "被孤立", "被霸凌",
    "恐慌", "心慌", "胸闷", "吃不下", "暴食", "厌学", "想逃", "恨自己",
]

# 出现这些词会让"高危词"失效（例如"我没有想死"）
NEGATION_WORDS: List[str] = ["没有", "不是", "不会", "不再", "别", "不要", "并没有", "从来没"]

# 出现这些词说明是转述/关心他人，风险等级下调（但仍留痕给辅导员看）
THIRD_PARTY_WORDS: List[str] = ["我朋友", "我同学", "我室友", "他说", "她说", "有人"]

# 全国心理援助资源（高危时必须给出）
CRISIS_RESOURCES = (
    "全国24小时心理援助热线：400-161-9995（希望24热线）\n"
    "教育部华中师范大学心理援助热线：4009-678-320\n"
    "北京心理危机研究与干预中心：010-82951332\n"
    "紧急情况请直接拨打 120 或联系学校保卫处、辅导员"
)


def detect_keywords(text: str) -> Dict[str, object]:
    """规则判定：返回命中词、是否高危、是否中危。"""
    text = text or ""
    high_hits = [w for w in HIGH_RISK_WORDS if w in text]
    medium_hits = [w for w in MEDIUM_RISK_WORDS if w in text]

    # 否定词紧邻高危词 → 视为否定表达（"我没有想死"），降级为无风险
    if high_hits and any(neg + w in text for neg in NEGATION_WORDS for w in high_hits):
        high_hits = [w for w in high_hits
                     if not any(re.search(re.escape(neg + w), text) for neg in NEGATION_WORDS)]

    # 转述他人 → 下调等级（不是当事人直接风险，但需要关注）
    third_party = any(w in text for w in THIRD_PARTY_WORDS)

    return {
        "keywords": high_hits + medium_hits,
        "high_hits": high_hits,
        "medium_hits": medium_hits,
        "is_high": bool(high_hits),
        "is_medium": bool(medium_hits) and not high_hits,
        "third_party": third_party,
    }


def risk_node(state: AgentState) -> dict:
    """LangGraph 节点：风险等级判定 + 生成处置建议"""
    message = state.get("message") or ""
    result = detect_keywords(message)

    if result["is_high"]:
        level = "HIGH"
    elif result["is_medium"] or state.get("intent") == "RISK_ALERT":
        level = "MEDIUM"
    else:
        level = "LOW"

    # 转述他人 + 无其他风险 → 降一档，但不能低于 LOW
    if result["third_party"] and level == "MEDIUM":
        level = "LOW"

    keywords = list(result["keywords"])

    suggestion = ""
    if level in ("HIGH", "MEDIUM"):
        suggestion = _build_suggestion(message, level, keywords)

    logger.info("风险判定: level=%s, keywords=%s", level, keywords)
    return {
        "risk_level": level,
        "keywords": keywords,
        "ai_suggestion": suggestion,
    }


def _build_suggestion(message: str, level: str, keywords: List[str]) -> str:
    """让 LLM 生成给辅导员的处置建议；不可用时用模板兜底。"""
    template = (
        f"【{level}】学生表达中出现 {'、'.join(keywords) or '强烈负面情绪'}。"
        "建议：1) 24小时内主动联系学生进行一对一沟通；"
        "2) 评估自伤风险与支持系统（室友/家人/朋友）；"
        "3) 必要时联系校心理中心安排面询，高危情况启动危机干预流程。"
    )

    llm = get_llm()
    prompt = (
        "你是高校心理危机干预的辅助系统。请针对下面这条学生发言，"
        "给辅导员写 2-3 条可执行的处置建议，语气专业、简短，不要复述原话，不要给医学诊断。\n\n"
        f"学生发言：{message}"
    )
    text, _ = llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        mock_text=template,
    )
    return text.strip() or template
