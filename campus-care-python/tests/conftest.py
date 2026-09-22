"""pytest 全局配置。

关键点：这些环境变量必须在 `import app.*` 之前设置好。
Settings 是 lru_cache 单例，第一次 get_settings() 就读定了环境；
晚了就只能测到「真实 .env 配置」，CI 上会因为没有 Key 而行为不一致。
"""
from __future__ import annotations

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 强制 Mock / 降级路径：测试不联网、不消耗额度、不下载模型
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("EMBEDDING_PROVIDER", "local_hash")
os.environ.setdefault("RETRIEVAL_MODE", "hybrid")
os.environ.setdefault("CHROMA_PERSIST_DIR", tempfile.mkdtemp(prefix="campuscare-test-chroma-"))
os.environ.setdefault("TOP_K", "3")
