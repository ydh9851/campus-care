"""DeepSeek LLM 客户端封装。

走 OpenAI 兼容协议，换模型不用改业务代码；未配置 API Key 时自动降级为 mock，
保证整条链路在任意环境下都能跑通；同时统一收集 token 用量。
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


class LLMClient:
    """轻量 LLM 封装：chat() 返回 (文本, tokens)。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Optional["OpenAI"] = None
        if self.settings.llm_ready:
            if OpenAI is None:
                logger.error("未安装 openai 包，降级为 mock 模式")
            else:
                self._client = OpenAI(
                    api_key=self.settings.deepseek_api_key,
                    base_url=self.settings.deepseek_base_url,
                    timeout=self.settings.llm_timeout,
                )
                logger.info("LLM 已就绪: %s @ %s",
                            self.settings.deepseek_model, self.settings.deepseek_base_url)
        if self._client is None:
            logger.warning("DEEPSEEK_API_KEY 未配置 —— 当前为 mock 模式，返回内置话术")

    @property
    def is_mock(self) -> bool:
        return self._client is None

    def chat(self, messages: List[dict], temperature: Optional[float] = None,
             mock_text: str = "") -> tuple[str, int]:
        """
        :param messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        :param mock_text: mock 模式下返回的文本
        :return: (回复文本, 消耗 token)
        """
        if self._client is None:
            return mock_text or "（mock 模式）我需要你先配置 DEEPSEEK_API_KEY 才能给出真实回复。", 0

        try:
            resp = self._client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=messages,
                temperature=self.settings.llm_temperature if temperature is None else temperature,
                stream=False,
            )
            text = (resp.choices[0].message.content or "").strip()
            tokens = resp.usage.total_tokens if resp.usage else 0
            return text, tokens

        except Exception as e:  # 网络/额度/限流都兜住，不让 AI 异常打挂业务接口
            logger.error("调用 DeepSeek 失败: %s", e)
            return mock_text or f"抱歉，我这边暂时连接不上，请稍后再试。（{type(e).__name__}）", 0

    def chat_stream(self, messages: List[dict], temperature: Optional[float] = None,
                    mock_text: str = ""):
        """
        流式版本：逐块产出 {"type": "delta", "text": ...}，最后产出 {"type": "usage", "tokens": n}。

        单独一个方法而不给 chat() 加 stream 参数，是因为错误处理不同：
        一次性调用失败可以整段换兜底话术，流式一旦开始吐字就没法回头，
        所以把错误作为独立事件抛给上层，由 Java 决定这条回复不落库。
        """
        if self._client is None:
            # mock 模式：把整段话切成小块吐出去。
            # 这样即使机器上没有 API Key，「Java -> Python -> 前端」这条流式链路也能被验证。
            text = mock_text or "（mock 模式）未配置 DEEPSEEK_API_KEY，无法给出真实回复。"
            for piece in _chunk_text(text):
                yield {"type": "delta", "text": piece}
            yield {"type": "usage", "tokens": 0}
            return

        try:
            stream = self._client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=messages,
                temperature=self.settings.llm_temperature if temperature is None else temperature,
                stream=True,
                # 让服务端在最后一个 chunk 里带上 token 用量（OpenAI 兼容协议的可选参数）
                stream_options={"include_usage": True},
            )
            tokens = 0
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage:
                    tokens = usage.total_tokens or tokens
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                piece = choices[0].delta.content
                if piece:
                    yield {"type": "delta", "text": piece}
            yield {"type": "usage", "tokens": tokens}

        except Exception as e:
            logger.error("流式调用 DeepSeek 失败: %s", e)
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}


def _chunk_text(text: str, size: int = 6):
    """把整段文本切成固定长度的小块，仅用于 mock 模式模拟流式输出。"""
    for i in range(0, len(text), size):
        yield text[i:i + size]


_llm_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """单例，避免每次请求都重建客户端。"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
