"""Grounded one-day AI itinerary: language intent -> real POIs -> road solver.

DeepSeek provides validated preferences ONLY. This service never asks an LLM to
invent places, roads, arrival times or opening hours. Unknown durations remain
unknown. One-way, fixed-first-stop, 3-6 places, single transport mode.
"""
from datetime import datetime, timedelta

from ..itinerary import great_circle_km
from ..road_itinerary import load_itinerary_places, plan_itinerary

ALLOWED_MODES = ("pedestrian", "bicycle", "auto")


def resolve_travel_mode(query, intent, override=None):
    """Explicit user-selected mode overrides words and soft preferences."""
    if override is not None:
        if override not in ALLOWED_MODES:
            raise ValueError("不支持该交通方式")
        return override
    if any(word in query for word in ("骑行", "骑车", "自行车", "单车")):
        return "bicycle"
    if any(word in query for word in ("驾车", "开车", "自驾", "打车", "出租车", "网约车")):
        return "auto"
    if any(word in query for word in ("步行", "徒步", "走路游览")) and not any(
        word in query for word in ("不想步行", "不想走路", "少走路", "不要步行")
    ):
        return "pedestrian"
    if intent.get("walking_level") == "low":
        return "auto"
    return "pedestrian"


def choose_candidates(features, origin, max_stops, budget_minutes,
                      intent=None, query=""):
    """Explainable POI subset selection before actual Valhalla road routing."""
    from .recommendation import select_ranked_places
    return select_ranked_places(
        features, origin, max_stops, budget_minutes,
        intent or {}, query, load_itinerary_places,
    )


def _clock(minutes):
    if minutes is None:
        return None
    return (datetime(2000, 1, 1) + timedelta(minutes=minutes)).strftime("%H:%M")


def build_timeline(itinerary, selected, budget_minutes, start_time):
    """Produce transparent *provisional* times, never asserted opening hours."""
    feature_by_id = {f["properties"]["id"]: f for f in selected}
    start_minutes = int(start_time[:2]) * 60 + int(start_time[3:])
    now = float(start_minutes)
    entries = []
    legs = itinerary["geometry"]["features"]
    for i, stop in enumerate(itinerary["ordered_stops"]):
        leg_minutes = 0.0 if i == 0 else legs[i - 1]["properties"]["duration_minutes"]
        now = None if now is None else now + leg_minutes
        arrival = _clock(now)
        dwell = stop.get("visit_duration")
        finish = now + dwell if now is not None and dwell is not None else None
        feature = feature_by_id[stop["id"]]
        category = feature["properties"].get("category", "")
        entries.append({
            "id": stop["id"],
            "name": stop["name"],
            "category": category,
            "reason": (feature["properties"].get("recommendation") or {}).get("reason")
                      or (f"已录入类别「{category}」" if category else "已收录于本地景点数据库"),
            "recommendation_score": (feature["properties"].get("recommendation") or {}).get("score"),
            "matched_tags": (feature["properties"].get("recommendation") or {}).get("matched_tags", []),
            "arrival_time": arrival,
            "departure_time": _clock(finish),
            "visit_duration": dwell,
            "travel_from_previous_minutes": round(leg_minutes, 1),
        })
        now = finish
    total_minutes = itinerary.get("total_plan_minutes")
    fit = None if total_minutes is None else total_minutes <= budget_minutes
    return entries, fit


def build_personalized_itinerary(features, origin, intent, mode, max_stops,
                                  budget_hours, start_time, selected=None):
    if selected is None:
        selected = choose_candidates(features, origin, max_stops, round(budget_hours * 60), intent)
    chosen_ids = [f["properties"]["id"] for f in selected]
    route = plan_itinerary(chosen_ids, mode)
    if (route["optimized_order_ids"][0] != chosen_ids[0] or
            set(route["optimized_order_ids"]) != set(chosen_ids) or
            len(route["geometry"]["features"]) != len(chosen_ids) - 1 or
            route["mode"] != mode):
        raise ValueError("道路服务返回了不一致的景点行程")
    timeline, fits = build_timeline(route, selected, budget_hours * 60, start_time)
    limitations = [
        "候选景点由兴趣类别、已有资料标签、多样性和地理距离启发式筛选；Valhalla仅优化所选景点顺序，并非南京全域最优景点组合",
        "建议到达时间是假设指定时间可入园的预排，不代表真实营业时间或预约情况",
        "不含排队、休息、餐饮、停车、上下车及实时交通变化",
        "当前仅支持单日、单一交通方式、固定首站3—6景点",
    ]
    if intent.get("walking_level") == "low":
        limitations.append("站间选择交通方式不能保证景区内少走路或无障碍设施")
    if any(f["properties"].get("category") is None for f in selected):
        limitations.append("部分景点类别缺失，推荐理由仅能说明其已在库")
    if fits is None:
        limitations.append("存在未知景点停留时长，无法判定是否符合可用时间预算")
    elif not fits:
        limitations.append("实际道路交通与停留时间超出时间预算；建议减少景点或增加时间")
    category_counts = {}
    matched_tag_pois = 0
    for feature in selected:
        category = feature["properties"].get("category") or "未分类"
        category_counts[category] = category_counts.get(category, 0) + 1
        recommendation = feature["properties"].get("recommendation") or {}
        if recommendation.get("matched_tags"):
            matched_tag_pois += 1
    return {
        "method": "grounded_poi_selection_plus_exact_road_matrix",
        "travel_mode": mode,
        "candidate_count": len(features),
        "budget_minutes": round(budget_hours * 60),
        "start_time": start_time,
        "within_time_budget": fits,
        "selected_places": {"type": "FeatureCollection", "features": selected},
        "recommendation_method": "explainable_greedy_v1",
        "recommendation_summary": {
            "selected_count": len(selected),
            "distinct_categories": len(category_counts),
            "categories": category_counts,
            "verified_tag_match_pois": matched_tag_pois,
            "origin_distance_kind": "haversine_candidate_proxy",
            "road_distance_provider": "Valhalla_OSM",
        },
        "recommendation_criteria": [
            "兴趣类别及现有PostGIS类别匹配",
            "仅使用数据库实际存在且与需求词匹配的旅游标签",
            "鼓励不同类别，降低同类景点重复推荐",
            "地图中心和景点间直线距离仅作候选阶段距离近似",
            "依据已知停留时长和每站30分钟粗略预留初筛；实际道路时间由Valhalla重新计算",
        ],
        "itinerary": route,
        "timeline": timeline,
        "limitations": limitations,
    }
