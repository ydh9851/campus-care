"""冒烟测试：不启动 HTTP 服务，直接跑 LangGraph，验证四个节点都能出结果。

用法：
    cd campus-care-python
    .venv\\Scripts\\python.exe scripts\\smoke_test.py

不需要配置 DEEPSEEK_API_KEY —— 没配会走 mock 模式，照样能验证链路。
"""
from __future__ import annotations

import os
import sys

# 让脚本能 import 到 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph.builder import get_graph, mermaid  # noqa: E402
from app.rag.store import get_store  # noqa: E402

CASES = [
    ("知识查询", "我一到考试周就焦虑得睡不着，有什么办法吗？"),
    ("心理倾诉", "最近真的很累，感觉做什么都没意思，也不想跟人说话"),
    ("高危预警", "我觉得活着没意义，想结束生命"),
    ("闲聊", "你好呀"),
]


def main() -> int:
    print("=" * 70)
    print("CampusCare LangGraph 冒烟测试")
    print("=" * 70)

    print("\n[1/2] 构建向量库 ...")
    count = get_store().build()
    print(f"      FAQ 文档数: {count}")
    if count == 0:
        print("      !! 向量库为空，请确认 data/psych_faq.json 存在")

    print("\n[2/2] 逐条跑多 Agent 链路 ...\n")
    graph = get_graph()
    failed = 0

    for name, message in CASES:
        print("-" * 70)
        print(f"用例：{name}")
        print(f"输入：{message}")
        try:
            state = graph.invoke({
                "user_id": 1,
                "conversation_id": 1,
                "message": message,
                "history": [],
            })
        except Exception as e:
            print(f"  !! 执行异常: {type(e).__name__}: {e}")
            failed += 1
            continue

        print(f"  意图      : {state.get('intent')}")
        print(f"  风险等级  : {state.get('risk_level')}")
        print(f"  命中关键词: {state.get('keywords')}")
        print(f"  RAG 来源  : {state.get('rag_sources')}")
        print(f"  tokens    : {state.get('tokens')}")
        print(f"  回复      : {(state.get('reply') or '')[:120]}...")

        if not state.get("reply"):
            print("  !! 回复为空")
            failed += 1

    print("-" * 70)
    print("\nLangGraph Mermaid 流程图（可贴到 README）:\n")
    print(mermaid())
    print("\n" + "=" * 70)
    print("冒烟测试结束" + ("" if failed == 0 else f"，{failed} 个用例异常"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
