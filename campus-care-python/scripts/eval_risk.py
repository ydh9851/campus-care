"""风险研判评估（离线、零依赖、可进 CI）。

为什么需要它：
    风险等级是心理平台最不能出错的一环 —— 漏判一次危机，代价是不可逆的。
    但在这之前，「能不能识别高危」全靠人工随手试几条，谁也说不清准确率。
    这个脚本用一份带标注的样本集跑**线上同一套规则**（risk_agent.classify_risk），
    给出每类的 precision / recall / F1 和危机召回率，改动词库之后有没有退化一目了然。

定位说明：
    这份标注集是「回归基线」——它记录的是当前规则库的期望行为，
    目的是防止改动把已经能识别的场景改坏（回归），而不是宣称这套规则的绝对准确率。
    要提升绝对准确率，需要引入更大规模的真实标注数据 + 人工复核。

用法：
    python campus-care-python/scripts/eval_risk.py
    python campus-care-python/scripts/eval_risk.py --min-macro-f1 0.85 --min-high-recall 0.9
退出码非 0 表示未达标（CI 据此判定）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.risk_agent import classify_risk  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "risk_eval.jsonl"

LEVELS = ("HIGH", "MEDIUM", "LOW")


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"[FAIL] 第 {lineno} 行 JSON 解析失败: {e}")
            if item.get("level") not in LEVELS:
                raise SystemExit(f"[FAIL] 第 {lineno} 行 level 非法: {item.get('level')}")
            cases.append(item)
    return cases


def evaluate(cases: list[dict]) -> dict:
    """跑规则，统计混淆矩阵与指标。"""
    confusion: dict[tuple[str, str], int] = defaultdict(int)  # (期望, 实际)
    wrong: list[dict] = []

    for case in cases:
        expected = case["level"]
        predicted = classify_risk(case["text"]).get("level", "LOW")
        confusion[(expected, predicted)] += 1
        if expected != predicted:
            wrong.append({
                "id": case.get("id"),
                "text": case["text"],
                "expected": expected,
                "predicted": predicted,
            })

    total = len(cases)
    correct = sum(v for (e, p), v in confusion.items() if e == p)

    per_class = {}
    for level in LEVELS:
        tp = confusion[(level, level)]
        fp = sum(confusion[(other, level)] for other in LEVELS if other != level)
        fn = sum(confusion[(level, other)] for other in LEVELS if other != level)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class[level] = {
            "support": tp + fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    return {
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(LEVELS),
        "per_class": per_class,
        "confusion": confusion,
        "wrong": wrong,
    }


def print_report(result: dict) -> None:
    print("=" * 78)
    print(f"风险研判评估（样本 {result['total']} 条，规则来自 app/agents/risk_agent.classify_risk）")
    print("=" * 78)
    print(f"{'类别':<10}{'样本数':>8}{'Precision':>12}{'Recall':>10}{'F1':>10}")
    print("-" * 78)
    for level in LEVELS:
        m = result["per_class"][level]
        print(f"{level:<10}{m['support']:>8}{m['precision']:>12.3f}"
              f"{m['recall']:>10.3f}{m['f1']:>10.3f}")
    print("-" * 78)
    print(f"准确率   : {result['accuracy']:.3f}")
    print(f"Macro-F1 : {result['macro_f1']:.3f}")
    print(f"危机召回率(Recall@HIGH): {result['per_class']['HIGH']['recall']:.3f}"
          f"  ← 最关键的指标，漏判危机不可接受")
    print("=" * 78)

    if result["wrong"]:
        print(f"\n误判明细（共 {len(result['wrong'])} 条）：")
        for item in result["wrong"]:
            print(f"  · [{item['id']}] {item['text']}")
            print(f"      期望 {item['expected']}，实际 {item['predicted']}")
    else:
        print("\n全部样本判定正确")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-macro-f1", type=float, default=0.90,
                        help="Macro-F1 下限，低于此值退出码非 0")
    parser.add_argument("--min-high-recall", type=float, default=0.90,
                        help="HIGH 类召回率下限（危机不能漏判）")
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"[FAIL] 找不到标注集: {DATA_PATH}")
        return 1

    cases = load_cases(DATA_PATH)
    if not cases:
        print("[FAIL] 标注集为空")
        return 1

    result = evaluate(cases)
    print_report(result)

    failed = []
    if result["macro_f1"] < args.min_macro_f1:
        failed.append(f"Macro-F1 {result['macro_f1']:.3f} < 阈值 {args.min_macro_f1:.3f}")
    high_recall = result["per_class"]["HIGH"]["recall"]
    if high_recall < args.min_high_recall:
        failed.append(f"HIGH 召回率 {high_recall:.3f} < 阈值 {args.min_high_recall:.3f}")

    if failed:
        print("\n[FAIL] " + "；".join(failed))
        return 1
    print("\n[PASS] 风险研判评估通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
