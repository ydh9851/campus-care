"""ChromaDB 向量库封装：FAQ 语料的建库与检索。

建库幂等，靠「语料 + 向量模型」的指纹判断是否需要重建；检索返回 Top-K 文档与相似度分数。
"""
from __future__ import annotations

import hashlib
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

    def _client(self):
        if chromadb is None:
            raise RuntimeError("未安装 chromadb，请先 pip install -r requirements.txt")
        return chromadb.PersistentClient(
            path=self.settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )

    def _fingerprint(self, faqs: List[dict]) -> str:
        """向量模型 + 语料内容的指纹。

        只比条数是不够的：换模型（维度变化）或改内容但条数不变时都会漏更新，
        结果就是拿新模型的向量去查旧向量库，检索结果全是噪声且不报错。
        """
        digest = hashlib.sha256()
        digest.update(self.embedder.name.encode("utf-8"))
        digest.update(str(self.embedder.dim).encode("utf-8"))
        for item in faqs:
            digest.update(str(item.get("id", "")).encode("utf-8"))
            digest.update(build_document_text(item).encode("utf-8"))
        return digest.hexdigest()[:16]

    def build(self, force: bool = False) -> int:
        """建库（幂等）。返回 collection 中的文档数。"""
        client = self._client()
        name = self.settings.chroma_collection

        faqs = load_faq()
        if not faqs:
            logger.error("FAQ 语料为空，向量库无法建立")
            self._ready = False
            return 0

        fingerprint = self._fingerprint(faqs)

        # 取已有集合；取不到或指纹不一致都要重建
        existing = None
        try:
            existing = client.get_collection(name)
        except Exception:
            existing = None

        stale = existing is None or (existing.metadata or {}).get("fingerprint") != fingerprint
        if existing is not None and not stale and not force:
            self._collection = existing
            self._ready = True
            logger.info("向量库已就绪，跳过重建（%d 条，%s）", existing.count(), self.embedder.name)
            return existing.count()

        if existing is not None:
            logger.info("向量库需要重建（指纹变化或强制），正在删除旧集合")
            client.delete_collection(name)

        self._collection = client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "fingerprint": fingerprint},
        )

        ids = [str(item.get("id")) for item in faqs]
        documents = [item.get("content", "") for item in faqs]
        metadatas = [
            {
                "title": item.get("title", ""),
                "category": item.get("category", "通用"),
                "source": item.get("source", ""),
            }
            for item in faqs
        ]
        embeddings = self.embedder.encode([build_document_text(item) for item in faqs])

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info("向量库构建完成：%d 条 FAQ，向量模型 %s(dim=%d)",
                    self._collection.count(), self.embedder.name, self.embedder.dim)
        self._ready = True
        return self._collection.count()

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
                # 查询侧标记 is_query：BGE 需要加指令前缀，文档侧不加
                query_embeddings=self.embedder.encode([query], is_query=True),
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("检索失败: %s", e)
            return []

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        # 阈值跟向量模型走：哈希向量 0.15，语义向量 0.35
        min_score = self.settings.retrieval_min_score
        if min_score is None:
            min_score = self.embedder.min_relevant_score

        hits: List[RetrievedDoc] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            score = round(1.0 - float(dist), 4)
            if score < min_score:
                continue
            meta = meta or {}
            hits.append({
                "title": meta.get("title", ""),
                "category": meta.get("category", "通用"),
                "content": doc or "",
                "score": score,
                "source": meta.get("source", ""),
            })
        logger.info("RAG 检索 '%s' -> 命中 %d 条（阈值 %.2f）", query[:20], len(hits), min_score)
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
