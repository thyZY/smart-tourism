"""Verified POIs and optional real Valhalla routing for AI plans.

The model never creates a POI, coordinate, walking time or street geometry.
Only PostgreSQL results and a successful Valhalla response can provide these.
"""
import json
import math
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def fetch_candidates(connection_factory, limit=200):
    connection = connection_factory()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT id, name, category, address, ST_X(geom), ST_Y(geom)
               FROM places WHERE geom IS NOT NULL ORDER BY id LIMIT %s""",
            (limit,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    result = []
    for id_, name, category, address, lng, lat in rows:
        if not (isinstance(lng, (float, int)) and isinstance(lat, (float, int))):
            continue
        if not (math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180
                and -90 <= lat <= 90):
            continue
        result.append({
            "id": int(id_), "name": str(name), "category": category or "",
            "address": address or "", "lng": float(lng), "lat": float(lat)
        })
    return result


def decode_polyline6(encoded):
    """Decode Valhalla polyline6 to GeoJSON [longitude, latitude]."""
    coords = []
    index = latitude = longitude = 0
    while index < len(encoded):
        values = []
        for _ in range(2):
            shift = result = 0
            while True:
                if index >= len(encoded):
                    raise ValueError("Truncated Valhalla polyline")
                byte = ord(encoded[index]) - 63
                index += 1
                if byte < 0 or byte > 63 or shift > 36:
                    raise ValueError("Invalid Valhalla polyline")
                result |= (byte & 0x1F) << shift
                shift += 5
                if not byte & 0x20:
                    break
            values.append(~(result >> 1) if result & 1 else result >> 1)
        latitude += values[0]
        longitude += values[1]
        lng, lat = longitude / 1e6, latitude / 1e6
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise ValueError("Invalid Valhalla coordinate")
        coords.append([lng, lat])
        if len(coords) > 250000:
            raise ValueError("Valhalla geometry too large")
    return coords


def valhalla_route(places, mode="pedestrian", endpoint=None):
    """Returns an actual road route, or an explicit unavailable status.

    A failed or disabled router NEVER emits a straight-line 'road route'.
    """
    endpoint = endpoint or os.getenv("VALHALLA_URL", "").strip()
    if len(places) < 2:
        return {"status": "unavailable", "message": "至少选择两个景点"}
    if not endpoint:
        return {"status": "unavailable", "message": "尚未配置VALHALLA_URL；仅显示直线预览"}
    if mode not in ("pedestrian", "bicycle", "auto"):
        raise ValueError("Unsupported Valhalla costing")
    if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
        return {"status": "unavailable", "message": "仅允许使用本机Valhalla服务"}
    url = endpoint.rstrip("/")
    if not url.endswith("/route"):
        url += "/route"
    req_data = {
        "locations": [{"lat": p["lat"], "lon": p["lng"]} for p in places],
        "costing": mode, "units": "kilometers"
    }
    request = Request(url, data=json.dumps(req_data).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=18) as response:
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("Route response too large")
        trip = json.loads(raw).get("trip", {})
        legs = trip.get("legs") or []
        if len(legs) != len(places) - 1:
            raise ValueError("Missing Valhalla route legs")
        coords = []
        for leg in legs:
            segment = decode_polyline6(leg["shape"])
            if len(segment) < 2:
                raise ValueError("Invalid route segment")
            coords.extend(segment if not coords else segment[1:])
        summary = trip.get("summary", {})
        length = float(summary["length"])
        seconds = float(summary["time"])
        if not (0 <= length <= 5000 and 0 <= seconds <= 864000):
            raise ValueError("Invalid route metrics")
        return {
            "status": "verified_by_routing_service",
            "provider": "Valhalla",
            "mode": mode,
            "distance_km": round(length, 3),
            "duration_minutes": round(seconds / 60, 1),
            "geojson": {"type": "FeatureCollection", "features": [{
                "type": "Feature", "properties": {"source": "Valhalla", "mode": mode},
                "geometry": {"type": "LineString", "coordinates": coords}
            }]}
        }
    except (HTTPError, URLError, OSError, TimeoutError, ValueError,
            KeyError, TypeError, json.JSONDecodeError):
        return {"status": "unavailable", "message": "道路服务不可用或数据格式错误；仅显示直线预览"}
