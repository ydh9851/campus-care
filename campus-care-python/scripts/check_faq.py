"""校验知识库语料结构。

为什么需要单独一个脚本：`psych_faq.json` 是纯数据，没有类型系统保护。
少一个 `source` 字段、`id` 写重复、正文没写完就提交 —— 程序照跑不误，
只是 RAG 检索结果悄悄变差、科普页少一条出处，谁都不会立刻发现。
这类静默的数据问题只能靠显式校验拦住。

用法：python campus-care-python/scripts/check_faq.py
退出码非 0 表示校验失败（CI 据此判定）。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

FAQ_PATH = Path(__file__).resolve().parent.parent / "data" / "psych_faq.json"

REQUIRED_FIELDS = ("id", "category", "title", "content", "source")

# 正文短于这个长度基本说明内容没写完，检索出来也帮不到学生
MIN_CONTENT_LEN = 40


def main() -> int:
    if not FAQ_PATH.exists():
        print(f"[FAIL] 找不到语料文件: {FAQ_PATH}")
        return 1

    try:
        data = json.loads(FAQ_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON 解析失败: {e}")
        return 1

    faqs = data.get("faqs") or []
    print(f"语料文件 : {FAQ_PATH.name}")
    print(f"版本     : {data.get('version', '(未标注)')}")
    print(f"条目数   : {len(faqs)}")

    errors: list[str] = []

    if not faqs:
        errors.append("语料为空")

    ids = [str(f.get("id", "")) for f in faqs]
    duplicated = [i for i, c in Counter(ids).items() if c > 1]
    if duplicated:
        errors.append(f"id 重复: {duplicated}")

    for faq in faqs:
        fid = faq.get("id", "(无 id)")
        for field in REQUIRED_FIELDS:
            value = faq.get(field)
            if value is None or not str(value).strip():
                errors.append(f"{fid} 缺少字段 {field}")

        length = len(str(faq.get("content", "")))
        if length < MIN_CONTENT_LEN:
            errors.append(f"{fid} 正文过短（{length} 字，至少 {MIN_CONTENT_LEN}）")

    categories = Counter(str(f.get("category") or "通用") for f in faqs)
    print(f"分类数   : {len(categories)}")
    for name, count in categories.most_common():
        print(f"  · {name}: {count}")

    if errors:
        print(f"\n[FAIL] 发现 {len(errors)} 个问题：")
        for item in errors:
            print(f"  - {item}")
        return 1

    print("\n[PASS] 语料结构校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
