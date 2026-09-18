"""ChromaDB 向量库封装：FAQ 语料的建库与检索。
建库幂等，重复启动不会重复插入；检索返回 Top-K 文档与相似度分数。
"""
from __future__ import annotations

import logging
from typing import List

from app.agents.state import RetrievedDoc
from app.config import get_settings
from app.rag.embedding import get_embedder
from app.rag.loader import build_document_text, load_faq

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:  # pragma: no cover
    chromadb = None


class FaqVectorStore:
    """FAQ 向量库：ChromaDB PersistentClient + 余弦距离"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.embedder = get_embedder()
        self._collection = None
        self._ready = False

    # ---------------- 初始化 ----------------

    def _client(self):
        if chromadb is None:
            raise RuntimeError("未安装 chromadb，请先 pip install -r requirements.txt")
        return chromadb.PersistentClient(
            path=self.settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )

    def build(self, force: bool = False) -> int:
        """建库（幂等）。返回 collection 中的文档数。"""
        client = self._client()
        self._collection = client.get_or_create_collection(
            name=self.settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

        existing = self._collection.count()
        faqs = load_faq()
        if existing >= len(faqs) and not force and existing > 0:
            logger.info("向量库已就绪，跳过重建（%d 条）", existing)
            self._ready = True
            return existing

        if not faqs:
            logger.error("FAQ 语料为空，向量库无法建立")
            self._ready = False
            return 0

        ids = [str(item.get("id")) for item in faqs]
        documents = [item.get("content", "") for item in faqs]
        metadatas = [
            {"title": item.get("title", ""), "category": item.get("category", "通用")}
            for item in faqs
        ]
        embeddings = self.embedder.encode([build_document_text(item) for item in faqs])

        # upsert 而非 add：重复启动不会因为主键冲突报错
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info("向量库构建完成，共 %d 条 FAQ", self._collection.count())
        self._ready = True
        return self._collection.count()

    # ---------------- 检索 ----------------

    def search(self, query: str, top_k: int | None = None) -> List[RetrievedDoc]:
        """语义检索，返回 Top-K 结果（按相似度倒序）。"""
        if not self._ready:
            try:
                self.build()
            except Exception as e:
                logger.error("向量库不可用: %s", e)
                return []

        k = top_k or self.settings.top_k
        try:
            result = self._collection.query(
                query_embeddings=self.embedder.encode([query]),
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("检索失败: %s", e)
            return []

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        hits: List[RetrievedDoc] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # cosine 距离 -> 相似度
            score = round(1.0 - float(dist), 4)
            if score < 0.15:      # 相似度过低的不给 LLM，避免污染回答
                continue
            hits.append({
                "title": (meta or {}).get("title", ""),
                "category": (meta or {}).get("category", "通用"),
                "content": doc or "",
                "score": score,
            })
        logger.info("RAG 检索 '%s' -> 命中 %d 条", query[:20], len(hits))
        return hits

    @property
    def ready(self) -> bool:
        return self._ready

    def count(self) -> int:
        try:
            if self._collection is None:
                return 0
            return self._collection.count()
        except Exception:
            return 0


_store: FaqVectorStore | None = None


def get_store() -> FaqVectorStore:
    """单例向量库，避免每个请求都连一次 ChromaDB。"""
    global _store
    if _store is None:
        _store = FaqVectorStore()
    return _store
