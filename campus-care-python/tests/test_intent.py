"""意图识别测试：标签解析容错、Mock 规则兜底、条件路由。"""
from __future__ import annotations

from app.agents.intent_agent import (
    INTENT_CHITCHAT,
    INTENT_KNOWLEDGE,
    INTENT_PSYCH,
    INTENT_RISK,
    _parse_intent,
    _rule_based_intent,
    route_by_intent,
)


def test_parse_intent_picks_valid_label():
    assert _parse_intent("KNOWLEDGE_QUERY") == INTENT_KNOWLEDGE
    assert _parse_intent("判断结果：CHITCHAT") == INTENT_CHITCHAT


def test_parse_intent_falls_back_to_psych():
    assert _parse_intent("") == INTENT_PSYCH
    assert _parse_intent("这是一个模型瞎编的标签") == INTENT_PSYCH


def test_rule_based_intent_detects_knowledge():
    assert _rule_based_intent("焦虑怎么办") == INTENT_KNOWLEDGE
    assert _rule_based_intent("有什么办法吗") == INTENT_KNOWLEDGE


def test_rule_based_intent_detects_chitchat():
    assert _rule_based_intent("你好") == INTENT_CHITCHAT


def test_rule_based_intent_defaults_to_psych():
    assert _rule_based_intent("最近真的很累") == INTENT_PSYCH


def test_route_by_intent():
    assert route_by_intent({"intent": INTENT_KNOWLEDGE}) == "rag"
    assert route_by_intent({"intent": INTENT_PSYCH}) == "risk"
    assert route_by_intent({"intent": INTENT_RISK}) == "risk"
    assert route_by_intent({"intent": INTENT_CHITCHAT}) == "risk"
