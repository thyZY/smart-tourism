"""Evidence-gated, mode-specific access points for large scenic POIs.

A reviewed record is a *maintainer-supplied* input, not an automatically
verified official entrance. This module does NOT geocode or fetch sources.
It rejects unsupported/unreviewed coordinates and transparently falls back
to the ordinary database POI marker.
"""
from datetime import date
from math import asin, cos, isfinite, radians, sin, sqrt
from urllib.parse import urlsplit

MODES = ("pedestrian", "bicycle", "auto")
MAX_CENTER_DISTANCE_KM = 10.0


def _distance_km(a, b):
    lng1, lat1 = map(radians, a)
    lng2, lat2 = map(radians, b)
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    return 12742.0 * asin(min(1.0, sqrt(
        sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    )))


def _valid_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme in ("https", "http") and bool(url.hostname) and
                url.username is None and url.password is None)
    except ValueError:
        return False


def _reviewed_point(record, mode, center):
    """Return vetted-shaped metadata or None, never repair invented positions."""
    if not isinstance(record, dict) or record.get("status") != "reviewed":
        return None
    longitude, latitude = record.get("lng"), record.get("lat")
    if (type(longitude) not in (float, int) or
            type(latitude) not in (float, int) or
            not isfinite(longitude) or not isfinite(latitude) or
            not -180 <= longitude <= 180 or not -90 <= latitude <= 90):
        return None
    if _distance_km(center, (longitude, latitude)) > MAX_CENTER_DISTANCE_KM:
        return None
    reviewed_on = record.get("reviewed_on")
    if not isinstance(reviewed_on, str):
        return None
    try:
        reviewed = date.fromisoformat(reviewed_on)
    except ValueError:
        return None
    if reviewed > date.today() or reviewed.year < 2000:
        return None
    source_url = record.get("source_url")
    if not _valid_url(source_url):
        return None
    name = record.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        return None
    return {
        "mode": mode, "kind": "reviewed_access_point",
        "name": name.strip(), "lon": float(longitude),
        "lat": float(latitude), "source_url": source_url,
        "reviewed_on": reviewed_on,
    }


def apply_routing_access(place, mode):
    """Return a copy with the selected navigation coordinate for one mode.

    Geometry used to show a POI on a map stays untouched elsewhere.
    No reviewed point => explicitly documented original-center fallback.
    """
    if mode not in MODES:
        raise ValueError("Unsupported access point travel mode")
    center = (place["lon"], place["lat"])
    if any(type(x) not in (float, int) or not isfinite(x) for x in center):
        raise ValueError("POI has invalid original coordinates")
    configured = place.get("routing_access") or {}
    item = _reviewed_point(configured.get(mode), mode, center) if isinstance(configured, dict) else None
    result = dict(place)
    if item:
        result["lon"], result["lat"] = item["lon"], item["lat"]
        result["routing_point"] = item
    else:
        result["routing_point"] = {
            "mode": mode, "kind": "poi_coordinate_fallback",
            "lon": float(center[0]), "lat": float(center[1]),
        }
    return result


def routing_provenance(place):
    point = place["routing_point"]
    return {
        "id": place["id"], "name": place["name"],
        "kind": point["kind"], "mode": point["mode"],
        "lon": point["lon"], "lat": point["lat"],
        **({"access_name": point["name"],
            "source_url": point["source_url"],
            "reviewed_on": point["reviewed_on"]}
           if point["kind"] == "reviewed_access_point" else {}),
    }
