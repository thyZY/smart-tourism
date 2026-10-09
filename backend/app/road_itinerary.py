"""Multi-stop road itinerary based on trusted POIs and Valhalla's travel-time matrix.

3–6 distinct POI IDs; the first selected stop remains the origin. Among all
permutations of remaining stops, choose the minimal matrix travel time.
An actual multi-leg route is fetched separately and used for map geometry.
This is not a schedule, navigation service, or a claim of live road conditions.
"""
from itertools import permutations
from math import isfinite
from os import getenv
from urllib.request import Request, urlopen
import json

from .db import get_db_connection
from .routing_routes import decode_polyline6


def load_itinerary_places(ids):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT p.id, p.name, ST_X(p.geom), ST_Y(p.geom),
                          to_jsonb(p)->>'visit_duration',
                          to_jsonb(p)->'tags',
                          to_jsonb(p)->>'indoor',
                          to_jsonb(p)->>'description'
                   FROM places p WHERE p.id = ANY(%s)""",
                (ids,),
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    places = {}
    for row in rows:
        # Optional tourism columns are read via to_jsonb and may be absent
        # before the metadata migration. Existing 5-field test fixtures
        # remain compatible with this read-only enrichment.
        ident, name, lon, lat, minutes = row[:5]
        tags = row[5] if len(row) > 5 else None
        indoor = row[6] if len(row) > 6 else None
        description = row[7] if len(row) > 7 else None
        visit = None
        if minutes is not None:
            try:
                number = int(minutes)
                visit = number if 0 < number <= 480 else None
            except (ValueError, TypeError):
                pass
        places[ident] = {
            "id": ident, "name": name, "lon": lon, "lat": lat,
            "visit_duration": visit,
            "tags": [tag.strip() for tag in tags
                     if isinstance(tag, str) and tag.strip()][:12]
            if isinstance(tags, list) else [],
            "indoor": indoor if type(indoor) is bool else
            True if indoor == "true" else False if indoor == "false" else None,
            "description": description.strip()[:600]
            if isinstance(description, str) else "",
        }
    if any(ident not in places for ident in ids):
        raise LookupError("部分景点ID不存在，无法计算多站路线")
    return [places[ident] for ident in ids]


def _post_json(url, payload, opener=urlopen):
    req = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Client-Id": "smart-tourism-prototype",
        },
    )
    with opener(req, timeout=20) as resp:
        return json.load(resp)


def _locations(places):
    return [{"lat": p["lat"], "lon": p["lon"]} for p in places]


def matrix_url():
    explicit = getenv("VALHALLA_MATRIX_URL")
    if explicit:
        return explicit
    route_url = getenv("VALHALLA_ROUTE_URL", "https://valhalla1.openstreetmap.de/route")
    return route_url.rstrip("/").rsplit("/", 1)[0] + "/sources_to_targets"


def request_matrix(places, mode, *, opener=urlopen):
    locations = _locations(places)
    return _post_json(matrix_url(), {
        "sources": locations, "targets": locations,
        "costing": mode, "units": "kilometers",
    }, opener=opener)


def validate_matrix(result, size):
    rows = result.get("sources_to_targets") if isinstance(result, dict) else None
    if not isinstance(rows, list) or len(rows) != size:
        raise ValueError("Valhalla matrix missing rows")
    times = []
    distances = []
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != size:
            raise ValueError("Valhalla matrix row has wrong length")
        trow, drow = [], []
        for j, cell in enumerate(row):
            if not isinstance(cell, dict):
                raise ValueError("Valhalla matrix has unreachable pair")
            t, d = cell.get("time"), cell.get("distance")
            if (type(t) not in (float, int) or type(d) not in (float, int)
                    or not isfinite(t) or not isfinite(d)
                    or t < 0 or d < 0 or (i != j and (t <= 0 or d <= 0))
                    or t > 86400):
                raise ValueError("Valhalla matrix returned missing/invalid travel cost")
            trow.append(float(t))
            drow.append(float(d))
        times.append(trow)
        distances.append(drow)
    return times, distances


def optimize_open_path(times):
    """Exact shortest open Hamiltonian path with fixed first POI (≤6)."""
    count = len(times)
    if not 3 <= count <= 6:
        raise ValueError("Expected 3–6 POIs")
    def cost(order):
        return sum(times[a][b] for a, b in zip(order, order[1:]))
    original = tuple(range(count))
    optimum = min(
        ((0,) + order for order in permutations(range(1, count))),
        key=lambda path: (cost(path), path),
    )
    return list(optimum), cost(original), cost(optimum)


def request_multileg_route(places, mode, *, opener=urlopen):
    url = getenv("VALHALLA_ROUTE_URL", "https://valhalla1.openstreetmap.de/route")
    return _post_json(url, {
        "locations": _locations(places), "costing": mode,
        "units": "kilometers", "directions_type": "none",
    }, opener=opener)


def build_itinerary_response(places, order, baseline_seconds, optimized_seconds,
                             response, mode):
    arranged = [places[idx] for idx in order]
    trip = response.get("trip") if isinstance(response, dict) else None
    legs = trip.get("legs") if isinstance(trip, dict) else None
    if not isinstance(legs, list) or len(legs) != len(arranged) - 1:
        raise ValueError("Valhalla did not return one road leg per selected pair")
    features = []
    total_distance = 0.0
    total_seconds = 0.0
    for index, leg in enumerate(legs):
        summary = leg.get("summary") or {}
        length = summary.get("length")
        seconds = summary.get("time")
        if (type(length) not in (int, float) or type(seconds) not in (int, float)
                or not isfinite(length) or not isfinite(seconds)
                or length <= 0 or seconds <= 0):
            raise ValueError("Invalid road leg travel cost")
        coordinates = decode_polyline6(leg["shape"])
        start, end = arranged[index], arranged[index + 1]
        features.append({
            "type": "Feature",
            "properties": {
                "sequence": index + 1,
                "from_id": start["id"], "to_id": end["id"],
                "mode": mode,
                "distance_km": round(float(length), 3),
                "duration_minutes": round(float(seconds) / 60, 1),
            },
            "geometry": {"type": "LineString", "coordinates": coordinates},
        })
        total_distance += float(length)
        total_seconds += float(seconds)
    known_visit = sum(p["visit_duration"] or 0 for p in arranged)
    missing_visit = sum(p["visit_duration"] is None for p in arranged)
    return {
        "mode": mode,
        "method": "exact_shortest_road_time_fixed_first_stop",
        "ordered_stops": [
            {"id": p["id"], "name": p["name"], "visit_duration": p["visit_duration"]}
            for p in arranged
        ],
        "original_order_ids": [p["id"] for p in places],
        "optimized_order_ids": [p["id"] for p in arranged],
        "estimated_original_travel_minutes": round(baseline_seconds / 60, 1),
        "estimated_optimized_travel_minutes": round(optimized_seconds / 60, 1),
        "travel_minutes_saved_estimate": round(max(0, baseline_seconds - optimized_seconds) / 60, 1),
        "distance_km": round(total_distance, 3),
        "duration_minutes": round(total_seconds / 60, 1),
        "known_visit_minutes": known_visit,
        "missing_visit_duration_count": missing_visit,
        "total_plan_minutes": round(total_seconds / 60 + known_visit, 1)
        if missing_visit == 0 else None,
        "geometry": {"type": "FeatureCollection", "features": features},
        "limitations": [
            "首站固定、终点自由；仅在所选站点的道路时间矩阵内求最短行驶/步行时间",
            "与实际道路折线对应的分段时间可能不同于矩阵估算",
            "未加入景点开放时间、休息、拥堵、泊车、公共交通班次及接驳时间",
            "若景点游览时长缺失，则不计算完整行程总用时",
            "公共Valhalla服务仅适用于小规模验证，非实时导航",
        ],
    }


def plan_itinerary(place_ids, mode):
    places = load_itinerary_places(place_ids)
    matrix_response = request_matrix(places, mode)
    times, _distances = validate_matrix(matrix_response, len(places))
    order, initial_time, optimized_time = optimize_open_path(times)
    route = request_multileg_route([places[i] for i in order], mode)
    return build_itinerary_response(
        places, order, initial_time, optimized_time, route, mode,
    )
