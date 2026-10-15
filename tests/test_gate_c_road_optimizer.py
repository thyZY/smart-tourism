"""Gate C road matrix optimization and strict route API contract."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.ai import itinerary_routes
from app.ai.road_optimizer import optimize_fixed_first, plan_verified_route


class GateCRoutingTests(unittest.TestCase):
    def test_matrix_fixed_first_and_asymmetry(self):
        order, before, after = optimize_fixed_first([
            [0, 100, 10], [40, 0, 100], [30, 10, 0]])
        self.assertEqual(order, (0, 2, 1))
        self.assertEqual(before, 200)
        self.assertEqual(after, 20)

    def test_invalid_matrix_rejected(self):
        for matrix in ([[0, 0], [2, 0]], [[0, None], [2, 0]],
                       [[0, 1], [2]], [[0, float("nan")], [1, 0]]):
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                optimize_fixed_first(matrix)

    def test_only_real_database_ids_and_local_provider(self):
        pois = [{"id": i, "name": str(i), "category": "文化",
                 "address": "", "lng": 118.7 + i/1000, "lat": 32.01}
                for i in (1, 2, 3)]
        with patch("app.ai.road_optimizer.fetch_candidates", return_value=pois):
            with patch.dict("os.environ", {"VALHALLA_URL": "https://not-allowed.example"}):
                result = plan_verified_route([1, 2], "pedestrian")
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("geojson", result)
            with self.assertRaises(LookupError):
                plan_verified_route([1, 999])
            with self.assertRaises(ValueError):
                plan_verified_route([1, 1])

    def test_verified_geometry_and_optimized_order(self):
        pois = [{"id": i, "name": str(i), "category": "文化",
                 "address": "", "lng": 118.7 + i/1000, "lat": 32.01}
                for i in (1, 2, 3)]
        road = {"status": "verified_by_routing_service", "distance_km": 4.3,
                "duration_minutes": 8.0,
                "geojson": {"type": "FeatureCollection", "features": [
                    {"type": "Feature", "geometry": {"type": "LineString",
                    "coordinates": [[118.7, 32.01], [118.8, 32.01]]},
                    "properties": {}}]}}
        with patch("app.ai.road_optimizer.fetch_candidates", return_value=pois), \
             patch("app.ai.road_optimizer.valhalla_root", return_value="http://127.0.0.1:8002"), \
             patch("app.ai.road_optimizer._get_matrix", return_value=[
                 [0, 100, 10], [40, 0, 100], [30, 10, 0]]), \
             patch("app.ai.road_optimizer.valhalla_route", return_value=road):
            result = plan_verified_route([1, 2, 3], "bicycle", optimize=True)
        self.assertEqual(result["ordered_place_ids"], [1, 3, 2])
        self.assertTrue(result["optimized"])
        self.assertEqual(result["matrix_minutes_saved_estimate"], 3.0)

    def test_endpoint_validation(self):
        app = FastAPI()
        app.include_router(itinerary_routes.router)
        client = TestClient(app)
        self.assertEqual(client.post("/api/ai/itinerary/road", json={
            "place_ids": [1, 1], "travel_mode": "pedestrian"}).status_code, 422)
        self.assertEqual(client.post("/api/ai/itinerary/road", json={
            "place_ids": [1, 2], "travel_mode": "flight"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
