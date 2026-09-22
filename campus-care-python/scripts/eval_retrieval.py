"""RAG 检索质量评估（离线、可进 CI）。

用一份人工标注的测试集（口语化提问 → 期望命中的 FAQ）对比不同检索方案，
输出 Recall@1 / Recall@3 / Recall@5 与 MRR。

为什么需要它：
    换向量模型、改语料、调阈值、上混合检索之后，「感觉变好了」是没法验收的。
    这个脚本每次都给出同一套指标，改动是否有效一目了然，
    也能在 CI 里卡住底线（--min-recall3），防止某次改动把检索质量改回去。

测试集的设计要点：
    提问全部用学生的口语表达，刻意避开 FAQ 标题里的原词。
    「翻来覆去睡不着」对「失眠了怎么办」这种题，字面匹配必然失败、
    语义匹配才能命中 —— 这正是不同方案的差距所在。

三种检索模式（--mode）：
    vector  仅向量（旧行为）
    bm25    仅 BM25（零依赖，CI 默认用它）
    hybrid  BM25 + 向量 + RRF + 轻量重排（线上默认）

用法：
    python campus-care-python/scripts/eval_retrieval.py
    python campus-care-python/scripts/eval_retrieval.py --provider local_hash --mode hybrid
    python campus-care-python/scripts/eval_retrieval.py --mode bm25 --min-recall3 0.5
退出码非 0 表示未达标（CI 据此判定）。
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.hybrid import HybridRetriever  # noqa: E402
from app.rag.loader import build_document_text, load_faq  # noqa: E402

# ---------------------------------------------------------------------------
# 标注集：口语化提问 -> 可接受的 FAQ id（可以是多个）
#
# 为什么允许一个提问对应多条：
#   知识库细化之后，同一个提问常常有多条都算合理答案。
#   「室友不理我」既可以是「被室友孤立」，也可以是「集体宿舍生活受不了」。
#   只认一条会把「命中了相邻话题」也算成失败，低估实际效果。
#   但也不能滥标 —— 只把确实能回答该提问的条目列进来。
# ---------------------------------------------------------------------------
CASES = [
    ("晚上翻来覆去睡不着，白天没精神", ["faq-001", "faq-026"]),
    ("一到考试就紧张得不行，手都在抖", ["faq-002", "faq-055"]),
    ("我这样是不是已经抑郁了", ["faq-003"]),
    ("有时候会冒出伤害自己的念头", ["faq-004", "faq-088"]),
    ("室友都不怎么理我，在宿舍很压抑", ["faq-005", "faq-103"]),
    ("作业和考试压得我喘不过气来", ["faq-006"]),
    ("突然心跳加速、喘不上气，感觉自己要死了", ["faq-007", "faq-047"]),
    ("觉得自己什么都做不好，特别没用", ["faq-008", "faq-074"]),
    ("分手之后一直缓不过来", ["faq-009"]),
    ("学校里有哪里可以找人聊聊", ["faq-010", "faq-095", "faq-100"]),
    ("怎么看出来身边的同学状态不对", ["faq-011", "faq-093"]),
    ("通宵之后怎么把状态缓回来", ["faq-012", "faq-028"]),
    ("明知道该做，但就是一直拖着不动", ["faq-013", "faq-056"]),
    ("容易紧张算不算是一种病", ["faq-014"]),
    ("一上台就一句话都说不出来", ["faq-015", "faq-058"]),
    ("身边的人都比我强，压力很大", ["faq-016", "faq-067"]),
    ("朋友哭得很厉害，我不知道该说什么", ["faq-017", "faq-066"]),
    ("冥想对调节情绪真的有用吗", ["faq-018"]),
    ("躺到床上脑子一直在转停不下来", ["faq-019"]),
    ("挂科了，感觉一切都完了", ["faq-020"]),
    ("第一次去做心理咨询，需要准备什么", ["faq-021"]),
    ("总觉得自己没什么价值", ["faq-022"]),
    ("刚才发完脾气，现在特别后悔", ["faq-023", "faq-033"]),
    ("在网上刷到了和自杀有关的内容", ["faq-024"]),
]


def build_index(embedder, faqs):
    """把 FAQ 编码成矩阵（文档侧，不加查询指令）。"""
    import numpy as np

    texts = [build_document_text(item) for item in faqs]
    vecs = embedder.encode(texts, is_query=False)
    return np.array(vecs, dtype="float32")


def make_retriever(mode: str, provider: str, faqs: list):
    """按模式返回一个 callable(query, top_k) -> List[doc]。"""
    if mode == "bm25":
        # 纯 BM25 不需要向量模型，CI 里跑这条路径零额外开销
        retriever = HybridRetriever(vector_search=None, faqs=faqs)
        return lambda query, k: retriever.search(query, top_k=k, min_score=0.0), "bm25", 0

    from app.rag.embedding import BgeEmbedder, LocalHashEmbedder

    if provider == "bge":
        from app.config import get_settings
        embedder = BgeEmbedder(get_settings().bge_model)
    else:
        embedder = LocalHashEmbedder()

    import numpy as np

    matrix = build_index(embedder, faqs)
    id_list = [str(item.get("id")) for item in faqs]

    def vector_search(query: str, top_k: int):
        qv = np.array(embedder.encode([query], is_query=True)[0], dtype="float32")
        sims = matrix @ qv
        order = np.argsort(-sims)[:top_k]
        hits = []
        for idx in order:
            item = faqs[int(idx)]
            hits.append({
                "id": id_list[int(idx)],
                "title": item.get("title", ""),
                "category": item.get("category", "通用"),
                "content": item.get("content", ""),
                "score": float(sims[int(idx)]),
                "source": item.get("source", ""),
                "retrieval": "vector",
            })
        return hits

    if mode == "vector":
        return vector_search, embedder.name, embedder.dim

    retriever = HybridRetriever(vector_search=vector_search, faqs=faqs)
    return (lambda query, k: retriever.search(query, top_k=k, min_score=0.0),
            embedder.name, embedder.dim)


def evaluate(mode: str, provider: str, faqs: list, cases: list, k_max: int = 5) -> dict:
    search, name, dim = make_retriever(mode, provider, faqs)
    id_to_idx = {str(item.get("id")): i for i, item in enumerate(faqs)}

    hit1 = hit3 = hitk = 0
    mrr = 0.0
    top1_scores: list[float] = []
    misses = []

    for query, expect in cases:
        expects = {expect} if isinstance(expect, str) else set(expect)
        targets = {id_to_idx[e] for e in expects if e in id_to_idx}
        if not targets:
            raise ValueError(f"标注集里的 id 在语料中不存在: {expects}")

        hits = search(query, k_max)
        ids = [str(h.get("id")) for h in hits]
        if hits:
            top1_scores.append(float(hits[0].get("score", 0.0)))

        rank = -1
        for pos, doc_id in enumerate(ids, start=1):
            if doc_id in {str(faqs[i].get("id")) for i in targets}:
                rank = pos
                break

        if rank == 1:
            hit1 += 1
        if 1 <= rank <= 3:
            hit3 += 1
        if 1 <= rank <= k_max:
            hitk += 1
            mrr += 1.0 / rank
        else:
            top_title = hits[0].get("title") if hits else "(无结果)"
            misses.append((query, "/".join(sorted(expects)), top_title))

    total = len(cases)
    return {
        "mode": mode,
        "provider": name,
        "dim": dim,
        "recall1": hit1 / total,
        "recall3": hit3 / total,
        f"recall{k_max}": hitk / total,
        "mrr": mrr / total,
        "avg_top1": (sum(top1_scores) / len(top1_scores)) if top1_scores else 0.0,
        "k_max": k_max,
        "misses": misses,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["bge", "local_hash"], default=None,
                        help="只评估指定向量化方案，默认两种都跑（bm25 模式忽略此项）")
    parser.add_argument("--mode", choices=["vector", "bm25", "hybrid"], default="hybrid",
                        help="检索模式，默认 hybrid（线上默认）")
    parser.add_argument("--min-recall3", type=float, default=None, help="Recall@3 下限")
    parser.add_argument("--min-recall5", type=float, default=None, help="Recall@5 下限")
    parser.add_argument("--min-mrr", type=float, default=None, help="MRR 下限")
    args = parser.parse_args()

    faqs = load_faq()
    if not faqs:
        print("FAQ 语料为空，无法评估")
        return 1

    if args.mode == "bm25":
        # BM25 与向量模型无关，跑一次即可
        providers = [args.provider or "local_hash"]
    else:
        providers = [args.provider] if args.provider else ["local_hash", "bge"]

    results = []
    for provider in providers:
        print(f"\n>>> 正在评估 mode={args.mode}, provider={provider} ...")
        results.append(evaluate(args.mode, provider, faqs, CASES))

    k_max = 5
    print("\n" + "=" * 88)
    print(f"RAG 检索质量评估（语料 {len(faqs)} 条，测试集 {len(CASES)} 条，单条可多答案，模式 {args.mode}）")
    print("=" * 88)
    print(f"{'方案':<12}{'维度':>6}{'Recall@1':>11}{'Recall@3':>11}"
          f"{'Recall@' + str(k_max):>11}{'MRR':>8}{'Top1均分':>10}")
    print("-" * 88)
    for r in results:
        print(f"{r['provider']:<12}{r['dim']:>6}{r['recall1']:>10.1%}"
              f"{r['recall3']:>11.1%}{r[f'recall{k_max}']:>11.1%}"
              f"{r['mrr']:>8.3f}{r['avg_top1']:>10.3f}")
    print("=" * 88)

    for r in results:
        if r["misses"]:
            print(f"\n[{r['provider']}] Recall@{k_max} 未命中 {len(r['misses'])} 条：")
            for query, expect, got in r["misses"]:
                print(f"    · {query}  →  期望 {expect}，实际命中「{got}」")
        else:
            print(f"\n[{r['provider']}] Recall@{k_max} 全部命中")

    # 阈值只对第一组结果判定（CI 里通常只跑一组）
    primary = results[0]
    failed = []
    if args.min_recall3 is not None and primary["recall3"] < args.min_recall3:
        failed.append(f"Recall@3 {primary['recall3']:.3f} < 阈值 {args.min_recall3:.3f}")
    if args.min_recall5 is not None and primary[f"recall{k_max}"] < args.min_recall5:
        failed.append(f"Recall@{k_max} {primary[f'recall{k_max}']:.3f} < 阈值 {args.min_recall5:.3f}")
    if args.min_mrr is not None and primary["mrr"] < args.min_mrr:
        failed.append(f"MRR {primary['mrr']:.3f} < 阈值 {args.min_mrr:.3f}")

    if failed:
        print("\n[FAIL] " + "；".join(failed))
        return 1
    print("\n[PASS] 检索质量达标")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
