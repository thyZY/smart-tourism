"""Offline contracts for three Valhalla transport profiles and API compatibility."""
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.routing_routes import (
    RoadRouteRequest, build_road_feature, request_valhalla, route_between_places,
)

FIRST = {"id": 1, "name": "南京博物院", "lat": 32.0407, "lon": 118.7921}
SECOND = {"id": 2, "name": "夫子庙", "lat": 32.0270, "lon": 118.7877}
ROUTE = {"trip": {
    "summary": {"length": 1.827, "time": 1344},
    "legs": [{"shape": "e~epoA|jfpOiDaK"}],
}}


class FakeResponse:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, *args):
        return json.dumps(ROUTE).encode("utf-8")


class MultiModalRoutingTests(unittest.TestCase):
    def test_legacy_request_still_defaults_to_walking(self):
        self.assertEqual(RoadRouteRequest(from_id=1, to_id=2).mode, "pedestrian")

    def test_three_modes_use_distinct_valhalla_costing(self):
        for mode in ("pedestrian", "bicycle", "auto"):
            with self.subTest(mode=mode):
                calls = []
                def fake_open(req, timeout):
                    calls.append((req, timeout))
                    return FakeResponse()
                response = request_valhalla(FIRST, SECOND, mode=mode, opener=fake_open)
                req, timeout = calls[0]
                params = json.loads(req.data)
                self.assertEqual(params["costing"], mode)
                self.assertEqual(params["units"], "kilometers")
                self.assertEqual(len(params["locations"]), 2)
                self.assertEqual(timeout, 15)
                feature = build_road_feature(FIRST, SECOND, response, mode=mode)
                self.assertEqual(feature["properties"]["mode"], mode)
                self.assertEqual(feature["geometry"]["type"], "LineString")
                self.assertEqual(feature["properties"]["distance_km"], 1.827)
                self.assertEqual(feature["properties"]["duration_minutes"], 22.4)

    def test_invalid_mode_rejected_before_provider(self):
        for mode in ("transit", "taxi", "motorcycle", "", "AUTO"):
            with self.subTest(mode=mode):
                with self.assertRaises(ValidationError):
                    RoadRouteRequest(from_id=1, to_id=2, mode=mode)
        with self.assertRaises(ValueError):
            request_valhalla(FIRST, SECOND, mode="transit", opener=lambda *_: None)

    def test_backend_forwards_mode_to_valhalla_and_response(self):
        for mode in ("pedestrian", "bicycle", "auto"):
            with self.subTest(mode=mode):
                with patch("backend.app.routing_routes.load_places",
                           return_value={1: FIRST, 2: SECOND}), \
                     patch("backend.app.routing_routes.request_valhalla",
                           return_value=ROUTE) as caller:
                    feature = route_between_places(
                        RoadRouteRequest(from_id=1, to_id=2, mode=mode)
                    )
                caller.assert_called_once_with(FIRST, SECOND, mode=mode)
                self.assertEqual(feature["properties"]["mode"], mode)

    def test_empty_provider_result_returns_502(self):
        with patch("backend.app.routing_routes.load_places",
                   return_value={1: FIRST, 2: SECOND}), \
             patch("backend.app.routing_routes.request_valhalla",
                   return_value={"trip": {"summary": {"length": 0, "time": 0}, "legs": []}}):
            with self.assertRaises(HTTPException) as failure:
                route_between_places(RoadRouteRequest(from_id=1, to_id=2, mode="bicycle"))
        self.assertEqual(failure.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
