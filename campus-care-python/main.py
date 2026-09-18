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
from app.rag.store import get_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("campus-care")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时把向量库建好，避免第一个请求慢得像卡死。"""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("CampusCare Python AI 服务启动中 ...")
    logger.info("LLM 模式: %s", "mock（未配置 API Key）" if get_llm().is_mock else "DeepSeek")
    logger.info("向量化方案: %s", settings.embedding_provider)
    try:
        count = get_store().build()
        logger.info("向量库就绪，FAQ 文档数: %d", count)
    except Exception as e:
        logger.error("向量库初始化失败（服务仍会启动，RAG 将不可用）: %s", e)
    logger.info("接口文档: http://localhost:%d/docs", settings.server_port)
    logger.info("=" * 60)
    yield
    logger.info("CampusCare Python AI 服务已停止")


app = FastAPI(
    title="CampusCare AI 服务",
    description="校园心理多 Agent 智能咨询平台 —— Python 侧：LangGraph 编排 + RAG 检索 + 风险预警",
    version="1.0.0",
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

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=get_settings().server_port,
        reload=False,
    )
