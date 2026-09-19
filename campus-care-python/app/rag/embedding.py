"""文本向量化（Embedding）。

两种实现：
  bge         —— BAAI/bge-small-zh-v1.5，真正的中文语义向量，需要 sentence-transformers
  local_hash  —— 字符 n-gram 哈希，零依赖离线可跑，但只是字面匹配，作为降级方案

配置文件里的 EMBEDDING_PROVIDER 决定用哪个，默认 bge，加载失败会自动回退。
"""
from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import List

from app.config import get_settings

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    """向量化器接口。

    min_relevant_score 定义在实现类上而不是全局配置里，因为「多少分算相关」
    是向量空间自身的属性：哈希向量的分数普遍在 0.2~0.4，语义向量普遍在 0.5~0.8，
    用同一个阈值会有一边必然失效。
    """

    name: str = "base"
    dim: int = 0
    min_relevant_score: float = 0.15

    @abstractmethod
    def encode(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        ...

    def encode_one(self, text: str, is_query: bool = False) -> List[float]:
        return self.encode([text], is_query=is_query)[0]


class LocalHashEmbedder(BaseEmbedder):
    """字符 n-gram 哈希向量（n=1,2），L2 归一化。

    这是降级方案，不是语义模型：它只能匹配「字面重合」，
    学生说「翻来覆去睡不着」时检索不到标题为「失眠了怎么办」的条目。
    保留它的唯一理由是零依赖、离线可跑，以及 sentence-transformers 加载失败时兜底。
    """

    name = "local_hash"
    min_relevant_score = 0.15

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def _features(self, text: str) -> List[str]:
        text = (text or "").strip().lower()
        chars = [c for c in text if not c.isspace()]
        feats = list(chars)
        feats += [a + b for a, b in zip(chars, chars[1:])]
        return feats

    def encode(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for feature in self._features(text):
                digest = hashlib.md5(feature.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


class BgeEmbedder(BaseEmbedder):
    """BGE 中文语义向量模型。

    BGE 训练时对「查询」加了指令前缀、对「文档」不加，所以检索侧必须区分两者。
    不加指令会明显掉点（官方也建议检索时使用指令）。
    """

    name = "bge"
    # v1.5 的官方建议：短查询加指令，长文本 / 文档不加
    QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
    # 语义向量的分数分布比哈希向量高，0.35 以下基本是无关内容
    min_relevant_score = 0.35

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        logger.info("正在加载 BGE 向量模型: %s（首次运行需要下载，约 95MB）", model_name)
        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()
        logger.info("BGE 向量模型就绪: %s (dim=%d)", model_name, self.dim)

    def encode(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        if is_query:
            texts = [self.QUERY_INSTRUCTION + t for t in texts]
        # normalize_embeddings=True 让余弦相似度退化成点积，计算更快也更稳定
        arr = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in arr]


_embedder: BaseEmbedder | None = None


def get_embedder() -> BaseEmbedder:
    global _embedder
    if _embedder is not None:
        return _embedder

    settings = get_settings()
    provider = (settings.embedding_provider or "bge").lower()

    if provider == "bge":
        try:
            _embedder = BgeEmbedder(settings.bge_model)
            return _embedder
        except Exception as e:
            logger.error(
                "BGE 加载失败（%s），已回退到 local_hash。"
                "检索将退化为字面匹配，召回质量明显下降 —— 请检查 "
                "sentence-transformers 是否安装。", e)

    _embedder = LocalHashEmbedder()
    logger.warning("使用 local_hash 向量化（dim=%d）：这是字面匹配降级方案，不是语义检索",
                   _embedder.dim)
    return _embedder
