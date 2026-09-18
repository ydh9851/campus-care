"""FAQ 语料加载：把 data/psych_faq.json 读成结构化列表。"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

from app.config import get_settings

logger = logging.getLogger(__name__)


def load_faq() -> List[Dict[str, str]]:
    """读取心理 FAQ 语料。

    :return: [{"id": "faq-001", "title": ..., "category": ..., "content": ...}]
    """
    settings = get_settings()
    path = settings.faq_data_path
    if not os.path.isabs(path):
        # 相对路径统一以 campus-care-python 为基准，避免受启动目录影响
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), path.lstrip("./"))

    if not os.path.exists(path):
        logger.error("FAQ 语料不存在: %s", path)
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    faqs = raw.get("faqs", raw) if isinstance(raw, dict) else raw
    logger.info("加载 FAQ 语料 %d 条 <- %s", len(faqs), path)
    return faqs


def build_document_text(item: Dict[str, str]) -> str:
    """把一条 FAQ 拼成用于向量化的文本（标题 + 正文，标题权重靠重复一次来加强）。"""
    title = item.get("title", "")
    return f"{title}。{title}。{item.get('content', '')}"
