"""混合检索测试：分词、BM25 排序、RRF 融合、重排、阈值过滤。

全部不依赖 chromadb / sentence-transformers —— vector_search=None 时
检索器退化为纯 BM25，这正是 CI 里跑的路径，也顺带验证了降级可用。
"""
from __future__ import annotations

from app.rag.hybrid import HybridRetriever, LightBM25, rrf_fuse, tokenize


def test_tokenize_emits_cjk_chars_and_bigrams():
    tokens = tokenize("失眠了")
    assert "失" in tokens and "眠" in tokens
    assert "失眠" in tokens


def test_tokenize_handles_ascii():
    tokens = tokenize("PHQ-9 量表")
    assert "phq" in tokens
    assert "9" in tokens


def test_bm25_ranks_exact_match_first():
    docs = [
        {"id": "a", "title": "失眠了怎么办", "content": "固定起床时间，睡前离开手机。"},
        {"id": "b", "title": "考试焦虑", "content": "把担心的事写下来。"},
    ]
    bm25 = LightBM25(docs)
    hits = bm25.search("失眠", top_k=2)
    assert hits
    assert bm25.doc_ids[hits[0][0]] == "a"


def test_rrf_favors_document_hit_by_both_channels():
    """两路都命中的文档，融合分必须高于只被一路命中的。"""
    fused = rrf_fuse([["a", "b"], ["b", "c"]])
    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]


def test_rrf_ignores_score_scale():
    """RRF 只看名次：两路各自的第一名得分相等。"""
    fused = rrf_fuse([["x"], ["y"]])
    assert fused["x"] == fused["y"]


def test_hybrid_search_without_vector_falls_back_to_bm25():
    """没装 chromadb 时检索应退化为纯 BM25，而不是抛异常。"""
    retriever = HybridRetriever(vector_search=None)
    hits = retriever.search("失眠怎么办", top_k=3, min_score=0.0)
    assert hits
    assert any("失眠" in h["title"] for h in hits)


def test_hybrid_marks_retrieval_channel():
    retriever = HybridRetriever(vector_search=None)
    hits = retriever.search("考试焦虑怎么缓解", top_k=3, min_score=0.0)
    assert hits
    assert hits[0]["retrieval"] == "bm25"


def test_min_score_filters_everything_out():
    retriever = HybridRetriever(vector_search=None)
    assert retriever.search("失眠", top_k=3, min_score=1.01) == []


def test_empty_query_returns_empty():
    retriever = HybridRetriever(vector_search=None)
    assert retriever.search("", top_k=3) == []


def test_rerank_prefers_title_hit():
    """标题命中的文档应排在「正文里顺带提一句」的前面。"""
    docs = [
        {"id": "a", "title": "无关主题", "content": "这里顺带提了一句失眠。"},
        {"id": "b", "title": "失眠了怎么办", "content": "固定起床时间，睡前离开手机。"},
    ]
    retriever = HybridRetriever(vector_search=None, faqs=docs)
    hits = retriever.search("失眠怎么办", top_k=2, min_score=0.0)
    assert hits
    assert hits[0]["id"] == "b"


def test_vector_channel_is_used_when_provided():
    """给了向量检索函数时应被调用，且结果能进入融合。"""
    calls = {"n": 0}

    def fake_vector(query: str, top_k: int):
        calls["n"] += 1
        return [{
            "id": "faq-001", "title": "失眠了怎么办", "category": "睡眠",
            "content": "固定起床时间。", "score": 0.88, "source": "x", "retrieval": "vector",
        }]

    retriever = HybridRetriever(vector_search=fake_vector)
    hits = retriever.search("睡不着", top_k=3, min_score=0.0)
    assert calls["n"] == 1
    assert any(h["id"] == "faq-001" for h in hits)


def test_vector_channel_failure_does_not_break_search():
    """向量库挂了（没装/没建库）也必须能返回 BM25 的结果。"""

    def broken_vector(query: str, top_k: int):
        raise RuntimeError("chromadb 不可用")

    retriever = HybridRetriever(vector_search=broken_vector)
    hits = retriever.search("失眠怎么办", top_k=3, min_score=0.0)
    assert hits
