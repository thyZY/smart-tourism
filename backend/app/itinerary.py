"""Small, deterministic POI ordering preview based on geodesic distance.

No street routing, transit times, opening hours, prices, or optimized itineraries.
"""
from math import asin, cos, radians, sin, sqrt


def great_circle_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Approximate earth-surface great-circle distance in kilometers."""
    lng1, lat1 = first
    lng2, lat2 = second
    lat_delta = radians(lat2 - lat1)
    lng_delta = radians(lng2 - lng1)
    a = sin(lat_delta / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(lng_delta / 2) ** 2
    return 6371.0088 * 2 * asin(min(1.0, sqrt(a)))


def build_preview(
    features: list[dict],
    origin: tuple[float, float],
    max_stops: int = 4,
) -> dict:
    """Select nearby POIs greedily, beginning at an explicit map-center origin.

    The calculation is deterministic and heuristic: not a globally shortest path.
    """
    if not 2 <= max_stops <= 6:
        raise ValueError("max_stops should be between 2 and 6")

    candidates = {}
    for feature in features:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        place_id = props.get("id")
        if (
            not isinstance(place_id, int)
            or isinstance(place_id, bool)
            or geometry.get("type") != "Point"
            or len(coordinates) != 2
            or not all(isinstance(v, (int, float)) for v in coordinates)
        ):
            continue
        candidates[place_id] = feature

    remaining = list(candidates.values())
    selected = []
    segments = []
    position = origin
    for _ in range(min(max_stops, len(remaining))):
        chosen = min(
            remaining,
            key=lambda feature: (
                great_circle_km(position, tuple(feature["geometry"]["coordinates"])),
                feature["properties"]["id"],
            ),
        )
        distance = great_circle_km(position, tuple(chosen["geometry"]["coordinates"]))
        selected.append(chosen)
        segments.append(round(distance, 2))
        position = tuple(chosen["geometry"]["coordinates"])
        remaining.remove(chosen)

    between_stops = [
        great_circle_km(
            tuple(left["geometry"]["coordinates"]),
            tuple(right["geometry"]["coordinates"]),
        )
        for left, right in zip(selected, selected[1:])
    ]

    return {
        "method": "greedy_straight_line_proximity",
        "stops": selected,
        "segments_from_origin_direct_km": segments,
        "between_stops_direct_km": round(sum(between_stops), 2),
        "from_origin_direct_km": round(sum(
            great_circle_km(
                origin if index == 0 else tuple(selected[index - 1]["geometry"]["coordinates"]),
                tuple(feature["geometry"]["coordinates"]),
            )
            for index, feature in enumerate(selected)
        ), 2),
        "limitations": [
            "仅按地表直线距离进行启发式排序，不是道路导航或全局最优行程",
            "尚未使用开放时间、游览时长、交通方式、票价或实时客流",
            "起点为当前地图中心，非用户GPS位置",
        ],
    }
