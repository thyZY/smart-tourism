"""Single-day itinerary grounded in PostgreSQL records, not LLM-created names.

The DeepSeek model may rank only IDs supplied from the database. If it fails
or is unconfigured, a transparent deterministic ranking is used.
"""
import json
import math
import os

from .deepseek_client import DeepSeekClient
from .itinerary_geo_service import valhalla_route
from .recommendation_quality import evaluate_recommendation

_CATEGORY_MATCH = {
    "历史": ("历史", "古迹", "陵园", "寺庙", "博物"),
    "文化": ("文化", "博物", "古迹", "历史"),
    "博物": ("博物",),
    "自然": ("公园", "自然", "陵园"),
    "亲子": ("公园", "博物", "自然"),
    "休闲": ("公园", "自然", "文化商业"),
}


def _score(poi, style, location):
    category = poi["category"]
    groups = [terms for keyword, terms in _CATEGORY_MATCH.items()
              if keyword in style or keyword in location]
    flat = set(term for group in groups for term in group)
    return (4 if any(t in category for t in flat) else 0) + (
        2 if location.strip() and location.strip() in poi["name"] else 0)


class ItineraryPlanner:
    def __init__(self, client=None):
        self.client = client

    def generate(self, location, days=1, style="历史文化",
                 people="普通游客", walking_limit="中等",
                 candidates=None, max_stops=4, travel_mode="pedestrian",
                 excluded_place_ids=None):
        if days != 1:
            raise ValueError("当前版本只支持单日行程")
        candidates = candidates or []
        unique = {}
        for p in candidates:
            if isinstance(p.get("id"), int):
                unique[p["id"]] = p
        candidates = list(unique.values())
        if not candidates:
            raise ValueError("数据库中尚无可供规划的真实景点")

        max_stops = min(max(2, int(max_stops)), 6)
        ranking = sorted(candidates, key=lambda p: (
            -_score(p, style, location), p["id"]
        ))
        preferred = [p["id"] for p in ranking[:max_stops]]
        method = "local_rule_fallback"
        # LLM is NEVER asked to invent names or coordinates.
        if os.getenv("DEEPSEEK_API_KEY") or self.client is not None:
            try:
                client = self.client if self.client is not None else DeepSeekClient()
                message = client.chat_json(
                    system_prompt=(
                        "你是旅游排序助手。只能从给定的数据库POI ID中选择不重复的ID，"
                        "按用户偏好输出JSON对象，例如{\"place_ids\":[1,2]}。"
                        "严禁新增POI、时间、道路长度或凭空声称开放、无障碍。"
                    ),
                    user_prompt=json.dumps({
                        "task": "select and order verified place IDs",
                        "location": location[:120], "style": style[:80],
                        "people": people[:80], "walking_limit": walking_limit[:80],
                        "max_stops": max_stops,
                        "candidates": [{"id": p["id"], "name": p["name"],
                                        "category": p["category"]} for p in ranking[:60]]
                    }, ensure_ascii=False),
                )
                raw_ids = message.get("place_ids") if isinstance(message, dict) else None
                allowed = {p["id"] for p in ranking[:60]}
                if isinstance(raw_ids, list):
                    selected = []
                    for id_ in raw_ids:
                        if type(id_) is int and id_ in allowed and id_ not in selected:
                            selected.append(id_)
                        if len(selected) == max_stops:
                            break
                    if len(selected) >= 2:
                        preferred = selected
                        method = "deepseek_ranked_verified_ids"
            except Exception:
                # Fail closed: a broken/timeout AI response must not fabricate results.
                method = "local_rule_fallback"

        mapping = {p["id"]: p for p in candidates}
        places = [mapping[id_] for id_ in preferred]
        # Heuristic scores describe our local rules, not the LLM's reasoning.
        rule_scores = {p["id"]: _score(p, style, location) for p in candidates}
        audit = {
            "method": method,
            "candidate_count": len(candidates),
            "rule": "类别关键词命中加4分；需求与景点名称完全匹配加2分；同分按ID排序",
            "score_is_selection_basis": method == "local_rule_fallback",
            "not_considered": ["开放时间", "票价", "实时客流", "无障碍条件", "真实道路时间"],
            "limitations": "规则分仅解释本地排序，不能用来解释DeepSeek内部决策。",
        }
        stops = [{
            "id": p["id"], "name": p["name"], "category": p["category"],
            "address": p["address"], "lng": p["lng"], "lat": p["lat"],
            "rule_score": rule_scores[p["id"]],
            "reason": ("数据库中的真实景点，类别为" + (p["category"] or "未分类")
                       + "；需人工确认开放时间及无障碍条件")
        } for p in places]
        routing = valhalla_route(places, mode=travel_mode)
        return {
            "schema_version": 1,
            "title": f"{location[:40]}·{style[:30]}一日游",
            "summary": "已根据现有PostGIS景点记录生成候选行程。未核实景区开放、客流和无障碍条件。",
            "planning_method": method,
            "recommendation_audit": audit,
            "excluded_place_ids": list(excluded_place_ids or []),
            "quality_diagnostics": evaluate_recommendation(candidates, places, style, location, method),
            "days": 1, "mode": travel_mode, "stops": stops,
            "route": routing,
            "selected_places": {"type": "FeatureCollection", "features": [{
                "type": "Feature",
                "properties": {"id": p["id"], "name": p["name"],
                               "category": p["category"], "address": p["address"]},
                "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]}
            } for p in places]},
            "warnings": [
                "只有route.status=verified_by_routing_service时才有真实道路距离与时间。",
                "当前未取得景区实际开放时间或无障碍设施证据。",
                "若未配置VALHALLA_URL，将仅显示直线预览，不可当导航路线。"
            ]
        }
