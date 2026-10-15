"""Verified local-Valhalla time-matrix optimization of 2–6 database POIs.

Uses the same localhost-only service trust boundary as itinerary_geo_service.
No public routing endpoint or invented road distance is used.
"""
import json
import math
import os
from itertools import permutations
from urllib.request import Request, urlopen

from .itinerary_geo_service import fetch_candidates, valhalla_route


def optimize_fixed_first(times):
    n = len(times)
    if not 2 <= n <= 6 or any(len(row) != n for row in times):
        raise ValueError("Invalid routing matrix dimensions")
    for i, row in enumerate(times):
        for j, cell in enumerate(row):
            if not isinstance(cell, (int, float)) or not math.isfinite(cell) or cell < 0 or (i != j and cell <= 0):
                raise ValueError("Missing/unreachable road travel cost")
    def cost(seq):
        return sum(times[a][b] for a, b in zip(seq, seq[1:]))
    original = tuple(range(n))
    best = min(((0,) + tail for tail in permutations(range(1, n))),
               key=lambda seq: (cost(seq), seq))
    return best, cost(original), cost(best)


def _local_root():
    raw = os.getenv("VALHALLA_URL", "").strip().rstrip("/")
    # Only loopback services are allowed, aligned with existing v1.x endpoint.
    from urllib.parse import urlsplit
    parsed = urlsplit(raw)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or not parsed.port:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    return raw[:-6] if raw.endswith("/route") else raw


def _get_matrix(places, mode, root):
    positions = [{"lat": p["lat"], "lon": p["lng"]} for p in places]
    payload = {"sources": positions, "targets": positions, "costing": mode,
               "units": "kilometers"}
    req = Request(root + "/sources_to_targets",
                  data=json.dumps(payload).encode("utf8"), method="POST",
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=18) as resp:
        raw = resp.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Oversized matrix")
    rows = json.loads(raw).get("sources_to_targets")
    n = len(places)
    if not isinstance(rows, list) or len(rows) != n:
        raise ValueError("Missing matrix")
    times = []
    for row in rows:
        if not isinstance(row, list) or len(row) != n:
            raise ValueError("Invalid matrix row")
        times.append([cell.get("time") if isinstance(cell, dict) else None for cell in row])
    return times


def plan_verified_route(place_ids, mode="pedestrian", optimize=False):
    if mode not in ("pedestrian", "bicycle", "auto"):
        raise ValueError("Invalid travel mode")
    if not 2 <= len(place_ids) <= 6 or any(type(i) is not int or i <= 0 for i in place_ids):
        raise ValueError("Select 2–6 valid POI IDs")
    if len(set(place_ids)) != len(place_ids):
        raise ValueError("Duplicate POI ID")
    candidates = {p["id"]: p for p in fetch_candidates()}
    if any(i not in candidates for i in place_ids):
        raise LookupError("POI ID not found in current database")
    places = [candidates[i] for i in place_ids]
    root = _local_root()
    if not root:
        return {"status": "unavailable", "message": "请先配置本机 VALHALLA_URL；保留直线预览"}
    original_seconds = optimized_seconds = None
    if optimize and len(places) >= 3:
        try:
            matrix = _get_matrix(places, mode, root)
            order, original_seconds, optimized_seconds = optimize_fixed_first(matrix)
            places = [places[i] for i in order]
        except Exception:
            return {"status": "unavailable", "message": "道路时间矩阵不可用或不可达；未更改原路线"}
    route = valhalla_route(places, mode=mode, endpoint=root)
    if route.get("status") != "verified_by_routing_service":
        return {"status": "unavailable", "message": "道路服务未返回有效路线；保留直线预览"}
    route["ordered_place_ids"] = [p["id"] for p in places]
    route["optimized"] = original_seconds is not None
    if original_seconds is not None:
        route["original_matrix_minutes"] = round(original_seconds / 60, 1)
        route["optimized_matrix_minutes"] = round(optimized_seconds / 60, 1)
        route["matrix_minutes_saved_estimate"] = round(max(0, original_seconds - optimized_seconds) / 60, 1)
    route["limitations"] = "道路时间为Valhalla路网估算，非实时导航；矩阵时间与路线分段估算可能不同"
    return route
