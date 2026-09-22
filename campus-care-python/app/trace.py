"""链路追踪：trace id 贯穿 Java → Python → 日志。

为什么需要它：
    一次咨询会经过「浏览器 → Java → Python（4 个 Agent 节点）→ DeepSeek」，
    线上排查时 Java 日志和 Python 日志是两份文件，没有共同标识就只能靠时间戳猜。
    约定 Java 在请求头 X-Trace-Id 里带一个 id，Python 侧读出来放进 contextvar，
    之后这一条请求链路上所有日志自动带上它，两端用同一个 id 就能串起来。

用 contextvar 而不是全局变量：FastAPI 在线程池里并发处理请求，
全局变量会被并发请求互相覆盖，contextvar 天然按协程/上下文隔离。
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Optional

TRACE_HEADER = "X-Trace-Id"

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


def new_trace_id() -> str:
    """生成一个短 trace id（16 位十六进制，够用且不占日志宽度）。"""
    return uuid.uuid4().hex[:16]


def set_trace_id(trace_id: Optional[str]) -> str:
    """写入当前上下文的 trace id；为空则新生成一个。"""
    value = (trace_id or "").strip() or new_trace_id()
    _trace_id.set(value)
    return value


def get_trace_id() -> str:
    return _trace_id.get()


class TraceIdFilter(logging.Filter):
    """给每条日志记录挂上 trace_id 字段，供 Formatter 用 %(trace_id)s 引用。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = get_trace_id()
        return True


def install_logging(trace_prefix: str = "%(trace_id)s") -> None:
    """统一配置日志格式：时间 | 级别 | trace_id | 模块 | 消息。"""
    handler = logging.StreamHandler()
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | " + trace_prefix + " | %(name)s | %(message)s"
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
