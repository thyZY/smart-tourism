"""Two-POI road routing via Valhalla (prototype; public demo is not production SLA).

Trust boundary: POI IDs always resolve to existing PostGIS WGS84 coordinates.
External routing does not receive credentials, user messages, or database connection info.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from .db import get_db_connection
from .access_points import apply_routing_access, routing_provenance

router = APIRouter(prefix="/api/routing", tags=["road-routing"])


class RoadRouteRequest(BaseModel):
    from_id: int = Field(ge=1)
    to_id: int = Field(ge=1)
    mode: Literal["pedestrian", "bicycle", "auto"] = "pedestrian"


def _decode_number(polyline, index):
    result = 0
    shift = 0
    while True:
        if index >= len(polyline) or shift > 35:
            raise ValueError("Incomplete or invalid encoded route shape")
        byte = ord(polyline[index]) - 63
        index += 1
        if byte < 0 or byte > 63:
            raise ValueError("Invalid encoded route character")
        result |= (byte & 0x1f) << shift
        if byte < 0x20:
            return ((result >> 1) ^ -(result & 1)), index
        shift += 5


def decode_polyline6(shape):
    """Valhalla coordinates encode lat-first with 6 decimal places; GeoJSON is lon-first."""
    if not isinstance(shape, str) or not shape:
        raise ValueError("Empty route geometry")
    coords = []
    lat = lon = index = 0
    while index < len(shape):
        dlat, index = _decode_number(shape, index)
        dlon, index = _decode_number(shape, index)
        lat += dlat
        lon += dlon
        if not -90000000 <= lat <= 90000000 or not -180000000 <= lon <= 180000000:
            raise ValueError("Invalid decoded coordinate")
        coords.append([lon / 1_000_000, lat / 1_000_000])
        if len(coords) > 100000:
            raise ValueError("Route geometry too large")
    if len(coords) < 2:
        raise ValueError("Route must contain at least two coordinates")
    return coords


def load_places(from_id, to_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, ST_X(geom), ST_Y(geom), "
                "to_jsonb(places)->'routing_access' "
                "FROM places WHERE id = ANY(%s)", ([from_id, to_id],)
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    return {
        row[0]: {
            "id": row[0], "name": row[1], "lon": row[2], "lat": row[3],
            "routing_access": row[4] if len(row) > 4 and isinstance(row[4], dict) else None,
        }
        for row in rows
    }


def request_valhalla(first, second, mode="pedestrian", *, opener=urlopen):
    if mode not in ("pedestrian", "bicycle", "auto"):
        raise ValueError("Unsupported routing mode")
    url = os.getenv("VALHALLA_ROUTE_URL", "https://valhalla1.openstreetmap.de/route")
    body = json.dumps({
        "locations": [
            {"lat": first["lat"], "lon": first["lon"]},
            {"lat": second["lat"], "lon": second["lon"]},
        ],
        "costing": mode,
        "units": "kilometers",
        "directions_type": "none",
    }).encode("utf-8")
    request = Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Client-Id": "smart-tourism-prototype"},
    )
    with opener(request, timeout=15) as response:
        return json.load(response)


def build_road_feature(first, second, response, mode="pedestrian"):
    trip = response.get("trip")
    if not isinstance(trip, dict):
        raise ValueError("Provider returned no trip")
    summary = trip.get("summary") or {}
    legs = trip.get("legs") or []
    length = summary.get("length")
    time = summary.get("time")
    if (not isinstance(length, (float, int)) or length <= 0
            or not isinstance(time, (float, int)) or time <= 0 or not legs):
        raise ValueError("Provider returned no valid route summary")
    coordinates = []
    for leg in legs:
        points = decode_polyline6(leg["shape"])
        coordinates.extend(points if not coordinates else points[1:])
    if len(coordinates) < 2:
        raise ValueError("Provider returned incomplete route")
    return {
        "type": "Feature",
        "properties": {
            "from_id": first["id"], "to_id": second["id"],
            "from_name": first["name"], "to_name": second["name"],
            "mode": mode,
            "distance_km": round(float(length), 3),
            "duration_minutes": round(float(time) / 60, 1),
            "provider": "valhalla_osm",
            "routing_points": [
                routing_provenance(p) if p.get("routing_point") else {
                    "id": p["id"], "name": p["name"],
                    "kind": "poi_coordinate_fallback", "mode": mode,
                    "lon": p["lon"], "lat": p["lat"],
                }
                for p in (first, second)
            ],
            "limitations": "距离和时间为OSM路网估算，不含实时交通与交通工具等待时间；无审核入口时沿用POI坐标，起终点可能吸附至道路。",
        },
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


@router.post("/route")
def route_between_places(body: RoadRouteRequest):
    if body.from_id == body.to_id:
        raise HTTPException(status_code=422, detail="请选两个不同的景点")
    places = load_places(body.from_id, body.to_id)
    if body.from_id not in places or body.to_id not in places:
        raise HTTPException(status_code=404, detail="数据库中找不到对应景点")
    first = apply_routing_access(places[body.from_id], body.mode)
    second = apply_routing_access(places[body.to_id], body.mode)
    try:
        response = request_valhalla(first, second, mode=body.mode)
        return build_road_feature(first, second, response, mode=body.mode)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="道路寻路服务暂不可用，请稍后重试；现有直线预览仍可使用") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="道路寻路服务未返回有效路线，请检查路网覆盖") from exc


class MultiStopRequest(BaseModel):
    place_ids: list[int] = Field(min_length=3, max_length=6)
    mode: Literal["pedestrian", "bicycle", "auto"] = "pedestrian"


@router.post("/itinerary")
def route_multistop_itinerary(body: MultiStopRequest):
    """Find minimal travel time over 3–6 selected POIs (first stop fixed).

    Two network calls to Valhalla: time matrix + multi-leg route geometry.
    On missing costs/route failures return a clear error; never fabricate roads.
    """
    if any(type(ident) is not int or ident <= 0 for ident in body.place_ids):
        raise HTTPException(status_code=422, detail="景点ID必须为正整数")
    if len(set(body.place_ids)) != len(body.place_ids):
        raise HTTPException(status_code=422, detail="路线中的景点不能重复")
    from .road_itinerary import plan_itinerary

    try:
        return plan_itinerary(body.place_ids, body.mode)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HTTPException(
            status_code=502,
            detail="道路时间矩阵或路线服务不可用，请稍后重试；保留原有直线预览",
        ) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="道路网络缺少部分路段或返回无效数据，无法生成可靠的多站路线",
        ) from exc


@router.get("/access-coverage")
def scenic_access_coverage():
    """Read-only inventory: which POIs have usable mode-specific access points?

    Safe before applying the optional migration: to_jsonb yields null.
    Does not mark a source as officially validated; review is manual.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, ST_X(geom), ST_Y(geom), "
                "to_jsonb(places)->'routing_access' "
                "FROM places ORDER BY id"
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    from .access_points import MODES

    reviewed_by_mode = {mode: 0 for mode in MODES}
    details = []
    for ident, name, longitude, latitude, access in rows:
        poi = {
            "id": ident, "name": name, "lon": longitude, "lat": latitude,
            "routing_access": access if isinstance(access, dict) else None,
        }
        modes = {}
        for mode in MODES:
            result = apply_routing_access(poi, mode)
            reviewed = result["routing_point"]["kind"] == "reviewed_access_point"
            reviewed_by_mode[mode] += int(reviewed)
            modes[mode] = "reviewed_access_point" if reviewed else "poi_coordinate_fallback"
        details.append({"id": ident, "name": name, "modes": modes})
    return {
        "total_places": len(rows),
        "reviewed_by_mode": reviewed_by_mode,
        "fallback_by_mode": {
            mode: len(rows) - reviewed_by_mode[mode] for mode in MODES
        },
        "places": details,
        "notice": "仅统计字段完整、通过坐标合理性检查并标记为人工审核的入口；不代表入口实时开放或官方保证",
    }
