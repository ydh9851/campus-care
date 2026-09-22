"""DeepSeek LLM 客户端封装。

走 OpenAI 兼容协议，换模型不用改业务代码；未配置 API Key 时自动降级为 mock，
保证整条链路在任意环境下都能跑通；同时统一收集 token 用量。

可靠性设计（三层，从里到外）：
    1. 单次调用超时   timeout        —— 一次请求最多等多久
    2. 失败重试       max_retries    —— 网络抖动 / 5xx / 429 值得再试
    3. 总时间预算     total_timeout  —— 重试叠加起来也不能把请求线程占死
    外层还有一个「多模型回退」：主模型彻底不可用时换备用模型，
    而不是直接把「抱歉我连接不上」甩给正处于情绪低谷的学生。
"""
from __future__ import annotations

import logging
import time
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
        self.models: List[str] = self._resolve_models()
        if self.settings.llm_ready:
            if OpenAI is None:
                logger.error("未安装 openai 包，降级为 mock 模式")
            else:
                self._client = OpenAI(
                    api_key=self.settings.deepseek_api_key,
                    base_url=self.settings.deepseek_base_url,
                    timeout=self.settings.llm_timeout,
                )
                logger.info("LLM 已就绪: %s @ %s（回退链: %s）",
                            self.models[0], self.settings.deepseek_base_url,
                            " -> ".join(self.models))
        if self._client is None:
            logger.warning("DEEPSEEK_API_KEY 未配置 —— 当前为 mock 模式，返回内置话术")

    def _resolve_models(self) -> List[str]:
        """主模型 + 备用模型（DEEPSEEK_FALLBACK_MODELS 逗号分隔），去重保序。"""
        models = [self.settings.deepseek_model]
        for item in (self.settings.deepseek_fallback_models or "").split(","):
            name = item.strip()
            if name and name not in models:
                models.append(name)
        return models

    @property
    def is_mock(self) -> bool:
        return self._client is None

    @property
    def max_retries(self) -> int:
        return max(0, int(self.settings.llm_max_retries))

    def _backoff_seconds(self, attempt: int) -> float:
        """第 attempt 次重试前的等待：base * 2^(attempt-1)，指数退避。"""
        return max(0.0, float(self.settings.llm_retry_backoff)) * (2 ** max(0, attempt - 1))

    def chat(self, messages: List[dict], temperature: Optional[float] = None,
             mock_text: str = "") -> tuple[str, int]:
        """
        :param messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        :param mock_text: mock 模式或彻底失败时返回的文本
        :return: (回复文本, 消耗 token)
        """
        if self._client is None:
            return mock_text or "（mock 模式）我需要你先配置 DEEPSEEK_API_KEY 才能给出真实回复。", 0

        started = time.perf_counter()
        budget = float(self.settings.llm_total_timeout)
        last_error: Optional[Exception] = None

        # 外层：重试轮次；内层：模型回退链
        for attempt in range(self.max_retries + 1):
            if time.perf_counter() - started >= budget:
                logger.warning("已超出 LLM 总时间预算 %.0fs，停止重试", budget)
                break

            for model in self.models:
                try:
                    resp = self._client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=self.settings.llm_temperature if temperature is None else temperature,
                        stream=False,
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    tokens = resp.usage.total_tokens if resp.usage else 0
                    if attempt > 0 or model != self.models[0]:
                        logger.info("LLM 调用成功（第 %d 次尝试，模型 %s）", attempt + 1, model)
                    return text, tokens
                except Exception as e:  # 网络/额度/限流都兜住，不让 AI 异常打挂业务接口
                    last_error = e
                    logger.warning("模型 %s 第 %d 次调用失败: %s: %s",
                                   model, attempt + 1, type(e).__name__, e)

            if attempt < self.max_retries:
                wait = self._backoff_seconds(attempt + 1)
                if time.perf_counter() - started + wait >= budget:
                    logger.warning("退避等待会超出总预算，停止重试")
                    break
                time.sleep(wait)

        logger.error("LLM 调用最终失败（已耗时 %.1fs）: %s",
                     time.perf_counter() - started, last_error)
        return mock_text or f"抱歉，我这边暂时连接不上，请稍后再试。（{type(last_error).__name__}）", 0

    def chat_stream(self, messages: List[dict], temperature: Optional[float] = None,
                    mock_text: str = ""):
        """
        流式版本：逐块产出 {"type": "delta", "text": ...}，最后产出 {"type": "usage", "tokens": n}。

        单独一个方法而不给 chat() 加 stream 参数，是因为错误处理不同：
        一次性调用失败可以整段换兜底话术；流式一旦开始吐字就收不回来，
        所以把错误作为独立事件抛给上层，由 Java 决定这条回复不落库。

        重试边界：只有「建立连接」阶段可以重试；一旦开始输出 delta 就不再重试，
        否则用户会看到前半段和后半段拼在一起，内容重复甚至矛盾。
        """
        if self._client is None:
            # mock 模式：把整段话切成小块吐出去。
            # 这样即使机器上没有 API Key，「Java -> Python -> 前端」这条流式链路也能被验证。
            text = mock_text or "（mock 模式）未配置 DEEPSEEK_API_KEY，无法给出真实回复。"
            for piece in _chunk_text(text):
                yield {"type": "delta", "text": piece}
            yield {"type": "usage", "tokens": 0}
            return

        stream = None
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            for model in self.models:
                try:
                    stream = self._client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=self.settings.llm_temperature if temperature is None else temperature,
                        stream=True,
                        # 让服务端在最后一个 chunk 里带上 token 用量（OpenAI 兼容协议的可选参数）
                        stream_options={"include_usage": True},
                    )
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("流式建连失败（模型 %s，第 %d 次）: %s: %s",
                                   model, attempt + 1, type(e).__name__, e)
            if stream is not None:
                break
            if attempt < self.max_retries:
                time.sleep(self._backoff_seconds(attempt + 1))

        if stream is None:
            yield {"type": "error", "message": f"{type(last_error).__name__}: {last_error}"}
            return

        try:
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
            # 已经吐出去的内容收不回来，只能报错终止
            logger.error("流式输出中断: %s", e)
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


def reset_llm() -> None:
    """清掉单例（测试隔离用）。"""
    global _llm_client
    _llm_client = None
