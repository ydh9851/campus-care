"""安全护栏：免责声明与转人工引导。

心理类 AI 应用的底线：
    1. 任何回复都不能被理解成医学诊断或治疗建议，所以每条回复都要有免责声明。
    2. 高风险会话不能只靠模型「好好说话」就结束，必须给出人工入口 ——
       模型可能被诱导、可能漏说，所以这一步用代码强制附加，不交给模型。

这里只做「输出侧的确定性兜底」。输入侧的敏感词拦截由 risk_agent 负责，
两者职责不重叠：一个决定风险等级，一个决定给用户什么出口。
"""
from __future__ import annotations

# 免责声明独立成字段返回，由前端决定展示位置（放正文里会冲淡共情）
DISCLAIMER = (
    "本回复由 AI 生成，仅供情绪支持与心理健康科普，"
    "不构成医学诊断或治疗建议；如有需要请咨询专业心理工作者。"
)

# 高危会话强制附加的人工入口
HANDOFF_HINT = (
    "——\n"
    "如果你希望和真人聊聊，可以：\n"
    "1) 在「我的」页面发起人工咨询，辅导员会看到你的诉求；\n"
    "2) 直接前往学校心理中心（工作日 8:30-17:30，预约免费）；\n"
    "3) 情况紧急时立刻联系辅导员、拨打 120，或使用上面的危机热线。"
)


def needs_handoff(risk_level: str) -> bool:
    """是否需要转人工。目前只对 HIGH 强制，MEDIUM 由辅导员在工单侧跟进。"""
    return (risk_level or "").upper() == "HIGH"


def apply_safety(reply: str, risk_level: str) -> str:
    """给回复做输出侧收尾：高危追加人工入口。

    免责声明不拼进正文（避免回复变长、语气变冷），而是通过接口的 disclaimer 字段返回。
    """
    text = (reply or "").strip()
    if needs_handoff(risk_level):
        text = f"{text}\n\n{HANDOFF_HINT}"
    return text
