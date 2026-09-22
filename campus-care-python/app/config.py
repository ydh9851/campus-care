"""CampusCare Python AI 服务：配置加载。

所有配置项集中在 Settings，从 .env 读，代码里不出现任何硬编码密钥。
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- DeepSeek ----------
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_temperature: float = 0.7
    llm_timeout: int = 60

    # ---------- RAG ----------
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "campus_psych_faq"
    faq_data_path: str = "./data/psych_faq.json"
    top_k: int = 3
    # bge = 中文语义向量（推荐）；local_hash = 零依赖字面匹配（降级）
    embedding_provider: str = "bge"
    bge_model: str = "BAAI/bge-small-zh-v1.5"
    # 检索相似度阈值。留空则按向量模型自带的默认值（哈希 0.15 / 语义 0.35）
    retrieval_min_score: Optional[float] = None

    # ---- 混合检索（BM25 + 向量 + RRF）----
    # hybrid = 双路召回后融合（推荐）；vector = 仅向量（旧行为，便于对比）
    retrieval_mode: str = "hybrid"
    # RRF 的 k 值：越大越压平「第 1 名 vs 第 3 名」的差距，60 是原论文经验值
    rrf_k: int = 60
    # 每路召回的候选数（融合前），最终再截断到 top_k
    retrieval_pool: int = 8
    # BM25 分在最终相关度里的权重（只在「仅 BM25 命中」时生效）
    bm25_weight: float = 0.9
    # 轻量重排开关（RRF 融合分 + 查询词覆盖率 + 标题命中）
    rerank_enabled: bool = True

    # ---------- LLM 可靠性 ----------
    # 单次调用失败后的重试次数（不含首次）
    llm_max_retries: int = 2
    # 重试退避基数（秒），第 n 次重试等待 base * 2^(n-1)
    llm_retry_backoff: float = 0.8
    # 整个调用（含所有重试）的总时间预算（秒），防止一次请求把线程占死
    llm_total_timeout: int = 90
    # 主模型失败后的备用模型，逗号分隔（如 deepseek-reasoner）
    deepseek_fallback_models: str = ""

    # ---------- 会话 ----------
    history_limit: int = 10

    # ---------- 安全 ----------
    # 是否在接口响应里返回免责声明（前端决定展示位置）
    disclaimer_enabled: bool = True

    # ---------- 服务 ----------
    server_port: int = 8000
    java_service_url: str = "http://localhost:8080"

    @property
    def llm_ready(self) -> bool:
        """是否配置了可用的 API Key。没配就降级为 mock，保证链路能跑通。"""
        return bool(self.deepseek_api_key and self.deepseek_api_key.strip()
                    and not self.deepseek_api_key.startswith("sk-xxxx"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
