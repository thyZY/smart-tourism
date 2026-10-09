"""Grounded multi-stop road network itinerary tests without network or a live database."""
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.main import app
from backend.app.road_itinerary import (
    build_itinerary_response, load_itinerary_places, matrix_url, optimize_open_path,
    request_matrix, request_multileg_route, validate_matrix,
)
from backend.app.routing_routes import MultiStopRequest, route_multistop_itinerary


STOPS = [
    {"id": 1, "name": "博物院", "lon": 118.79, "lat": 32.04, "visit_duration": 90},
    {"id": 2, "name": "夫子庙", "lon": 118.80, "lat": 32.03, "visit_duration": 75},
    {"id": 3, "name": "总统府", "lon": 118.78, "lat": 32.05, "visit_duration": 60},
]
# Starting at 0: visiting 2 then 1 is faster than 1 then 2.
TIMES = [[0, 900, 180], [800, 0, 1100], [150, 120, 0]]
MATRIX = {"sources_to_targets": [
    [{"time": 0, "distance": 0}, {"time": 900, "distance": 6}, {"time": 180, "distance": 1}],
    [{"time": 800, "distance": 5}, {"time": 0, "distance": 0}, {"time": 1100, "distance": 7}],
    [{"time": 150, "distance": 1}, {"time": 120, "distance": 0.8}, {"time": 0, "distance": 0}],
]}
# Known valid Valhalla polyline6 fixture from existing backend tests.
SHAPE = "e~epoA|jfpOiDaK"
ROUTE = {"trip": {"legs": [
    {"summary": {"length": 1, "time": 180}, "shape": SHAPE},
    {"summary": {"length": 0.8, "time": 120}, "shape": SHAPE},
]}}


class MultiStopTests(unittest.TestCase):
    def test_registered(self):
        self.assertIn("/api/routing/itinerary", app.openapi()["paths"])

    def test_validation_and_fixed_first(self):
        order, original, better = optimize_open_path(TIMES)
        self.assertEqual(order, [0, 2, 1])
        self.assertEqual(original, 2000)
        self.assertEqual(better, 300)
        self.assertEqual(order[0], 0)
        for ids in ([1, 2], [1, 2, 3, 4, 5, 6, 7]):
            with self.assertRaises(ValidationError):
                MultiStopRequest(place_ids=ids)
        with self.assertRaises(ValidationError):
            MultiStopRequest(place_ids=[1, 2, 3], mode="transit")
        with self.assertRaises(HTTPException) as e:
            route_multistop_itinerary(MultiStopRequest(place_ids=[1, 1, 2]))
        self.assertEqual(e.exception.status_code, 422)

    def test_exact_solver_cannot_worsen_original_route(self):
        for n in (3, 4, 5, 6):
            times = [[0 if a == b else abs(a - b) * 83 + a * 2 + b for b in range(n)]
                     for a in range(n)]
            order, original, best = optimize_open_path(times)
            self.assertEqual(sorted(order), list(range(n)))
            self.assertLessEqual(best, original)

    def test_fetch_only_selected_ids_and_optional_duration(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (3, "总统府", 118.78, 32.05, "60"),
            (1, "博物院", 118.79, 32.04, "90"),
            (2, "夫子庙", 118.80, 32.03, None),
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with patch("backend.app.road_itinerary.get_db_connection", return_value=conn):
            result = load_itinerary_places([1, 2, 3])
        sql, params = cursor.execute.call_args.args
        self.assertIn("WHERE p.id = ANY(%s)", sql)
        self.assertEqual(params, ([1, 2, 3],))
        self.assertEqual([p["id"] for p in result], [1, 2, 3])
        self.assertIsNone(result[1]["visit_duration"])
        conn.close.assert_called_once()

    def test_partial_db_result_is_404(self):
        with patch("backend.app.road_itinerary.load_itinerary_places",
                   side_effect=LookupError("missing")):
            with self.assertRaises(HTTPException) as e:
                route_multistop_itinerary(MultiStopRequest(place_ids=[1, 2, 3]))
        self.assertEqual(e.exception.status_code, 404)

    def test_directional_costs_require_full_matrix(self):
        times, distance = validate_matrix(MATRIX, 3)
        self.assertEqual(times[1][0], 800)
        self.assertEqual(times[0][1], 900)
        self.assertEqual(distance[2][1], 0.8)
        with self.assertRaises(ValueError):
            validate_matrix({"sources_to_targets": [[{}]]}, 3)
        broken = {"sources_to_targets": [
            [{**cell} for cell in row] for row in MATRIX["sources_to_targets"]
        ]}
        broken["sources_to_targets"][0][2]["time"] = None
        with self.assertRaises(ValueError):
            validate_matrix(broken, 3)

    def test_multileg_geometry_and_missing_visit_time(self):
        result = build_itinerary_response(
            STOPS, [0, 2, 1], 2000, 300, ROUTE, "pedestrian"
        )
        self.assertEqual(result["optimized_order_ids"], [1, 3, 2])
        self.assertEqual(len(result["geometry"]["features"]), 2)
        self.assertEqual(result["geometry"]["features"][0]["properties"]["to_id"], 3)
        self.assertEqual(result["duration_minutes"], 5.0)
        self.assertEqual(result["distance_km"], 1.8)
        self.assertEqual(result["total_plan_minutes"], 230.0)
        self.assertGreater(result["travel_minutes_saved_estimate"], 0)

        missing = [dict(stop) for stop in STOPS]
        missing[1]["visit_duration"] = None
        result = build_itinerary_response(missing, [0, 2, 1], 2000, 300, ROUTE, "auto")
        self.assertIsNone(result["total_plan_minutes"])
        self.assertEqual(result["missing_visit_duration_count"], 1)

    def test_incomplete_multileg_route_refused(self):
        with self.assertRaises(ValueError):
            build_itinerary_response(STOPS, [0, 2, 1], 2000, 300,
                {"trip": {"legs": [ROUTE["trip"]["legs"][0]]}}, "auto")

    def test_provider_failure_is_502_no_straight_line_fabrication(self):
        with patch("backend.app.road_itinerary.plan_itinerary",
                   side_effect=ValueError("unreachable")):
            with self.assertRaises(HTTPException) as failure:
                route_multistop_itinerary(MultiStopRequest(place_ids=[1, 2, 3]))
        self.assertEqual(failure.exception.status_code, 502)

    def test_matrix_and_multileg_use_same_mode_and_selected_coords(self):
        from unittest.mock import patch as mock_patch
        calls = []
        class Resp:
            def __init__(self, result): self.result = result
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, *args): return __import__("json").dumps(self.result).encode()
        def opening(req, timeout):
            payload = __import__("json").loads(req.data)
            calls.append((req.full_url, payload["costing"], payload, timeout))
            return Resp(MATRIX if "sources_to_targets" in req.full_url else ROUTE)
        with mock_patch("backend.app.road_itinerary.getenv",
                        side_effect=lambda key, default=None: default):
            result_matrix = request_matrix(STOPS, "bicycle", opener=opening)
            result_route = request_multileg_route(STOPS, "bicycle", opener=opening)
        self.assertEqual(result_matrix, MATRIX)
        self.assertEqual(result_route, ROUTE)
        self.assertIn("/sources_to_targets", calls[0][0])
        self.assertIn("/route", calls[1][0])
        self.assertTrue(all(call[1] == "bicycle" for call in calls))
        self.assertEqual(calls[0][2]["sources"], calls[0][2]["targets"])
        self.assertEqual(calls[1][2]["locations"][0]["lat"], 32.04)


if __name__ == "__main__":
    unittest.main()
