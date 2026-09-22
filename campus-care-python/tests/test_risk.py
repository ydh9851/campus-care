"""风险研判的边界测试。

风险识别是「宁可误报不可漏报」的模块，所以测试重点全在边界：
否定表达、转述他人、口语化高危词（笑死/烦死），以及情绪词的过敏感。
"""
from __future__ import annotations

from app.agents.risk_agent import classify_risk, detect_keywords, risk_node


def test_high_risk_explicit():
    assert classify_risk("我想死")["level"] == "HIGH"
    assert classify_risk("我昨天割腕了")["level"] == "HIGH"
    assert classify_risk("我在写遗书")["level"] == "HIGH"


def test_medium_risk_emotion():
    assert classify_risk("最近特别抑郁，什么都提不起劲")["level"] == "MEDIUM"
    assert classify_risk("我快崩溃了")["level"] == "MEDIUM"


def test_negation_downgrades_high_risk():
    """「我没有想死」不能判成高危 —— 这是最容易出事故的假阳性。"""
    verdict = classify_risk("我没有想死，别担心")
    assert verdict["level"] == "LOW"
    assert "想死" not in verdict["keywords"]


def test_casual_death_words_are_not_crisis():
    """「笑死」「烦死」是口语，不能触发高危。"""
    assert classify_risk("笑死我了，哈哈哈哈")["level"] == "LOW"
    assert classify_risk("烦死了，作业好多")["level"] == "LOW"


def test_third_party_downgrades_medium():
    """转述他人 + 中危词 → 降为 LOW（不是当事人直接风险）。"""
    assert classify_risk("我朋友最近压力好大，我想帮帮他")["level"] == "LOW"


def test_third_party_keeps_high():
    """转述他人但含明确高危词时保守判 HIGH —— 安全优先，宁可误报。"""
    assert classify_risk("我室友说他想自杀")["level"] == "HIGH"


def test_intent_risk_alert_raises_floor():
    """意图侧已识别为危机时，风险等级不能低于 MEDIUM。"""
    assert classify_risk("我最近很不好", intent="RISK_ALERT")["level"] == "MEDIUM"


def test_detect_keywords_returns_hits():
    result = detect_keywords("我觉得活着没意义，想结束生命")
    assert result["is_high"] is True
    assert "结束生命" in result["keywords"]


def test_risk_node_produces_suggestion_for_high():
    """节点层：高危必须产出给辅导员的处置建议（Mock 模式走模板兜底）。"""
    out = risk_node({"message": "我想死", "intent": "RISK_ALERT"})
    assert out["risk_level"] == "HIGH"
    assert out["ai_suggestion"].strip()


def test_risk_node_low_has_no_suggestion():
    out = risk_node({"message": "你好呀", "intent": "CHITCHAT"})
    assert out["risk_level"] == "LOW"
    assert out["ai_suggestion"] == ""
