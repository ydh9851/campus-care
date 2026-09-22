"""CampusCare Python AI 服务入口。

启动：
    uvicorn main:app --reload --port 8000
文档：
    http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.llm import get_llm
from app.prompts import prompt_versions
from app.rag.store import get_store
from app.trace import TRACE_HEADER, install_logging, set_trace_id

# 统一日志格式（带 trace_id），必须在其它模块打日志之前装好
install_logging()
logger = logging.getLogger("campus-care")


class TraceMiddleware:
    """纯 ASGI 中间件：把 X-Trace-Id 写进 contextvar，并回写到响应头。

    为什么不用 @app.middleware("http")：
        Starlette 的 BaseHTTPMiddleware 会把下游调用放进独立 task，
        在中间件里改的 contextvar 不会传播到 endpoint（日志里永远是默认值 "-"）。
        纯 ASGI 中间件是直接 await 下游，context 一脉相承。
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_headers = dict(scope.get("headers") or [])
        incoming = (raw_headers.get(TRACE_HEADER.lower().encode()) or b"").decode()
        trace_id = set_trace_id(incoming or None)

        async def send_with_trace(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((TRACE_HEADER.lower().encode(), trace_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_trace)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时把向量库建好，避免第一个请求慢得像卡死。"""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("CampusCare Python AI 服务启动中 ...")
    logger.info("LLM 模式: %s", "mock（未配置 API Key）" if get_llm().is_mock else "DeepSeek")
    logger.info("向量化方案: %s | 检索模式: %s",
                settings.embedding_provider, settings.retrieval_mode)
    logger.info("prompt 版本: %s", prompt_versions())
    try:
        count = get_store().build()
        logger.info("向量库就绪，FAQ 文档数: %d", count)
    except Exception as e:
        logger.error("向量库初始化失败（服务仍会启动，混合检索将退化为纯 BM25）: %s", e)
    logger.info("接口文档: http://localhost:%d/docs", settings.server_port)
    logger.info("=" * 60)
    yield
    logger.info("CampusCare Python AI 服务已停止")


app = FastAPI(
    title="CampusCare AI 服务",
    description="校园心理多 Agent 智能咨询平台 —— Python 侧：LangGraph 编排 + 混合检索(RAG) + 风险预警",
    version="1.1.0",
    lifespan=lifespan,
)

# Java 服务与前端都要跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 后加的在最外层：trace 中间件要最先执行，才能覆盖住后面所有日志
app.add_middleware(TraceMiddleware)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=get_settings().server_port,
        reload=False,
    )
