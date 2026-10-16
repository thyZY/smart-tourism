"""Offline full-stack fixture for browser E2E.

This imports the real FastAPI application and patches only external boundaries:
PostGIS candidate loading and Valhalla routing. No DeepSeek key is used.
"""
from app.main import app
import app.ai.itinerary_routes as routes
import app.ai.itinerary_planner as planner

POIS = [
    {"id": 1, "name": "南京总统府", "category": "历史文化", "address": "南京市玄武区",
     "lng": 118.7969, "lat": 32.0480},
    {"id": 2, "name": "夫子庙", "category": "历史文化", "address": "南京市秦淮区",
     "lng": 118.7897, "lat": 32.0208},
    {"id": 3, "name": "中华门瓮城", "category": "古迹遗址", "address": "南京市秦淮区",
     "lng": 118.7838, "lat": 32.0112},
    {"id": 4, "name": "南京科举博物馆", "category": "博物馆", "address": "南京市秦淮区",
     "lng": 118.7880, "lat": 32.0212},
]


def fake_candidates():
    return list(POIS)


def fake_route(places, mode="pedestrian"):
    # Deliberately shaped like the real verified Valhalla response.
    return {
        "status": "verified_by_routing_service",
        "provider": "e2e-fixture",
        "mode": mode,
        "distance_km": round(max(0, len(places) - 1) * 1.234, 3),
        "duration_minutes": round(max(0, len(places) - 1) * 12.5, 1),
        "geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p["lng"], p["lat"]] for p in places],
                },
            }],
        },
    }


routes.fetch_candidates = fake_candidates
routes.valhalla_route = fake_route
planner.valhalla_route = fake_route
