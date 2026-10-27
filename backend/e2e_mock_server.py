"""FastAPI browser-test app using the isolated PostGIS fixture.

POI and statistics endpoints use the disposable PostGIS database. Only the
external Valhalla boundary used by the road endpoint is replaced, so CI tests
the real same-origin API, DB records, MapLibre data flow, and route contract
without depending on a public routing service.
"""
from app.main import app
from app.ai import road_optimizer


def fixture_matrix(places, mode, root):
    """Deterministic directed matrix with a known fixed-first optimum: 1,2,4,3."""
    place_ids = [place["id"] for place in places]
    low_cost_edges = {(1, 2), (2, 4), (4, 3)}
    return [
        [0 if source == target else (120 if (source, target) in low_cost_edges else 1000)
         for target in place_ids]
        for source in place_ids
    ]


def fixture_route(places, mode="pedestrian", endpoint=None):
    """Return a clearly identified test geometry in the normal route contract."""
    coordinates = []
    for start, end in zip(places, places[1:]):
        for step in range(8):
            ratio = step / 8
            coordinates.append([
                start["lng"] + (end["lng"] - start["lng"]) * ratio,
                start["lat"] + (end["lat"] - start["lat"]) * ratio,
            ])
    if places:
        coordinates.append([places[-1]["lng"], places[-1]["lat"]])

    legs = max(0, len(places) - 1)
    return {
        "status": "verified_by_routing_service",
        "provider": "Valhalla",
        "mode": mode,
        "distance_km": round(legs * 1.234, 3),
        "duration_minutes": round(legs * 12.5, 1),
        "geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"source": "CI Valhalla contract fixture", "mode": mode},
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }],
        },
    }


# Keep place loading bound to the real isolated PostGIS database. The route API
# is exercised end-to-end while its external matrix/route calls stay local.
road_optimizer.valhalla_root = lambda: "http://127.0.0.1:8011"
road_optimizer._get_matrix = fixture_matrix
road_optimizer.valhalla_route = fixture_route
