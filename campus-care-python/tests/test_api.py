"""HTTP 接口契约测试（Mock 模式，不联网、不消耗额度）。

重点验证「新增字段」和「高危兜底」：
Java 侧就是靠这几个字段决定要不要建工单、前端要不要挂人工入口的，
字段丢了接口不报错，但业务会静默失效。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_exposes_retrieval_mode_and_prompt_versions():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["status"] == "UP"
    assert data["llmMode"] == "mock"
    assert data["retrievalMode"] in ("hybrid", "vector")
    assert data["promptVersions"]


def test_chat_high_risk_requires_handoff():
    resp = client.post("/api/agent/chat", json={
        "userId": 1, "conversationId": 1,
        "message": "我觉得活着没意义，想结束生命", "history": [],
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["riskLevel"] == "HIGH"
    assert data["needHandoff"] is True
    assert data["disclaimer"]
    assert data["traceId"]
    # 高危必须带上真实求助资源，这一段是硬编码兜底，不能依赖模型
    assert "400-161-9995" in data["reply"]


def test_chat_low_risk_has_no_handoff():
    resp = client.post("/api/agent/chat", json={
        "userId": 1, "conversationId": 1, "message": "你好呀", "history": [],
    })
    data = resp.json()["data"]
    assert data["riskLevel"] == "LOW"
    assert data["needHandoff"] is False


def test_chat_echoes_trace_id():
    resp = client.post("/api/agent/chat", json={
        "userId": 1, "conversationId": 1, "message": "你好", "history": [],
        "traceId": "trace-abc-123",
    })
    assert resp.json()["data"]["traceId"] == "trace-abc-123"


def test_kb_search_returns_scored_hits():
    resp = client.get("/api/agent/kb/search", params={"q": "失眠怎么办", "topK": 3})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert data
    assert "score" in data[0]
    assert "retrieval" in data[0]


def test_kb_categories_non_empty():
    resp = client.get("/api/agent/kb/categories")
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert data
    assert all("name" in item and "count" in item for item in data)
