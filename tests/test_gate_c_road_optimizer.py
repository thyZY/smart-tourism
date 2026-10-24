"""Gate C road matrix optimization and strict route API contract."""
import json
import sys
import unittest
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.ai import itinerary_routes
from app.ai.road_optimizer import (
    MATRIX_REQUEST_TIMEOUT_SECONDS,
    MatrixRoutingError,
    _get_matrix,
    optimize_fixed_first,
    plan_verified_route,
)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


class FakeOpener:
    def __init__(self, body=None, error=None):
        self.body = body
        self.error = error
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        if self.error is not None:
            raise self.error
        return FakeResponse(self.body)


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

    def test_get_matrix_parses_valid_valhalla_response(self):
        places = [
            {"id": 1, "lng": 118.7921, "lat": 32.0407},
            {"id": 2, "lng": 118.7877, "lat": 32.027},
            {"id": 3, "lng": 118.78, "lat": 32.02},
        ]
        matrix = [
            [{"time": 0, "distance": 0.0},
             {"time": 1344, "distance": 1.827},
             {"time": 5325, "distance": 6.808}],
            [{"time": 1317, "distance": 1.829},
             {"time": 0, "distance": 0.0},
             {"time": 6505, "distance": 8.396}],
            [{"time": 4786, "distance": 6.797},
             {"time": 5964, "distance": 8.385},
             {"time": 0, "distance": 0.0}],
        ]
        fake = FakeOpener(body=json.dumps({
            "sources_to_targets": matrix
        }).encode("utf-8"))

        with patch("app.ai.road_optimizer.request_opener", return_value=fake):
            result = _get_matrix(places, "pedestrian", "https://valhalla1.openstreetmap.de")

        self.assertEqual(result, [
            [0, 1344, 5325],
            [1317, 0, 6505],
            [4786, 5964, 0],
        ])
        self.assertEqual(fake.timeout, MATRIX_REQUEST_TIMEOUT_SECONDS)
        self.assertGreaterEqual(fake.timeout, 30)
        self.assertTrue(fake.request.full_url.endswith("/sources_to_targets"))
        sent = json.loads(fake.request.data.decode("utf-8"))
        self.assertEqual(sent["costing"], "pedestrian")
        self.assertEqual(len(sent["sources"]), 3)
        self.assertEqual(sent["sources"], sent["targets"])

    def test_get_matrix_rejects_unreachable_cell_with_clear_error(self):
        places = [
            {"id": 1, "lng": 118.7921, "lat": 32.0407},
            {"id": 2, "lng": 118.7877, "lat": 32.027},
        ]
        fake = FakeOpener(body=json.dumps({
            "sources_to_targets": [
                [{"time": 0, "distance": 0}, {"time": None, "distance": None}],
                [{"time": 100, "distance": 1}, {"time": 0, "distance": 0}],
            ]
        }).encode("utf-8"))

        with patch("app.ai.road_optimizer.request_opener", return_value=fake):
            with self.assertRaisesRegex(MatrixRoutingError, "不可达"):
                _get_matrix(places, "pedestrian", "https://valhalla1.openstreetmap.de")

    def test_get_matrix_reports_network_error(self):
        places = [
            {"id": 1, "lng": 118.7921, "lat": 32.0407},
            {"id": 2, "lng": 118.7877, "lat": 32.027},
        ]
        fake = FakeOpener(error=URLError("network offline"))

        with patch("app.ai.road_optimizer.request_opener", return_value=fake):
            with self.assertRaisesRegex(MatrixRoutingError, "网络连接失败"):
                _get_matrix(places, "pedestrian", "https://valhalla1.openstreetmap.de")

    def test_matrix_failure_is_actionable_and_does_not_claim_optimized(self):
        pois = [{"id": i, "name": str(i), "category": "文化",
                 "address": "", "lng": 118.7 + i/1000, "lat": 32.01}
                for i in (1, 2, 3)]
        with patch("app.ai.road_optimizer.fetch_candidates", return_value=pois), \
             patch("app.ai.road_optimizer.valhalla_root",
                   return_value="https://valhalla1.openstreetmap.de"), \
             patch("app.ai.road_optimizer._get_matrix",
                   side_effect=MatrixRoutingError("Valhalla 时间矩阵请求超时")):
            result = plan_verified_route([1, 2, 3], "pedestrian", optimize=True)

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("超时", result["message"])
        self.assertIn("未更改原路线", result["message"])
        self.assertNotIn("ordered_place_ids", result)
        self.assertNotIn("geojson", result)

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
