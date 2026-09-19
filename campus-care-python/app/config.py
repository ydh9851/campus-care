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

    # ---------- 会话 ----------
    history_limit: int = 10

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
