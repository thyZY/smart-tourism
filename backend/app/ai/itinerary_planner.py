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


def choose_candidates(features, origin, max_stops, budget_minutes):
    """Closest eligible POIs, with known dwell times checked before selection.

    Road-time optimization happens later on the selected subset, not at this
    candidate-selection stage. Unknown visit time is never guessed.
    """
    if len(features) < 3:
        raise ValueError("匹配的真实景点不足3个，请放宽筛选类别或搜索范围")
    valid = []
    seen = set()
    for feature in features:
        props = feature.get("properties") or {}
        xy = (feature.get("geometry") or {}).get("coordinates")
        ident = props.get("id")
        if (type(ident) is not int or ident <= 0 or ident in seen or
                not isinstance(xy, list) or len(xy) != 2 or
                any(type(n) not in (float, int) for n in xy)):
            continue
        seen.add(ident)
        valid.append(feature)
    if len(valid) < 3:
        raise ValueError("可用于道路规划的有效景点不足3个")
    valid.sort(key=lambda f: (
        great_circle_km(origin, tuple(f["geometry"]["coordinates"])),
        f["properties"]["id"],
    ))
    # Limit database metadata reads and candidate-selection radius. No matrix
    # requests for a large unbounded set of 40+ POIs.
    shortlist = valid[:min(18, len(valid))]
    places = load_itinerary_places([f["properties"]["id"] for f in shortlist])
    metadata = {p["id"]: p for p in places}
    selected = []
    known_minutes = 0
    for feature in shortlist:
        if len(selected) >= max_stops:
            break
        visit = metadata[feature["properties"]["id"]]["visit_duration"]
        # 30 minutes/transfer is a conservative SELECTION reserve, not a
        # claimed roadway duration. Final fit uses measured road legs.
        proposed = known_minutes + (visit or 0)
        if visit is not None and proposed + (len(selected) * 30) > budget_minutes:
            continue
        selected.append(feature)
        known_minutes = proposed
    if len(selected) < 3:
        raise ValueError("当前时间预算无法容纳至少3个具备已知停留时长的景点，请增加可用小时数")
    return selected


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
            "reason": (f"与你的{category}兴趣条件匹配，且已收录于本地景点数据库"
                       if category else "已收录于本地景点数据库，按地理邻近性入选"),
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
        selected = choose_candidates(features, origin, max_stops, round(budget_hours * 60))
    chosen_ids = [f["properties"]["id"] for f in selected]
    route = plan_itinerary(chosen_ids, mode)
    if (route["optimized_order_ids"][0] != chosen_ids[0] or
            set(route["optimized_order_ids"]) != set(chosen_ids) or
            len(route["geometry"]["features"]) != len(chosen_ids) - 1 or
            route["mode"] != mode):
        raise ValueError("道路服务返回了不一致的景点行程")
    timeline, fits = build_timeline(route, selected, budget_hours * 60, start_time)
    limitations = [
        "候选景点按地图中心附近和已录入的停留时长初筛；道路时间矩阵仅优化已选景点顺序",
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
    return {
        "method": "grounded_poi_selection_plus_exact_road_matrix",
        "travel_mode": mode,
        "candidate_count": len(features),
        "budget_minutes": round(budget_hours * 60),
        "start_time": start_time,
        "within_time_budget": fits,
        "selected_places": {"type": "FeatureCollection", "features": selected},
        "itinerary": route,
        "timeline": timeline,
        "limitations": limitations,
    }
