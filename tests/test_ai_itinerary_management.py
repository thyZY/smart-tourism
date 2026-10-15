"""Offline regression coverage for grounded AI itinerary and snapshot restoration."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai import itinerary_routes
from app.ai.itinerary_planner import ItineraryPlanner
from app.ai.itinerary_geo_service import decode_polyline6, valhalla_route


SAMPLE = [
    {"id": 1, "name": "博物院", "category": "博物馆", "address": "A",
     "lng": 118.7, "lat": 32.01},
    {"id": 2, "name": "古城门", "category": "古迹遗址", "address": "B",
     "lng": 118.71, "lat": 32.02},
    {"id": 3, "name": "市民公园", "category": "城市公园", "address": "C",
     "lng": 118.72, "lat": 32.03}
]


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class ItineraryTests(unittest.TestCase):
    def test_fallback_no_key_never_invents_poi_or_road(self):
        with patch.dict(os.environ, {}, clear=True):
            result = ItineraryPlanner().generate(
                "南京", candidates=SAMPLE, max_stops=3)
        self.assertEqual(result["planning_method"], "local_rule_fallback")
        self.assertEqual({s["id"] for s in result["stops"]}, {1, 2, 3})
        self.assertEqual(result["route"]["status"], "unavailable")
        self.assertNotIn("distance_km", result["route"])
        self.assertTrue(all("reason" in s for s in result["stops"]))

    def test_fake_model_may_rank_ids_but_cannot_add_fiction(self):
        client = FakeClient({"place_ids": [9999, 2, 2, 1, 3]})
        with patch.dict(os.environ, {}, clear=True):
            result = ItineraryPlanner(client).generate(
                "南京", candidates=SAMPLE, max_stops=3)
        self.assertEqual([s["id"] for s in result["stops"]], [2, 1, 3])
        self.assertEqual(result["planning_method"], "deepseek_ranked_verified_ids")
        self.assertIn("system_prompt", client.calls[0])
        self.assertIn("user_prompt", client.calls[0])
        self.assertNotIn("messages", client.calls[0])

    def test_wrong_model_shape_or_unknown_ids_falls_back(self):
        for response in ({"place_ids": [999]}, {"place_ids": "hello"}, []):
            with self.subTest(response=response):
                with patch.dict(os.environ, {}, clear=True):
                    result = ItineraryPlanner(FakeClient(response)).generate(
                        "南京", candidates=SAMPLE)
                self.assertEqual(result["planning_method"], "local_rule_fallback")

    def test_valhalla_disabled_does_not_make_fake_road(self):
        with patch.dict(os.environ, {}, clear=True):
            result = valhalla_route(SAMPLE)
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("geojson", result)

    def test_decode_empty_and_truncated(self):
        self.assertEqual(decode_polyline6(""), [])
        with self.assertRaises(ValueError):
            decode_polyline6("~~~~")

    def test_http_missing_db_and_restore_validates_ids(self):
        app = FastAPI()
        app.include_router(itinerary_routes.router)
        client = TestClient(app)
        with patch.object(itinerary_routes, "fetch_candidates", return_value=SAMPLE):
            invalid = client.post("/api/ai/itinerary/restore", json={
                "place_ids": [1, 1]})
            self.assertEqual(invalid.status_code, 422)
            missing = client.post("/api/ai/itinerary/restore", json={
                "place_ids": [1, 900]})
            self.assertEqual(missing.status_code, 409)
            restored = client.post("/api/ai/itinerary/restore", json={
                "place_ids": [3, 1], "travel_mode": "pedestrian"})
            self.assertEqual(restored.status_code, 200)
            payload = restored.json()
            self.assertEqual([p["id"] for p in payload["stops"]], [3, 1])
            self.assertEqual(payload["route"]["status"], "unavailable")
            self.assertNotIn("distance_km", payload["route"])
            no_days = client.post("/api/ai/itinerary/generate", json={
                "location": "南京", "days": 3})
            self.assertEqual(no_days.status_code, 422)
            with patch.dict(os.environ, {}, clear=True):
                generated = client.post("/api/ai/itinerary/generate", json={
                    "location": "南京", "days": 1, "max_stops": 3})
            self.assertEqual(generated.status_code, 200)
            self.assertTrue(all(s["id"] in (1, 2, 3)
                                for s in generated.json()["stops"]))


if __name__ == "__main__":
    unittest.main()
