"""FastAPI 出入参模型（两个服务之间的内部协议）。"""
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------- 请求 ----------------

class HistoryMessage(BaseModel):
    role: str = Field(description="user / assistant")
    content: str


class AgentChatRequest(BaseModel):
    userId: Optional[int] = Field(default=None, description="学生 id")
    conversationId: Optional[int] = Field(default=None, description="会话 id")
    message: str = Field(description="学生本次说的话")
    history: List[HistoryMessage] = Field(default_factory=list, description="最近的历史消息")


# ---------------- 响应 ----------------

class AgentChatData(BaseModel):
    reply: str = Field(description="AI 回复正文")
    intent: str = Field(description="意图：PSYCH_EMOTION/KNOWLEDGE_QUERY/RISK_ALERT/CHITCHAT")
    riskLevel: str = Field(description="风险等级：LOW/MEDIUM/HIGH")
    keywords: List[str] = Field(default_factory=list, description="命中的风险关键词")
    aiSuggestion: Optional[str] = Field(default=None, description="风险处置建议")
    ragSources: List[str] = Field(default_factory=list, description="RAG 命中的 FAQ 来源")
    tokens: int = Field(default=0, description="消耗 token")


class ReportData(BaseModel):
    summary: str = Field(description="会话摘要")
    emotionScore: int = Field(default=60, description="情绪评分 0-100，越高越积极")
    riskLevel: str = Field(default="LOW", description="综合风险等级")
    suggestion: str = Field(default="", description="干预建议")


class Envelope(BaseModel):
    """统一信封：{code, message, data}，与 Java 侧完全一致"""
    code: int = 200
    message: str = "success"
    data: Optional[object] = None

    @classmethod
    def ok(cls, data):
        return cls(code=200, message="success", data=data)

    @classmethod
    def fail(cls, message: str, code: int = 500):
        return cls(code=code, message=message, data=None)
