"""Source-gated scenic access routing tests: synthetic coordinates, no network."""
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.access_points import apply_routing_access, routing_provenance
from backend.app.road_itinerary import plan_itinerary
from backend.app.routing_routes import RoadRouteRequest, route_between_places


CENTER = {"id": 1, "name": "测试景区", "lon": 118.7900, "lat": 32.0400}
SECOND = {"id": 2, "name": "测试博物馆", "lon": 118.8000, "lat": 32.0450}
THIRD = {"id": 3, "name": "测试公园", "lon": 118.8100, "lat": 32.0500}
# These are fabricated TEST points, not claims about real scenic entrances.
PED_POINT = {"status": "reviewed", "name": "示例步行入口",
             "lng": 118.791, "lat": 32.041,
             "source_url": "https://example.org/reviewed-map",
             "reviewed_on": "2026-09-01"}
AUTO_POINT = {**PED_POINT, "name": "示例机动车入口",
              "lng": 118.792, "lat": 32.042}
SHAPE = "e~epoA|jfpOiDaK"
MATRIX = {"sources_to_targets": [
    [{"time": 0, "distance": 0}, {"time": 200, "distance": 1}, {"time": 300, "distance": 2}],
    [{"time": 200, "distance": 1}, {"time": 0, "distance": 0}, {"time": 220, "distance": 1}],
    [{"time": 300, "distance": 2}, {"time": 220, "distance": 1}, {"time": 0, "distance": 0}],
]}
ROUTE = {"trip": {"legs": [
    {"shape": SHAPE, "summary": {"length": 1.3, "time": 190}},
    {"shape": SHAPE, "summary": {"length": 0.8, "time": 140}},
]}}


class ReviewedAccessTests(unittest.TestCase):
    def test_absent_and_unreviewed_fall_back_without_lying(self):
        for access in (None, {}, {"pedestrian": {**PED_POINT, "status": "draft"}},
                       {"pedestrian": {**PED_POINT, "source_url": ""}},
                       {"pedestrian": {**PED_POINT, "lat": 33.04}},
                       {"pedestrian": {**PED_POINT, "lng": 118.791, "lat": 100}},
                       {"pedestrian": {**PED_POINT, "lng": True}},
                       {"pedestrian": {**PED_POINT, "reviewed_on": "2039-01-01"}},
                       {"pedestrian": {**PED_POINT, "source_url": "file:///etc/passwd"}}):
            with self.subTest(access=access):
                p = apply_routing_access({**CENTER, "routing_access": access}, "pedestrian")
                self.assertEqual((p["lon"], p["lat"]), (CENTER["lon"], CENTER["lat"]))
                self.assertEqual(p["routing_point"]["kind"], "poi_coordinate_fallback")
                self.assertEqual(routing_provenance(p)["kind"], "poi_coordinate_fallback")
                self.assertNotIn("source_url", routing_provenance(p))

    def test_mode_specific_validated_coords_and_source(self):
        place = {**CENTER, "routing_access": {
            "pedestrian": PED_POINT, "auto": AUTO_POINT,
        }}
        walking = apply_routing_access(place, "pedestrian")
        driving = apply_routing_access(place, "auto")
        cycling = apply_routing_access(place, "bicycle")
        self.assertEqual((walking["lon"], walking["lat"]), (118.791, 32.041))
        self.assertEqual((driving["lon"], driving["lat"]), (118.792, 32.042))
        self.assertEqual((cycling["lon"], cycling["lat"]), (118.79, 32.04))
        self.assertEqual(walking["routing_point"]["kind"], "reviewed_access_point")
        self.assertEqual(routing_provenance(driving)["access_name"], "示例机动车入口")
        self.assertNotIn("routing_point", place, "must not mutate original POI")
        self.assertEqual((place["lon"], place["lat"]), (118.79, 32.04))

    def test_future_date_and_bad_url_rejected(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        for item in ({**PED_POINT, "reviewed_on": tomorrow},
                     {**PED_POINT, "source_url": "http://admin:secret@example.org/a"},
                     {**PED_POINT, "source_url": "javascript:alert(1)"}):
            p = apply_routing_access(
                {**CENTER, "routing_access": {"pedestrian": item}}, "pedestrian")
            self.assertEqual(p["routing_point"]["kind"], "poi_coordinate_fallback")

    def test_two_stop_endpoint_uses_reviewed_and_keeps_fallback(self):
        sites = {
            1: {**CENTER, "routing_access": {"pedestrian": PED_POINT}},
            2: SECOND,
        }
        response = {"trip": {
            "summary": {"length": 1.5, "time": 600},
            "legs": [{"shape": SHAPE}],
        }}
        with patch("backend.app.routing_routes.load_places", return_value=sites), \
             patch("backend.app.routing_routes.request_valhalla", return_value=response) as provider:
            result = route_between_places(RoadRouteRequest(from_id=1, to_id=2))
        start, finish = provider.call_args.args
        self.assertEqual(start["lon"], 118.791)
        self.assertEqual(finish["lon"], SECOND["lon"])
        self.assertEqual(provider.call_args.kwargs, {"mode": "pedestrian"})
        points = result["properties"]["routing_points"]
        self.assertEqual([p["kind"] for p in points],
                         ["reviewed_access_point", "poi_coordinate_fallback"])

    def test_multistop_matrix_and_geometry_use_identical_entrances(self):
        stops = [
            {**CENTER, "visit_duration": 60,
             "routing_access": {"pedestrian": PED_POINT}},
            {**SECOND, "visit_duration": 60},
            {**THIRD, "visit_duration": 60,
             "routing_access": {"pedestrian": {**PED_POINT,
                 "name": "示例公园入口", "lng": 118.811, "lat": 32.051}}},
        ]
        with patch("backend.app.road_itinerary.load_itinerary_places", return_value=stops), \
             patch("backend.app.road_itinerary.request_matrix", return_value=MATRIX) as matrix, \
             patch("backend.app.road_itinerary.request_multileg_route", return_value=ROUTE) as route:
            result = plan_itinerary([1, 2, 3], "pedestrian")
        matrix_points = matrix.call_args.args[0]
        route_points = route.call_args.args[0]
        self.assertEqual(matrix_points[0]["lon"], 118.791)
        self.assertEqual(matrix_points[2]["lon"], 118.811)
        self.assertEqual(route_points[0]["lon"], 118.791)
        self.assertEqual(
            [p["id"] for p in route_points], result["optimized_order_ids"]
        )
        self.assertEqual(sum(p["kind"] == "reviewed_access_point"
                             for p in result["routing_points"]), 2)
        self.assertEqual(len(result["geometry"]["features"]), 2)


if __name__ == "__main__":
    unittest.main()
