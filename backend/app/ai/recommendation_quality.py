"""Descriptive, reproducible quality diagnostics for a selected POI itinerary.

These are coverage/diversity diagnostics, not recommendation accuracy, user
satisfaction or evidence that the itinerary is feasible in the real world.
"""
from collections import Counter

from .itinerary_planner import _score


def evaluate_recommendation(candidates, places, style, location, method):
    """Compute reproducible, non-subjective diagnostics using DB POI fields."""
    candidate_ids = {p["id"] for p in candidates}
    selected_ids = [p["id"] for p in places]
    if not selected_ids or len(selected_ids) != len(set(selected_ids)):
        raise ValueError("selected POI IDs must be unique and nonempty")
    if any(id_ not in candidate_ids for id_ in selected_ids):
        raise ValueError("selected POI IDs must belong to candidates")
    categories = [p.get("category") for p in places if p.get("category")]
    counts = dict(sorted(Counter(categories).items()))
    rule_match_count = sum(_score(p, style, location) > 0 for p in places)
    n = len(places)
    return {
        "schema_version": 1,
        "metric_type": "descriptive_proxy_not_ground_truth",
        "method": method,
        "candidate_count": len(candidate_ids),
        "selected_count": n,
        "category_counts": counts,
        "distinct_category_count": len(counts),
        "category_diversity_ratio": round(len(counts) / n, 4),
        "rule_keyword_match_count": rule_match_count,
        "rule_keyword_match_ratio": round(rule_match_count / n, 4),
        "rule_is_actual_ranker": method == "local_rule_fallback",
        "limitations": [
            "匹配仅根据预设类别关键词与完整景点名称判断，不等于语义相关性或用户满意度",
            "类别多样性不代表推荐质量更高；专项主题行程可能合理地集中在一种类别",
            "未核实营业时间、门票、无障碍、客流或实际路网可达性",
            "DeepSeek排序不使用规则匹配比例作为模型准确率",
        ],
    }
