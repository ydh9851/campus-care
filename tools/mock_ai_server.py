#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CampusCare Mock AI 服务（开发用桩服务）

用途：
    在真正的 campus-care-python（FastAPI + LangGraph + DeepSeek）还没写好的时候，
    用它来跑通 Java 主服务的整条链路，包括：
      - /api/chat/consult  → 意图、回复、风险等级落库
      - risk_alert 表自动插入预警
      - /api/report/{id}   → 生成咨询报告

    好处：
      1. Java 侧和 Python 侧可以并行开发，谁先做完谁能先自测；
      2. 不消耗 DeepSeek token，不用等 10~60 秒，本地毫秒级返回；
      3. 风险等级可以人为控制，方便测试高危预警链路。

启动：
    python tools/mock_ai_server.py
    （零依赖，只用 Python 标准库，Python 3.8+ 均可）

对接真实 Python 服务时：
    直接停掉这个进程，启动 campus-care-python 即可，
    因为两者监听的端口和接口协议完全一致。
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8000

# ---- 用关键词模拟「风险预警 Agent」的判定逻辑 ----
HIGH_WORDS = ["自杀", "自残", "不想活", "活着没意思", "死了算了"]
MEDIUM_WORDS = ["失眠", "焦虑", "压力", "抑郁", "崩溃", "难受", "睡不着"]


def envelope(data):
    """统一信封 {code, message, data}，与 Python 真实服务的约定一致。"""
    return {"code": 200, "message": "success", "data": data}


class MockAiHandler(BaseHTTPRequestHandler):

    # 用 HTTP/1.1，行为与真实的 FastAPI / uvicorn 更接近
    protocol_version = "HTTP/1.1"

    # ---------- 工具方法 ----------
    def _send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        """
        读取请求体，必须同时支持两种传输方式：

          1. Content-Length               —— 普通提交
          2. Transfer-Encoding: chunked   —— Spring 的 RestTemplate 可能用这种

        只处理 Content-Length 会踩一个很隐晦的坑：
        请求体读不到（读成 0 字节），未读数据还留在 socket 缓冲区里，
        我们一关连接，操作系统就会发 RST，Java 侧报的错是
        "你的主机中的软件中止了一个已建立的连接"，完全看不出是 mock 的问题。
        """
        raw = b""

        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            while True:
                size_line = self.rfile.readline().strip()
                if not size_line:          # 空行，跳过
                    continue
                size = int(size_line.split(b";")[0], 16)
                if size == 0:              # 长度为 0 的 chunk 表示结束
                    self.rfile.readline()
                    break
                raw += self.rfile.read(size)
                self.rfile.readline()      # 吃掉 chunk 末尾的 CRLF
        else:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                raw = self.rfile.read(length)

        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---------- 路由 ----------
    def do_GET(self):
        # Java 侧的 PythonAgentClient.ping() 只需要拿到非空响应
        if self.path.startswith("/api/health"):
            self._send_json({"status": "UP", "service": "mock-ai-server"})
        else:
            self._send_json({"code": 404, "message": "not found"})

    def do_POST(self):
        body = self._read_body()
        message = body.get("message") or ""

        # 把传输方式打出来，方便排查「请求体读不到」这类问题
        print("[mock-ai] POST %s  Transfer-Encoding=%s  Content-Length=%s  message=%r"
              % (self.path,
                 self.headers.get("Transfer-Encoding"),
                 self.headers.get("Content-Length"),
                 message[:24]), flush=True)

        if self.path.startswith("/api/agent/chat"):
            # traceId 由 Java 生成后透传，这里原样回显，行为与真实 Python 服务一致
            self._send_json(envelope(self._chat(message, body.get("traceId"))))
        elif self.path.startswith("/api/agent/report"):
            self._send_json(envelope(self._report()))
        else:
            self._send_json({"code": 404, "message": "not found"})

    # ---------- 模拟两个 Agent 的输出 ----------
    # 字段必须与真实 Python 服务（app/schemas.py: AgentChatData）保持一致，
    # 否则「用 mock 联调通过、换真服务挂掉」这种最难查的问题就会出现。
    def _common(self, trace_id):
        return {
            "traceId": trace_id or "",
            "retrievalMode": "hybrid",
            "promptVersion": {"intent": "mock0001", "reply_base": "mock0002", "risk_suggestion": "mock0003"},
            "disclaimer": "本回复由 AI 生成，仅供情绪支持与心理健康科普，"
                          "不构成医学诊断或治疗建议；如有需要请咨询专业心理工作者。",
        }

    def _chat(self, message, trace_id=None):
        high_hits = [w for w in HIGH_WORDS if w in message]
        medium_hits = [w for w in MEDIUM_WORDS if w in message]

        if high_hits:
            return {
                "reply": "我听到你说的话了，能把这些说出来很不容易。你现在的感受很重要，"
                         "请立刻联系学校心理健康中心的老师，或者拨打全国心理援助热线 12356。"
                         "你不是一个人，我们会陪着你。",
                "intent": "RISK_ALERT",
                "riskLevel": "HIGH",
                "keywords": high_hits,
                "aiSuggestion": "建议 24 小时内联系该学生本人，启动高危干预流程并通知院系辅导员。",
                "ragSources": ["FAQ-011 危机干预与求助渠道（相关度 0.82）"],
                "tokens": 128,
                "needHandoff": True,
                **self._common(trace_id),
            }

        if medium_hits:
            return {
                "reply": "谢谢你愿意说出来。你提到的这些感受在同学里其实很常见，"
                         "我们可以先从作息和情绪记录开始，慢慢找到适合你的调节方式。",
                "intent": "PSYCH_EMOTION",
                "riskLevel": "MEDIUM",
                "keywords": medium_hits,
                "aiSuggestion": "建议辅导员在 3 天内关注该学生的状态变化。",
                "ragSources": ["FAQ-003 睡眠与情绪的关系（相关度 0.71）", "FAQ-007 压力管理（相关度 0.66）"],
                "tokens": 156,
                "needHandoff": False,
                **self._common(trace_id),
            }

        return {
            "reply": "你好，我是校园心理助手。你可以和我聊聊最近的状态，"
                     "也可以问一些心理健康相关的问题，比如怎么缓解考试焦虑。",
            "intent": "CHITCHAT",
            "riskLevel": "LOW",
            "keywords": [],
            "aiSuggestion": None,
            "ragSources": [],
            "tokens": 62,
            "needHandoff": False,
            **self._common(trace_id),
        }

    def _report(self):
        return {
            "summary": "本次会话中，学生主要表达了学业压力与睡眠困扰，情绪起伏较为明显。",
            "emotionScore": 55,
            "riskLevel": "MEDIUM",
            "suggestion": "建议持续关注睡眠情况，可安排一次线下谈心；若情绪持续低落，转介学校心理咨询中心。",
        }

    # 让日志带上前缀，方便在多进程环境下区分
    def log_message(self, fmt, *args):
        print("[mock-ai] " + fmt % args, flush=True)


if __name__ == "__main__":
    print("========================================================")
    print("  CampusCare Mock AI 服务已启动")
    print("  地址: http://localhost:%d" % PORT)
    print("  接口: POST /api/agent/chat  |  POST /api/agent/report  |  GET /api/health")
    print("  停止: Ctrl + C")
    print("========================================================")
    ThreadingHTTPServer(("0.0.0.0", PORT), MockAiHandler).serve_forever()
