"""混合检索：BM25（字面）+ 向量（语义）+ RRF 融合 + 轻量重排。

为什么要在纯向量检索之外加这一路：
    向量检索擅长「翻来覆去睡不着」→「失眠了怎么办」这类语义改写，
    但它对专有名词、数字、精确短语不敏感；
    BM25 正好相反，字面命中就打高分。两路召回互补，是 RAG 的标准做法。
    实测里最典型的收益是「4-7-8 呼吸法」「PHQ-9」这类词 —— 纯向量容易漂移，BM25 一击即中。

为什么 RRF 而不是加权求和：
    向量分（余弦，0~1，密集）和 BM25 分（无上界，稀疏）量纲完全不同，
    直接加权要先做归一化，而归一化本身又依赖分数分布，调参极其脆弱。
    RRF（Reciprocal Rank Fusion）只用「名次」不用「分数」，天然免疫量纲问题，
    是工业界最常用的融合方式。

为什么自己实现 BM25 而不引入 rank-bm25：
    这个模块要求零新增依赖就能跑（CI 只装轻量依赖），
    而 BM25Okapi 的核心公式只有二十来行，自己写反而更可控、更好单测。

重排说明：
    这里没有引入 cross-encoder（那要再下几百 MB 模型），
    而是用「RRF 融合分 + 查询词覆盖率 + 标题命中」做轻量重排，
    足以压掉「向量分数虚高但内容和问题无关」的结果。真要用模型重排，替换 _rerank 即可。
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Callable, Dict, List, Optional, Sequence

from app.agents.state import RetrievedDoc
from app.rag.loader import build_document_text, load_faq

logger = logging.getLogger(__name__)

_CJK = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD = re.compile(r"[a-z0-9]+")

# 向量检索函数签名：(query, top_k) -> List[RetrievedDoc]
VectorSearch = Callable[[str, int], List[RetrievedDoc]]


# ---------------------------------------------------------------------------
# 分词：中文按「单字 + 双字」切，英文/数字按词切
#
# 中文不做分词器（jieba 体积大且对短文本收益有限）：
#   单字保证召回，双字保证精度 —— 「失眠」比「失」「眠」更能锁定主题，
#   而单字能兜住「失恋」「焦虑」里没被双字覆盖的字面命中。
# ---------------------------------------------------------------------------
def tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    tokens: List[str] = list(_ASCII_WORD.findall(text))
    cjk = _CJK.findall(text)
    tokens.extend(cjk)
    tokens.extend(a + b for a, b in zip(cjk, cjk[1:]))
    return tokens


def _coverage(query_tokens: Sequence[str], doc_tokens: Sequence[str]) -> float:
    """查询词在文档里的覆盖率（0~1）。查询词集合去重，避免长查询被反复计入。"""
    q = set(query_tokens)
    if not q:
        return 0.0
    return len(q & set(doc_tokens)) / len(q)


# ---------------------------------------------------------------------------
# BM25（Okapi），k1=1.5 / b=0.75 是文献里的常用默认值
# ---------------------------------------------------------------------------
class LightBM25:
    """轻量 BM25 倒排：语料是静态 FAQ，建一次索引反复查。"""

    def __init__(self, docs: List[dict], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_ids: List[str] = []
        self.doc_tokens: List[List[str]] = []

        for i, item in enumerate(docs):
            self.doc_ids.append(str(item.get("id") or f"doc-{i}"))
            # 与向量化用同一份文本（标题重复加权），保证两路看到的内容一致
            self.doc_tokens.append(tokenize(build_document_text(item)))

        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        self.tf: List[Counter] = [Counter(t) for t in self.doc_tokens]

        df: Counter = Counter()
        for tokens in self.doc_tokens:
            df.update(set(tokens))
        n = len(self.doc_tokens)
        # BM25 的 idf 变体：加 1 后恒为正，避免高频词出现负分
        self.idf: Dict[str, float] = {
            w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()
        }

    def search(self, query: str, top_k: int = 8) -> List[tuple[int, float]]:
        """返回 [(doc 下标, BM25 分)]，按分数倒序。"""
        q_tokens = tokenize(query)
        if not q_tokens or not self.doc_tokens:
            return []

        scored: List[tuple[int, float]] = []
        for i, tf in enumerate(self.tf):
            score = 0.0
            for word in q_tokens:
                freq = tf.get(word)
                if not freq:
                    continue
                idf = self.idf.get(word, 0.0)
                denom = freq + self.k1 * (1 - self.b + self.b * self.doc_len[i] / (self.avgdl or 1.0))
                score += idf * freq * (self.k1 + 1) / denom
            if score > 0:
                scored.append((i, score))

        scored.sort(key=lambda pair: -pair[1])
        return scored[:top_k]


# ---------------------------------------------------------------------------
# RRF 融合
# ---------------------------------------------------------------------------
def rrf_fuse(rankings: Sequence[Sequence[str]], k: int = 60) -> Dict[str, float]:
    """Reciprocal Rank Fusion：把多路「有序 id 列表」融成一个分数表。

    某文档在一路里排第 rank 位，贡献 1/(k+rank)；多路命中就累加。
    k 取 60 是原论文的经验值，作用是压平「第 1 名和第 3 名」的差距，
    避免单路的高排名完全主导结果。
    """
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


class HybridRetriever:
    """BM25 + 向量混合检索器。

    :param vector_search: 向量检索函数（可传 None —— 例如没装 chromadb 时只跑 BM25）
    :param faqs:          BM25 语料，默认从 psych_faq.json 加载
    """

    def __init__(
        self,
        vector_search: Optional[VectorSearch] = None,
        faqs: Optional[List[dict]] = None,
        rrf_k: int = 60,
        pool: int = 8,
        bm25_weight: float = 0.9,
        rerank: bool = True,
    ) -> None:
        self.vector_search = vector_search
        self.faqs = faqs if faqs is not None else load_faq()
        self.rrf_k = rrf_k
        self.pool = pool
        self.bm25_weight = bm25_weight
        self.rerank_enabled = rerank

        self._bm25 = LightBM25(self.faqs) if self.faqs else None
        self._by_id: Dict[str, RetrievedDoc] = {
            str(item.get("id") or f"doc-{i}"): self._to_doc(item)
            for i, item in enumerate(self.faqs)
        }

    @staticmethod
    def _to_doc(item: dict) -> RetrievedDoc:
        return {
            "id": str(item.get("id", "")),
            "title": item.get("title", ""),
            "category": item.get("category", "通用"),
            "content": item.get("content", ""),
            "source": item.get("source", ""),
            "score": 0.0,
        }

    def search(self, query: str, top_k: int = 3, min_score: float = 0.0) -> List[RetrievedDoc]:
        query = (query or "").strip()
        if not query:
            return []

        vec_hits = self._safe_vector_search(query)
        bm25_hits = self._bm25.search(query, top_k=self.pool) if self._bm25 else []

        if not vec_hits and not bm25_hits:
            return []

        # ---- 1. 两路名次表（RRF 的输入只需要 id 顺序）----
        vec_ids = [str(d.get("id", "")) for d in vec_hits]
        bm25_ids = [self._bm25.doc_ids[i] for i, _ in bm25_hits] if self._bm25 else []
        fused = rrf_fuse([vec_ids, bm25_ids], k=self.rrf_k)

        vec_score = {str(d.get("id", "")): float(d.get("score") or 0.0) for d in vec_hits}
        bm25_score = {
            self._bm25.doc_ids[i]: s for i, s in bm25_hits
        } if self._bm25 else {}
        max_bm25 = max(bm25_score.values()) if bm25_score else 0.0

        # ---- 2. 归一化打分：用于展示与阈值过滤，统一在 0~1 ----
        # 向量分本身已是 0~1 余弦；BM25 分除以本查询最高分得到相对分。
        # 取两者较大值，语义是「任一路认为它相关，它就算相关」。
        merged: List[RetrievedDoc] = []
        for doc_id, fusion in fused.items():
            base = self._by_id.get(doc_id)
            if base is None:
                continue
            v = vec_score.get(doc_id, 0.0)
            b = (bm25_score.get(doc_id, 0.0) / max_bm25) if max_bm25 else 0.0
            score = max(v, b * self.bm25_weight)

            retrieval = "both" if (doc_id in vec_score and doc_id in bm25_score) else (
                "vector" if doc_id in vec_score else "bm25"
            )
            doc: RetrievedDoc = dict(base)  # type: ignore[assignment]
            doc["score"] = round(score, 4)
            doc["fusion"] = round(fusion, 6)
            doc["retrieval"] = retrieval
            merged.append(doc)

        # ---- 3. 轻量重排 ----
        if self.rerank_enabled:
            merged = self._rerank(query, merged)

        # ---- 4. 阈值过滤 + 截断 ----
        kept = [d for d in merged if float(d.get("score", 0.0)) >= min_score]
        result = kept[:top_k]
        logger.info(
            "混合检索 '%s' -> 向量 %d / BM25 %d / 融合 %d / 保留 %d",
            query[:20], len(vec_hits), len(bm25_hits), len(merged), len(result),
        )
        return result

    def _safe_vector_search(self, query: str) -> List[RetrievedDoc]:
        """向量检索可能因为没装 chromadb / 模型没下载而不可用，这里兜住不让整条链路挂掉。"""
        if self.vector_search is None:
            return []
        try:
            return self.vector_search(query, self.pool) or []
        except Exception as e:  # noqa: BLE001
            logger.warning("向量检索不可用，本次仅使用 BM25：%s", e)
            return []

    def _rerank(self, query: str, hits: List[RetrievedDoc]) -> List[RetrievedDoc]:
        """轻量重排：融合分主导(0.5) + 相关度(0.4) + 覆盖率微调(0.1) + 标题命中(0.05)。

        为什么以融合分为主：
            RRF 已经综合了「两路各自排第几」这个最重要的信号。
            如果改成字面覆盖率主导，等于把向量那一路的语义贡献直接抹掉 ——
            实测这么排之后 Recall@1 会从 29% 掉到 12%，比纯 BM25 还差。
            覆盖率只留 0.1，作用是在同分时压掉「正文完全没提到查询词」的结果。

        另一个坑：融合分不能按固定的 1/(k+1) 归一化。
            1/(60+1) 是单路第一名的上限，固定除它会让所有结果都变成 1.0，
            「融合分」这个维度当场失去区分度。必须按本次结果的最高分动态归一。
        """
        if not hits:
            return hits

        max_fusion = max(float(d.get("fusion", 0.0)) for d in hits) or 1.0
        q_tokens = tokenize(query)
        q_set = set(q_tokens)

        for doc in hits:
            fusion_norm = float(doc.get("fusion", 0.0)) / max_fusion
            relevance = float(doc.get("score", 0.0))
            cover = _coverage(q_tokens, tokenize(str(doc.get("content", ""))))
            title_hit = 1.0 if (q_set & set(tokenize(str(doc.get("title", ""))))) else 0.0

            doc["coverage"] = round(cover, 3)
            doc["rerankScore"] = round(
                fusion_norm * 0.5 + relevance * 0.4 + cover * 0.1 + title_hit * 0.05, 4
            )

        hits.sort(key=lambda d: float(d.get("rerankScore", 0.0)), reverse=True)
        return hits


_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    """进程级单例：BM25 索引只建一次。

    向量检索用懒加载的 lambda 包一层，避免「import 时就连接 ChromaDB」，
    也让没装 chromadb 的环境能正常 import 本模块。
    """
    global _retriever
    if _retriever is None:
        from app.config import get_settings

        settings = get_settings()

        def _vector(query: str, top_k: int) -> List[RetrievedDoc]:
            from app.rag.store import get_store

            # min_score=0.0：候选不做阈值过滤，由融合层统一判相关
            return get_store().search(query, top_k=top_k, min_score=0.0)

        _retriever = HybridRetriever(
            vector_search=_vector,
            rrf_k=settings.rrf_k,
            pool=settings.retrieval_pool,
            bm25_weight=settings.bm25_weight,
            rerank=settings.rerank_enabled,
        )
        logger.info(
            "混合检索器就绪：rrf_k=%d, pool=%d, bm25_weight=%.2f, rerank=%s",
            settings.rrf_k, settings.retrieval_pool, settings.bm25_weight, settings.rerank_enabled,
        )
    return _retriever


def reset_retriever() -> None:
    """清掉单例（语料变了或测试隔离时用）。"""
    global _retriever
    _retriever = None
