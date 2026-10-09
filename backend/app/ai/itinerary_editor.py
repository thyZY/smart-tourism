"""Editable, PostGIS-grounded one-day itinerary with a strict time budget.

The caller supplies only database IDs and constraints. Every edit is resolved
against PostGIS and re-routed using Valhalla; no earlier geometry is reused.
The first supplied POI stays the start. Locked IDs cannot be auto-dropped.
"""
from .itinerary_planner import build_timeline
from ..road_itinerary import load_itinerary_places, plan_itinerary
from ..db import get_db_connection


class BudgetConflict(Exception):
    """Selected/locked stops cannot fit the requested day."""


def fetch_selected_features(ids):
    """Resolve all input IDs from PostGIS, preserving the caller's ordering."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, name, category, address, ST_X(geom), ST_Y(geom)
                   FROM places WHERE id = ANY(%s)""",
                (ids,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    by_id = {
        row[0]: {
            "type": "Feature",
            "properties": {
                "id": row[0], "name": row[1],
                "category": row[2], "address": row[3],
            },
            "geometry": {
                "type": "Point", "coordinates": [row[4], row[5]],
            },
        }
        for row in rows
    }
    if any(ident not in by_id for ident in ids):
        raise LookupError("景点ID不存在或已被删除，请更新列表后重试")
    return [by_id[ident] for ident in ids]


def _remove_optional_tail(ids, locked):
    """Deterministic: drop last editable stop; never drop the fixed first."""
    for index in range(len(ids) - 1, 0, -1):
        if ids[index] not in locked:
            return ids.pop(index)
    raise BudgetConflict("固定首站和锁定景点超出时间预算，无法自动删减")


def replan_edited_itinerary(place_ids, locked_ids, mode, budget_hours,
                            start_time, auto_trim=True):
    """Recompute the complete route and timeline after manual POI/time edits.

    A known dwell-time overrun is checked before calling the routing provider.
    With auto_trim, the last *unlocked* optional stop is removed, at most
    three stops may remain, and real road times are calculated afresh.
    Unknown dwell times remain unknown; they cannot prove budget feasibility.
    """
    if len(place_ids) < 3 or len(place_ids) > 6:
        raise ValueError("行程需要3—6个景点")
    if len(place_ids) != len(set(place_ids)):
        raise ValueError("不能选择重复景点")
    if not set(locked_ids).issubset(place_ids):
        raise ValueError("锁定景点必须属于当前行程")
    if mode not in ("pedestrian", "bicycle", "auto"):
        raise ValueError("交通方式不支持")
    if not 3 <= budget_hours <= 12:
        raise ValueError("时间预算须为3—12小时")

    known_features = fetch_selected_features(place_ids)
    by_id = {f["properties"]["id"]: f for f in known_features}
    full_metadata = {
        p["id"]: p for p in load_itinerary_places(place_ids)
    }
    remaining = list(place_ids)
    locked = set(locked_ids) | {place_ids[0]}
    removed = []
    budget = budget_hours * 60

    while True:
        known_dwell = sum(
            full_metadata[ident]["visit_duration"] or 0
            for ident in remaining
        )
        missing_dwell = any(
            full_metadata[ident]["visit_duration"] is None
            for ident in remaining
        )
        if known_dwell > budget:
            if not auto_trim or len(remaining) <= 3:
                raise BudgetConflict("景点停留时间已经超过预算，请移除景点或延长时间")
            removed.append(_remove_optional_tail(remaining, locked))
            continue

        # Valhalla is the only source of real road travel times. Do not guess.
        route = plan_itinerary(remaining, mode)
        if (route["mode"] != mode
                or route["optimized_order_ids"][0] != remaining[0]
                or len(route["optimized_order_ids"]) != len(remaining)
                or set(route["optimized_order_ids"]) != set(remaining)
                or len(route["geometry"]["features"]) != len(remaining) - 1):
            raise ValueError("道路规划服务返回的景点或分段不一致")
        ordered_features = [by_id[ident] for ident in remaining]
        timeline, fits = build_timeline(route, ordered_features, budget, start_time)
        # Unknown dwell time is never invented. But known dwell + measured
        # travel still provides a provable lower bound for budget conflicts.
        lower_bound = known_dwell + route["duration_minutes"]
        if lower_bound > budget:
            fits = False
        if fits is False and auto_trim:
            if len(remaining) <= 3:
                raise BudgetConflict("即使保留3站仍超出预算，请延长时间或替换景点")
            removed.append(_remove_optional_tail(remaining, locked))
            continue
        break

    limitations = [
        "行程由用户手动锁定或替换景点，实际地点与坐标来自PostGIS，不是DeepSeek生成",
        "若需要自动减站，优先移除列表末尾未锁定的景点，未执行全库最优组合搜索",
        "首个景点始终固定为起点；锁定仅表示必须保留，不保证其他锁定景点的排列位置",
        "暂定到离时间没有核验实际营业时间、预约、休息、停车或实时交通",
    ]
    if fits is None:
        limitations.append("部分景点缺少停留时间，无法确认完整行程是否符合预算")
    elif missing_dwell and fits is False:
        limitations.append("虽然部分停留时间未知，但已知停留时间加实际道路时间已经超出预算")
    if fits is False:
        limitations.append("这份行程超出预算：关闭了自动减站，请手动调整")
    if removed:
        limitations.append("为了符合时间预算，自动移除未锁定景点：" +
                           "、".join(by_id[ident]["properties"]["name"] for ident in removed))
    return {
        "method": "manual_edited_grounded_road_itinerary",
        "ai_mode": "manual_replan",
        "explanation": "用户修改景点与预算，PostGIS核实后使用Valhalla重新计算道路路线",
        "travel_mode": mode,
        "start_time": start_time,
        "budget_minutes": budget,
        "within_time_budget": fits,
        "selected_places": {
            "type": "FeatureCollection",
            "features": [by_id[ident] for ident in remaining],
        },
        "itinerary": route,
        "timeline": timeline,
        "locked_place_ids": [ident for ident in remaining if ident in locked_ids],
        "dropped_place_ids": removed,
        "limitations": limitations,
    }
