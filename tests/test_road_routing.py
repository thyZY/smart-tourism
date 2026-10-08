"""Offline contract tests: no provider key, network or PostgreSQL required."""
import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from fastapi import HTTPException

from backend.app.main import app
from backend.app.routing_routes import (
    RoadRouteRequest, build_road_feature, decode_polyline6,
    load_places, request_valhalla, route_between_places,
)


FROM = {"id": 1, "name": "南京博物院", "lat": 32.0407, "lon": 118.7921}
TO = {"id": 2, "name": "南京总统府", "lat": 32.0444, "lon": 118.7969}
SHAPE = "e~epoA|jfpOiDaK"
VALID = {"trip": {"summary": {"length": 0.908, "time": 678},
                  "legs": [{"shape": SHAPE}]}}


class MockHTTPResponse:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, *args):
        return json.dumps(VALID).encode("utf-8")


class RoadRoutingTests(unittest.TestCase):
    def test_endpoint_registered(self):
        self.assertIn("/api/routing/route", {route.path for route in app.routes})

    def test_valhalla_polyline6_lon_lat_order(self):
        coords = decode_polyline6(SHAPE)
        self.assertEqual(len(coords), 2)
        self.assertAlmostEqual(coords[0][0], -8.670911)
        self.assertAlmostEqual(coords[0][1], 42.225139)
        self.assertAlmostEqual(coords[1][0], -8.670718)
        self.assertAlmostEqual(coords[1][1], 42.225224)

    def test_rejects_invalid_shape(self):
        for shape in ("", "~", "abc"):
            with self.assertRaises(ValueError):
                decode_polyline6(shape)

    def test_uses_only_database_place_coordinates(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (1, "南京博物院", 118.7921, 32.0407),
            (2, "南京总统府", 118.7969, 32.0444),
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        with patch("backend.app.routing_routes.get_db_connection", return_value=conn):
            result = load_places(1, 2)
        sql, values = cursor.execute.call_args.args
        self.assertEqual(values, ([1, 2],))
        self.assertIn("WHERE id = ANY(%s)", sql)
        self.assertEqual(result[1]["lat"], 32.0407)
        conn.close.assert_called_once()

    def test_valhalla_request_is_pedestrian_and_has_coordinates(self):
        calls = []
        def mock_opener(req, timeout):
            calls.append((req, timeout))
            return MockHTTPResponse()
        response = request_valhalla(FROM, TO, opener=mock_opener)
        self.assertEqual(response, VALID)
        request, timeout = calls[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["costing"], "pedestrian")
        self.assertEqual(body["locations"][0], {"lat": 32.0407, "lon": 118.7921})
        self.assertEqual(timeout, 15)

    def test_response_is_geojson_line_with_measured_summary(self):
        result = build_road_feature(FROM, TO, VALID)
        self.assertEqual(result["type"], "Feature")
        self.assertEqual(result["geometry"]["type"], "LineString")
        self.assertEqual(result["properties"]["distance_km"], 0.908)
        self.assertEqual(result["properties"]["duration_minutes"], 11.3)

    def test_no_0km_when_provider_returns_invalid_summary(self):
        with self.assertRaises(ValueError):
            build_road_feature(FROM, TO, {"trip": {"summary": {"length": 0, "time": 0},
                                                         "legs": [{"shape": SHAPE}]}})

    def test_invalid_or_unknown_poIs(self):
        with self.assertRaises(HTTPException) as same:
            route_between_places(RoadRouteRequest(from_id=1, to_id=1))
        self.assertEqual(same.exception.status_code, 422)
        with patch("backend.app.routing_routes.load_places", return_value={1: FROM}):
            with self.assertRaises(HTTPException) as missing:
                route_between_places(RoadRouteRequest(from_id=1, to_id=2))
        self.assertEqual(missing.exception.status_code, 404)

    def test_provider_failure_uses_explicit_bad_gateway(self):
        with patch("backend.app.routing_routes.load_places", return_value={1: FROM, 2: TO}), \
             patch("backend.app.routing_routes.request_valhalla", side_effect=URLError("offline")):
            with self.assertRaises(HTTPException) as failed:
                route_between_places(RoadRouteRequest(from_id=1, to_id=2))
        self.assertEqual(failed.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
