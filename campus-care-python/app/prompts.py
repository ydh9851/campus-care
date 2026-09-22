"""Prompt 外置与版本管理。

为什么要把 prompt 从代码里搬出来：
    1. prompt 是「会频繁调整的业务文案」，不是逻辑。以前改一句话要动代码 + 重新发版，
       现在改 txt 重启即可，也方便非开发同学评审措辞。
    2. 每次回复都要能回答「这次用的是哪一版 prompt」。prompt_version() 取内容哈希前 8 位，
       内容一改版本号必变；把它写进日志和接口响应，线上出问题能直接定位到那一版文案。

文件都在 campus-care-python/prompts/ 下：
    *.txt  纯文本 prompt，支持 {占位符}（用 fill() 填充）
    *.json 结构化 prompt（如按意图分风格的 reply_style.json）
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict

logger = logging.getLogger(__name__)

# app/prompts.py -> app -> campus-care-python -> prompts
_PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts"
)

# 参与版本统计的 prompt 清单（新增 prompt 时记得登记，方便日志里一次性打印全量版本）
KNOWN_PROMPTS = ("intent", "reply_base", "reply_style", "report", "risk_suggestion")


def _path(name: str, suffix: str) -> str:
    return os.path.join(_PROMPT_DIR, f"{name}{suffix}")


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """读取 txt prompt 原文（带缓存，避免每次请求都读磁盘）。"""
    path = _path(name, ".txt")
    if not os.path.exists(path):
        # prompt 缺失属于部署问题，直接抛错比静默返回空串更容易发现
        raise FileNotFoundError(f"prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


@lru_cache(maxsize=16)
def load_json_prompt(name: str) -> Dict[str, Any]:
    """读取 json prompt（如 reply_style.json）。"""
    path = _path(name, ".json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=64)
def prompt_version(name: str) -> str:
    """prompt 内容哈希（前 8 位）作为版本号，内容不变则版本稳定。"""
    try:
        path = _path(name, ".json") if os.path.exists(_path(name, ".json")) else _path(name, ".txt")
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except OSError:
        return "missing"


def prompt_versions() -> Dict[str, str]:
    """当前所有 prompt 的版本快照，供 /health 与启动日志打印。"""
    return {name: prompt_version(name) for name in KNOWN_PROMPTS}


def fill(template: str, **kwargs: Any) -> str:
    """填充 {占位符}。

    用 format 而不是 replace，是为了让缺失占位符直接报错而不是留下一个 {dialog} 在 prompt 里
    —— 后者会悄悄降低回答质量，很难发现。
    """
    return template.format(**kwargs)
