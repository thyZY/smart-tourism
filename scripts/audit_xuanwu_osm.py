#!/usr/bin/env python3
"""Audit (NOT approve) Xuanwu Lake entrance candidates against live OSM.

Usage:
  python scripts/audit_xuanwu_osm.py --osm-api  # use native OSM map JSON; bypass Overpass
  python scripts/audit_xuanwu_osm.py --osm-api-urls-only # browser links
  python scripts/audit_xuanwu_osm.py --online   # legacy Overpass query
  python scripts/audit_xuanwu_osm.py --osm-json-dir path/to/snapshots

No API key, no PostGIS writes, no reviewed status. Generated audit files are
local-only and must be manually inspected against actual public walkways.
OSM/Overpass data is © OpenStreetMap contributors, ODbL.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "entrance_evidence" / "xuanwu_lake_20261010.json"
OUT = ROOT / "data" / "entrance_evidence" / "xuanwu_lake_osm_audit_local.json"
OSM_ENDPOINT = "https://overpass-api.de/api/interpreter"
OSM_API_MAP = "https://api.openstreetmap.org/api/0.6/map.json"
A = 6378245.0
EE = 0.00669342162296594323
PATH_KINDS = frozenset(("footway", "pedestrian", "path", "steps", "living_street"))
GATE_BARRIERS = frozenset((
    "gate", "kissing_gate", "stile", "turnstile", "swing_gate",
    "entrance", "sally_port",
))
BANNED_ACCESS = frozenset(("no", "private"))


def _transform_lat(x, y):
    t = -100 + 2*x + 3*y + .2*y*y + .1*x*y + .2*math.sqrt(abs(x))
    t += (20*math.sin(6*x*math.pi)+20*math.sin(2*x*math.pi))*2/3
    t += (20*math.sin(y*math.pi)+40*math.sin(y/3*math.pi))*2/3
    t += (160*math.sin(y/12*math.pi)+320*math.sin(y*math.pi/30))*2/3
    return t


def _transform_lon(x, y):
    t = 300 + x + 2*y + .1*x*x + .1*x*y + .1*math.sqrt(abs(x))
    t += (20*math.sin(6*x*math.pi)+20*math.sin(2*x*math.pi))*2/3
    t += (20*math.sin(x*math.pi)+40*math.sin(x/3*math.pi))*2/3
    t += (150*math.sin(x/12*math.pi)+300*math.sin(x/30*math.pi))*2/3
    return t


def wgs84_to_gcj02(lng, lat):
    """Commonly used deterministic local GCJ-02 conversion approximation.

    It does not establish that a map marker represents a real, open gate.
    Outside mainland China, do not apply the transform.
    """
    if not (72.004 <= lng <= 137.8347 and .8293 <= lat <= 55.8271):
        raise ValueError("GCJ-02 conversion only supported within mainland China")
    x, y = lng - 105.0, lat - 35.0
    rad = math.radians(lat)
    magic = 1.0 - EE*math.sin(rad)**2
    root = math.sqrt(magic)
    delta_lat = _transform_lat(x, y)*180.0 / (A*(1-EE)/(magic*root)*math.pi)
    delta_lng = _transform_lon(x, y)*180.0 / (A/root*math.cos(rad)*math.pi)
    return lng + delta_lng, lat + delta_lat


def gcj02_to_wgs84(lng, lat):
    if type(lng) not in (int, float) or type(lat) not in (int, float):
        raise ValueError("Coordinates must be numeric")
    if not math.isfinite(lng) or not math.isfinite(lat):
        raise ValueError("Coordinates must be finite")
    x, y = float(lng), float(lat)
    for _ in range(15):
        fx, fy = wgs84_to_gcj02(x, y)
        dx, dy = lng-fx, lat-fy
        x += dx
        y += dy
        if max(abs(dx), abs(dy)) < 1e-11:
            break
    return x, y


def distance_m(a, b):
    lng1, lat1, lng2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dy, dx = lat2-lat1, lng2-lng1
    h = math.sin(dy/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dx/2)**2
    return 12742000*math.asin(min(1.0, math.sqrt(h)))


def build_query(lng, lat, radius=180):
    if not 50 <= radius <= 350:
        raise ValueError("Allowed OSM search radius is 50–350 metres")
    location = f"around:{int(radius)},{lat:.8f},{lng:.8f}"
    # Fetch tagged entrance/barrier nodes and nearby pedestrian ways, then
    # their constituent nodes. Inclusion in a way is a connectivity *hint*,
    # not proof of access through a wall or opening hours.
    return (
        "[out:json][timeout:25];("
        f'node({location})["entrance"];'
        f'node({location})["barrier"~"^(gate|kissing_gate|stile|turnstile|swing_gate)$"];'
        f'way({location})["highway"~"^(footway|pedestrian|path|steps|living_street)$"];'
        ");(._;>;);out body;"
    )


def fetch_overpass(query, endpoint=OSM_ENDPOINT, timeout=45):
    if not endpoint.startswith("https://"):
        raise ValueError("Overpass endpoint must be HTTPS")
    data = urlencode({"data": query}).encode("utf-8")
    req = Request(endpoint, data=data, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "SmartTourism-Research-Entrance-Audit/0.1 (manual spatial review only)",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = response.read(4_000_001)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Overpass unavailable: {exc}") from exc
    if len(payload) > 4_000_000:
        raise ValueError("OSM result too large; reduce search radius")
    result = json.loads(payload)
    if not isinstance(result, dict) or not isinstance(result.get("elements"), list):
        raise ValueError("Overpass did not return an OSM JSON element list")
    return result


def osm_bbox_url(lng, lat, radius=180):
    """Build a *small* bbox for the native OSM v0.6 JSON map API.

    Unlike Overpass, /api/0.6/map.json returns nearby map objects without
    executing resource-intensive Overpass QL. Keep this to two local
    research requests, not a bulk download. Bbox covers a radius-sized circle.
    """
    if not 50 <= radius <= 350:
        raise ValueError("Allowed OSM search radius is 50–350 metres")
    if not (-180 <= lng <= 180 and -80 <= lat <= 80):
        raise ValueError("Invalid map centre")
    dy = radius / 111_320.0
    dx = radius / (111_320.0 * math.cos(math.radians(lat)))
    bbox = f"{lng-dx:.8f},{lat-dy:.8f},{lng+dx:.8f},{lat+dy:.8f}"
    return OSM_API_MAP + "?bbox=" + bbox


def fetch_osm_map(lng, lat, radius=180, timeout=45):
    """Read source OSM nodes/ways as JSON; never calls an editing endpoint."""
    url = osm_bbox_url(lng, lat, radius)
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "SmartTourism-Research-Entrance-Audit/0.1 (two small read-only bbox requests)",
    })
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = response.read(8_000_001)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"OSM map API unavailable: {exc}") from exc
    if len(payload) > 8_000_000:
        raise ValueError("OSM map response too large; reduce --radius-m")
    try:
        result = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("OSM API did not return valid JSON") from exc
    if not isinstance(result, dict) or not isinstance(result.get("elements"), list):
        raise ValueError("OSM API did not return JSON with elements list")
    return result


def _walkable(tags):
    return (
        tags.get("highway") in PATH_KINDS
        and tags.get("foot") not in BANNED_ACCESS
        and tags.get("access") not in BANNED_ACCESS
    )


def _explicit_gate(tags):
    return (
        tags.get("barrier") in GATE_BARRIERS
        or tags.get("entrance") not in (None, "", "no")
    )


def _segment_distance_m(point, start, end):
    """Local planar projection is accurate enough to rank <=350 m segments.

    Returns distance to the full line segment and its closest WGS84 point,
    NOT merely the distance to the closest constituent OSM node.
    """
    metres_per_lat = 111_320.0
    metres_per_lon = metres_per_lat * math.cos(math.radians(point[1]))
    ax = (start[0] - point[0]) * metres_per_lon
    ay = (start[1] - point[1]) * metres_per_lat
    bx = (end[0] - point[0]) * metres_per_lon
    by = (end[1] - point[1]) * metres_per_lat
    denom = (bx - ax) ** 2 + (by - ay) ** 2
    t = max(0.0, min(1.0, -(ax * (bx - ax) + ay * (by - ay)) / denom)) if denom else 0.0
    x = ax + t * (bx - ax)
    y = ay + t * (by - ay)
    return math.hypot(x, y), (start[0] + t * (end[0] - start[0]),
                              start[1] + t * (end[1] - start[1]))


def _nearest_walkable_segments(point, segments, limit=5):
    nearby = []
    for segment in segments:
        distance, projected = _segment_distance_m(
            point, segment["start"], segment["end"])
        nearby.append({
            "osm_way_id": segment["osm_way_id"],
            "osm_way_url": f"https://www.openstreetmap.org/way/{segment['osm_way_id']}",
            "segment_start_node_id": segment["start_id"],
            "segment_end_node_id": segment["end_id"],
            "distance_m": round(distance, 1),
            "closest_wgs84_point": {"lng": round(projected[0], 8),
                                    "lat": round(projected[1], 8)},
        })
    return sorted(nearby, key=lambda x: (
        x["distance_m"], x["osm_way_id"], x["segment_start_node_id"]))[:limit]


def inspect_osm(payload, lng, lat, radius=180):
    """Rank OSM gate nodes with actual footpath-node-membership evidence."""
    nodes = {}
    ways = []
    for entry in payload.get("elements", []):
        if entry.get("type") == "node" and type(entry.get("id")) is int:
            if (type(entry.get("lon")) in (float, int)
                and type(entry.get("lat")) in (float, int)
                and math.isfinite(entry["lon"]) and math.isfinite(entry["lat"])):
                nodes[entry["id"]] = entry
        elif entry.get("type") == "way" and _walkable(entry.get("tags") or {}):
            ways.append(entry)
    footways_at_node = {}
    node_way_memberships = {}
    for entry in payload.get("elements", []):
        if entry.get("type") != "way":
            continue
        tags = entry.get("tags") or {}
        if not tags.get("highway"):
            continue
        for nid in entry.get("nodes") or []:
            node_way_memberships.setdefault(nid, []).append({
                "osm_way_id": entry["id"],
                "highway": tags.get("highway"),
                "foot": tags.get("foot"),
                "access": tags.get("access"),
            })
    pedestrian_nodes = []
    walkable_segments = []
    for way in ways:
        ids = way.get("nodes") or []
        for a_id, b_id in zip(ids, ids[1:]):
            if a_id in nodes and b_id in nodes:
                a, b = nodes[a_id], nodes[b_id]
                walkable_segments.append({
                    "osm_way_id": way["id"], "start_id": a_id, "end_id": b_id,
                    "start": (a["lon"], a["lat"]), "end": (b["lon"], b["lat"]),
                })
        for node_id in ids:
            footways_at_node.setdefault(node_id, []).append(way["id"])
            if node_id in nodes:
                n = nodes[node_id]
                pedestrian_nodes.append((n["lon"], n["lat"]))
    candidates = []
    for node in nodes.values():
        tags = node.get("tags") or {}
        if not _explicit_gate(tags):
            continue
        point = (node["lon"], node["lat"])
        metres = distance_m((lng, lat), point)
        if metres > radius:
            continue
        direct_ways = sorted(set(footways_at_node.get(node["id"], [])))
        nearest_segments = _nearest_walkable_segments(point, walkable_segments)
        nearest_way_node_m = min(
            (distance_m(point, xy) for xy in pedestrian_nodes), default=None)
        blocked = (
            tags.get("foot") in BANNED_ACCESS
            or tags.get("access") in BANNED_ACCESS
        )
        candidate = {
            "osm_node_id": node["id"],
            "osm_url": f"https://www.openstreetmap.org/node/{node['id']}",
            "wgs84": {"lng": round(node["lon"], 8), "lat": round(node["lat"], 8)},
            "distance_to_converted_map_marker_m": round(metres, 1),
            "node_tags": {k: v for k, v in tags.items() if k in (
                "name", "name:zh", "entrance", "barrier", "access", "foot",
                "wheelchair", "opening_hours", "operator", "ref",
                "bicycle", "motor_vehicle", "vehicle")},
            "highway_way_memberships": node_way_memberships.get(node["id"], [])[:15],
            "possible_other_attraction_exit": (
                bool(tags.get("ref") and "鸡鸣寺" in str(tags["ref"]))
            ),
            "pedestrian_way_membership_ids": direct_ways[:10],
            "is_member_of_walkable_osm_way": bool(direct_ways),
            "nearest_walkable_way_node_m": (
                round(nearest_way_node_m, 1)
                if nearest_way_node_m is not None else None),
            "nearest_walkable_way_segment_m": (
                nearest_segments[0]["distance_m"] if nearest_segments else None
            ),
            "nearest_walkable_way_segment_ids": (
                [nearest_segments[0]["osm_way_id"]] if nearest_segments else []
            ),
            "nearby_walkable_way_segments": nearest_segments,
            "tagged_pedestrian_access_restricted": blocked,
            "status": "candidate_requires_manual_review",
            "not_automatically_approved": True,
        }
        candidates.append(candidate)
    candidates.sort(key=lambda c: (
        c["possible_other_attraction_exit"],
        c["tagged_pedestrian_access_restricted"],
        not c["is_member_of_walkable_osm_way"],
        c["distance_to_converted_map_marker_m"],
        c["osm_node_id"],
    ))
    return {
        "candidate_count": len(candidates),
        "walkable_way_count": len(ways),
        "walkable_way_segment_count": len(walkable_segments),
        "nearest_walkable_segments_to_converted_marker": _nearest_walkable_segments(
            (lng, lat), walkable_segments),
        "gate_nodes": candidates[:30],
        "review_warning": (
            "An OSM gate node sharing a walkable way is not independent proof "
            "that the park entrance is open or that a route can cross it. "
            "OSM 'ref' or barrier tags may describe another attraction, "
            "such as the Jiming Temple exit. Check labels, wall passages, "
            "walkway connectivity and real access before any approval."
        ),
    }


def audit(evidence, snapshots=None, online=False, radius=180, endpoint=OSM_ENDPOINT,
          osm_api=False, raw_snapshot_dir=None):
    if not online and snapshots is None and not osm_api:
        raise ValueError("Specify --online, --osm-api or --osm-json-dir; no implicit network access")
    result = {
        "status": "research_only_unreviewed",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset_id": evidence["dataset_id"],
        "osm_attribution": "© OpenStreetMap contributors (ODbL)",
        "osm_endpoint": endpoint if online else OSM_API_MAP if osm_api else "offline_json_snapshot",
        "radius_metres": radius,
        "entrances": [],
        "routing_activation": "none",
    }
    for candidate in evidence["candidates"]:
        raw = candidate["raw_platform_position"]
        if raw["provider"] != "amap" or "WGS84" not in raw["coordinate_system"]:
            raise ValueError("Source coordinates must explicitly declare Amap non-WGS84")
        lng, lat = gcj02_to_wgs84(raw["longitude"], raw["latitude"])
        marker = {"lng": round(lng, 8), "lat": round(lat, 8)}
        query = build_query(lng, lat, radius)
        if online:
            osm = fetch_overpass(query, endpoint)
        elif osm_api:
            osm = fetch_osm_map(lng, lat, radius)
        else:
            filename = Path(snapshots) / (candidate["candidate_id"] + ".json")
            osm = json.loads(filename.read_text(encoding="utf-8"))
        if raw_snapshot_dir is not None:
            folder = Path(raw_snapshot_dir)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (candidate["candidate_id"] + ".json")).write_text(
                json.dumps(osm, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        matched = inspect_osm(osm, lng, lat, radius)
        result["entrances"].append({
            "candidate_id": candidate["candidate_id"],
            "name": candidate["name"],
            "source_url": raw["source_url"],
            "converted_wgs84_marker_estimate": marker,
            "conversion_method": "iterative_inverse_gcj02_to_wgs84",
            "coordinate_status": "estimated_marker_not_approved_routable_access",
            "osm_query": query,
            "osm_result": matched,
        })
    return result


def save_geojson(report, output_path):
    features = []
    for entry in report["entrances"]:
        xy = entry["converted_wgs84_marker_estimate"]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [xy["lng"], xy["lat"]]},
            "properties": {
                "name": entry["name"],
                "kind": "converted_amap_marker_not_verified_entrance",
                "status": "draft", "candidate_id": entry["candidate_id"],
            },
        })
        for gate in entry["osm_result"]["gate_nodes"]:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [
                    gate["wgs84"]["lng"], gate["wgs84"]["lat"]]},
                "properties": {
                    "name": entry["name"], "kind": "osm_gate_candidate",
                    "status": "candidate_requires_manual_review",
                    "osm_url": gate["osm_url"],
                    "distance_m": gate["distance_to_converted_map_marker_m"],
                    "on_walkable_way": gate["is_member_of_walkable_osm_way"],
                    "access_restricted": gate["tagged_pedestrian_access_restricted"],
                },
            })
    output_path.write_text(json.dumps({
        "type": "FeatureCollection", "name": "unreviewed_xuanwu_gate_candidates",
        "features": features,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--online", action="store_true", help="Query live public OSM Overpass")
    group.add_argument("--osm-api", action="store_true",
                       help="Use two small OSM native map.json bbox downloads (no Overpass)")
    group.add_argument("--osm-api-urls-only", action="store_true",
                       help="Print native OSM map.json download URLs; no network access")
    group.add_argument("--queries-only", action="store_true",
                       help="Print Overpass Turbo queries without any network request")
    group.add_argument("--osm-json-dir", type=Path,
                       help="Local Overpass JSON snapshots named <candidate_id>.json")
    parser.add_argument("--radius-m", type=int, default=180)
    parser.add_argument("--endpoint", default=OSM_ENDPOINT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--save-osm-snapshots", action="store_true",
                        help="Save raw OSM JSON locally for independent topology review")
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        if args.queries_only or args.osm_api_urls_only:
            for candidate in evidence["candidates"]:
                raw = candidate["raw_platform_position"]
                lng, lat = gcj02_to_wgs84(raw["longitude"], raw["latitude"])
                print(f"=== {candidate['name']} ===")
                if args.osm_api_urls_only:
                    print(osm_bbox_url(lng, lat, args.radius_m))
                else:
                    print(build_query(lng, lat, args.radius_m))
            if args.osm_api_urls_only:
                print("Open each URL in a browser. Save JSON under the matching candidate ID.")
            else:
                print("Paste each query into https://overpass-turbo.eu/ and export JSON.")
            return 0
        raw_dir = (args.out.parent / "xuanwu_osm_raw_local"
                   if args.save_osm_snapshots else None)
        report = audit(evidence, args.osm_json_dir, args.online,
                       args.radius_m, args.endpoint, args.osm_api, raw_dir)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        geojson = args.out.with_suffix(".geojson")
        save_geojson(report, geojson)
        for item in report["entrances"]:
            print(f"{item['name']}: WGS84 estimate="
                  f"{item['converted_wgs84_marker_estimate']}, "
                  f"OSM gate candidates={item['osm_result']['candidate_count']}, "
                  f"walkable OSM ways={item['osm_result']['walkable_way_count']}")
        print(f"Review JSON: {args.out}\nReview GeoJSON: {geojson}")
        if raw_dir is not None:
            print(f"Raw OSM JSON snapshots (unreviewed): {raw_dir}")
        print("SAFETY: no DB writes, no reviewed entrances, no routing changes.")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Audit failed; no DB updates made: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
