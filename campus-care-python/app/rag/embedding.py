"""文本向量化（Embedding）。

为什么自己写一个哈希向量？
  DeepSeek 只提供对话模型，没有 embedding 接口；而 bge / m3e 这类中文向量模型
  要额外装 PyTorch（几百 MB）。为了「克隆下来就能跑」，默认用零依赖的
  本地哈希向量，同时保留 bge 开关：

      EMBEDDING_PROVIDER=local_hash   # 默认，离线可跑
      EMBEDDING_PROVIDER=bge          # pip install sentence-transformers 后启用，中文语义更好
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
    """向量化器接口"""

    dim: int = 0

    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        ...

    def encode_one(self, text: str) -> List[float]:
        return self.encode([text])[0]


class LocalHashEmbedder(BaseEmbedder):
    """字符 n-gram 哈希向量（n=1,2），L2 归一化。

    原理：把中文字符和相邻字符二元组分别哈希到固定维度上累加，
    再做 L2 归一化。这样「失眠」和「睡不着」虽然语义不同，
    但共享字面特征的部分仍能被召回到——对 FAQ 这种
    「表述接近问题原文」的场景足够用，且完全离线、确定性可复现。
    """

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def _features(self, text: str) -> List[str]:
        text = (text or "").strip().lower()
        chars = [c for c in text if not c.isspace()]
        feats = list(chars)                                   # 一元
        feats += [a + b for a, b in zip(chars, chars[1:])]     # 二元
        return feats

    def encode(self, texts: List[str]) -> List[List[float]]:
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
    """BGE 中文向量模型（可选，需要 sentence-transformers）"""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # 延迟导入
        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()
        logger.info("BGE 向量模型加载完成: %s (dim=%d)", model_name, self.dim)

    def encode(self, texts: List[str]) -> List[List[float]]:
        # normalize_embeddings=True 让余弦相似度计算更稳定
        arr = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, row)) for row in arr]


_embedder: BaseEmbedder | None = None


def get_embedder() -> BaseEmbedder:
    global _embedder
    if _embedder is not None:
        return _embedder

    settings = get_settings()
    provider = (settings.embedding_provider or "local_hash").lower()
    if provider == "bge":
        try:
            _embedder = BgeEmbedder(settings.bge_model)
            return _embedder
        except Exception as e:
            logger.warning("BGE 加载失败（%s），回退到 local_hash", e)

    _embedder = LocalHashEmbedder()
    logger.info("使用 local_hash 向量化（dim=%d）", _embedder.dim)
    return _embedder
