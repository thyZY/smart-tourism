"""Explainable heuristic recommendation on existing, database-grounded POIs.

No LLM-generated IDs, distances, or factual claims. This stage is a POI subset
selector, not a global road optimization; Valhalla handles actual road costs
after candidate selection.
"""
from math import isfinite

from ..itinerary import great_circle_km

# A Chinese query keyword only defines a *preference*. Actual attribute
# evidence must come from a tag already present in the places database.
INTEREST_TAGS = {
    "博物馆": ("博物", "文物", "展览", "馆藏", "文博"),
    "古迹": ("遗址", "古迹", "城墙", "古建", "古城"),
    "历史": ("历史", "文物", "遗址", "古迹", "故居", "城墙"),
    "文化": ("文化", "艺术", "展览", "古迹", "建筑"),
    "自然": ("自然", "山水", "森林", "生态", "湿地", "公园"),
    "公园": ("公园", "景观", "自然", "花园", "休闲"),
    "亲子": ("亲子", "科普", "动物", "儿童"),
    "建筑": ("建筑", "古建", "城门", "街区", "故居"),
    "艺术": ("艺术", "美术", "展览", "演出"),
    "拍照": ("观景", "地标", "摄影", "景观"),
}


def _valid_features(features):
    seen = set()
    valid = []
    for feature in features[:100]:
        prop = feature.get("properties") or {}
        point = (feature.get("geometry") or {}).get("coordinates")
        ident = prop.get("id")
        if (type(ident) is not int or ident <= 0 or ident in seen
                or not isinstance(point, list) or len(point) != 2
                or any(type(x) not in (float, int) or not isfinite(x) for x in point)
                or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
            continue
        seen.add(ident)
        valid.append(feature)
    return valid


def _score(feature, meta, origin, selected, categories, interest_tags, query):
    prop = feature["properties"]
    category = prop.get("category") or ""
    tags = meta.get("tags") or []
    coords = tuple(feature["geometry"]["coordinates"])
    dist = great_circle_km(origin, coords)
    if not isfinite(dist):
        return None
    matched = [tag for tag in tags if any(token in tag for token in interest_tags)]
    matched = matched[:3]
    category_match = category in categories
    repeat = sum(p["properties"].get("category") == category for p in selected)

    # Positive score balances stated interests and genuine diversity. Distances
    # here are great-circle approximations, not claimed pedestrian road times.
    diversity = 2.8 if selected and repeat == 0 else -1.0 * repeat
    prox = min(dist, 20.0) * 0.13
    cluster = min((
        great_circle_km(coords, tuple(item["geometry"]["coordinates"]))
        for item in selected
    ), default=0.0)
    cluster_penalty = min(cluster, 12.0) * 0.17

    indoor = meta.get("indoor")
    wants_indoor = "室内" in query
    wants_outdoor = "户外" in query or "室外" in query
    indoor_match = ((wants_indoor and indoor is True) or
                    (wants_outdoor and indoor is False))
    indoor_conflict = ((wants_indoor and indoor is False) or
                       (wants_outdoor and indoor is True))
    indoor_bonus = 1.2 if indoor_match else -1.2 if indoor_conflict else 0.0
    completeness = 0.8 if meta.get("visit_duration") is None else 0.0
    score = (4.0 * category_match + 1.4 * len(matched) + diversity
             + indoor_bonus - prox - cluster_penalty - completeness)

    reason = ([f"匹配兴趣类别「{category}」"] if category_match else
              [f"已录入类别「{category}」"] if category else ["已收录于景点数据库"])
    if matched:
        reason.append("匹配已录入标签：" + "、".join(matched))
    if indoor_match:
        reason.append("已录入室内外属性符合需求")
    reason.append(f"距地图中心约{dist:.1f}公里（直线近似）")
    if meta.get("visit_duration") is None:
        reason.append("游览时长资料缺失")

    return {
        "score": round(score, 3),
        "category_match": category_match,
        "matched_tags": matched,
        "diversity_score": round(diversity, 2),
        "distance_from_map_center_km": round(dist, 2),
        "indoor_match": indoor_match,
        "has_visit_duration": meta.get("visit_duration") is not None,
        "reason": "；".join(reason),
        "source": "postgis_tourism_metadata",
        "algorithm": "explainable_greedy_v1",
    }


def select_ranked_places(features, origin, max_stops, budget_minutes,
                         intent, query, load_metadata):
    """Greedy reranking over up to 100 genuine PostGIS features.

    The first chosen POI becomes the fixed route origin. Every subsequent
    choice reranks the *remaining* candidates to favor variety. All ties are
    deterministic. Travel-time and opening-hour constraints are checked later
    and may still invalidate an otherwise promising candidate combination.
    """
    valid = _valid_features(features)
    if len(valid) < 3:
        raise ValueError("匹配的有效景点不足3个，请放宽筛选类别或搜索范围")

    places = load_metadata([f["properties"]["id"] for f in valid])
    metadata = {item["id"]: item for item in places}
    preferred = set((intent or {}).get("categories") or [])
    avoided = set((intent or {}).get("avoid_categories") or [])
    terms = {token for keyword, aliases in INTEREST_TAGS.items()
             if keyword in query for token in aliases}

    remaining = {f["properties"]["id"]: f for f in valid}
    selected, known_minutes = [], 0
    while remaining and len(selected) < max_stops:
        options = []
        for ident, f in remaining.items():
            meta = metadata[ident]
            category = f["properties"].get("category") or ""
            if category in avoided:
                continue
            duration = meta.get("visit_duration")
            # An approximate 30min/transfer *selection reserve*; never
            # displayed as actual road time, which comes from Valhalla.
            if known_minutes + (duration or 0) + len(selected) * 30 > budget_minutes:
                continue
            evidence = _score(f, meta, origin, selected, preferred, terms, query)
            if evidence is not None:
                options.append((f, meta, evidence))
        if not options:
            break
        feature, meta, evidence = max(
            options, key=lambda item: (
                item[2]["score"],
                -item[2]["distance_from_map_center_km"],
                -item[0]["properties"]["id"],
            )
        )
        # Add transparent evidence only to the returned subset, without
        # mutating the GeoJSON features shared by other endpoints.
        annotated = {
            **feature,
            "properties": {
                **feature["properties"],
                "recommendation": evidence,
            },
        }
        selected.append(annotated)
        remaining.pop(feature["properties"]["id"])
        known_minutes += meta.get("visit_duration") or 0

    if len(selected) < 3:
        raise ValueError("可用时间和候选景点资料无法形成至少3站，请增加时间或放宽条件")
    return selected
