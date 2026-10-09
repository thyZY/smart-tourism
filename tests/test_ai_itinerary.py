"""Offline personalized AI itinerary tests: grounded data, budget, modal travel, time safety."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.main import app
from backend.app.ai.router import PersonalizedItineraryRequest, personalized_itinerary
from backend.app.ai.itinerary_planner import (
    build_personalized_itinerary, build_timeline, choose_candidates, resolve_travel_mode,
)
from backend.app.ai.tourism_agent import fallback_intent


def place(ident, lon, lat, category="历史文化"):
    return {"type": "Feature", "properties": {
        "id": ident, "name": f"景点{ident}", "category": category, "address": "南京",
    }, "geometry": {"type": "Point", "coordinates": [lon, lat]}}


FEATURES = [
    place(1, 118.790, 32.040, "博物馆"),
    place(2, 118.791, 32.041),
    place(3, 118.793, 32.042),
    place(4, 118.794, 32.043),
]
PLACES = [
    {"id": 1, "name": "景点1", "lon": 118.790, "lat": 32.040, "visit_duration": 150},
    {"id": 2, "name": "景点2", "lon": 118.791, "lat": 32.041, "visit_duration": 120},
    {"id": 3, "name": "景点3", "lon": 118.793, "lat": 32.042, "visit_duration": 90},
    {"id": 4, "name": "景点4", "lon": 118.794, "lat": 32.043, "visit_duration": 180},
]
ITINERARY = {
    "mode": "auto",
    "ordered_stops": [
        {"id": 1, "name": "景点1", "visit_duration": 150},
        {"id": 3, "name": "景点3", "visit_duration": 90},
        {"id": 2, "name": "景点2", "visit_duration": 120},
    ],
    "optimized_order_ids": [1, 3, 2],
    "distance_km": 4.5, "duration_minutes": 29.0,
    "total_plan_minutes": 389.0,
    "geometry": {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"duration_minutes": 12.0}, "geometry": {
            "type": "LineString", "coordinates": [[118.790, 32.040], [118.793, 32.042]]}},
        {"type": "Feature", "properties": {"duration_minutes": 17.0}, "geometry": {
            "type": "LineString", "coordinates": [[118.793, 32.042], [118.791, 32.041]]}},
    ]},
}


class PersonalizedItineraryTests(unittest.TestCase):
    def test_endpoint_registered(self):
        self.assertIn("/api/ai/itinerary", app.openapi()["paths"])

    def test_modes_and_user_override(self):
        low = {"walking_level": "low"}
        self.assertEqual(resolve_travel_mode("南京一天 少走路", low), "auto")
        self.assertEqual(resolve_travel_mode("想骑行", low), "bicycle")
        self.assertEqual(resolve_travel_mode("步行路线", low), "pedestrian")
        self.assertEqual(resolve_travel_mode("少走路", low, "pedestrian"), "pedestrian")
        with self.assertRaises(ValueError):
            resolve_travel_mode("", low, "transit")

    def test_reject_invalid_day_and_hours_parameters(self):
        with self.assertRaises(ValidationError):
            PersonalizedItineraryRequest(query="旅游", lng=118.7, lat=32, max_stops=7)
        with self.assertRaises(ValidationError):
            PersonalizedItineraryRequest(query="旅游", lng=118.7, lat=32, budget_hours=2)
        with self.assertRaises(ValidationError):
            PersonalizedItineraryRequest(query="旅游", lng=118.7, lat=32, start_time="9pm")
        with patch("backend.app.ai.router.parse_tourism_intent",
                   new=AsyncMock(return_value=({**fallback_intent("两天游"), "duration_days": 2}, "rule_based"))):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(personalized_itinerary(PersonalizedItineraryRequest(
                    query="南京两天旅游", lng=118.79, lat=32.04,
                )))
        self.assertEqual(error.exception.status_code, 422)

    def test_choose_candidates_from_real_ids_and_dwell_budget(self):
        with patch("backend.app.ai.itinerary_planner.load_itinerary_places", return_value=PLACES) as loader:
            selected = choose_candidates(FEATURES, (118.790, 32.040), 4, 480)
        loader.assert_called_once()
        self.assertEqual([f["properties"]["id"] for f in selected], [1, 2, 3])
        # No model-generated POI ID or coords can enter selected result.
        self.assertTrue(all(f in FEATURES for f in selected))
        with patch("backend.app.ai.itinerary_planner.load_itinerary_places", return_value=PLACES):
            with self.assertRaises(ValueError):
                choose_candidates(FEATURES, (118.790, 32.040), 4, 180)

    def test_timeline_from_measured_legs_and_known_visit_times(self):
        timeline, fit = build_timeline(ITINERARY, FEATURES[:3], 480, "09:00")
        self.assertTrue(fit)
        self.assertEqual([s["id"] for s in timeline], [1, 3, 2])
        self.assertEqual(timeline[0]["arrival_time"], "09:00")
        self.assertEqual(timeline[0]["departure_time"], "11:30")
        self.assertEqual(timeline[1]["arrival_time"], "11:42")
        self.assertEqual(timeline[-1]["departure_time"], "15:29")
        self.assertFalse(build_timeline(ITINERARY, FEATURES[:3], 360, "09:00")[1])
        missing = dict(ITINERARY)
        missing["ordered_stops"] = [
            {**item, "visit_duration": None} if item["id"] == 3 else item
            for item in ITINERARY["ordered_stops"]
        ]
        missing["total_plan_minutes"] = None
        timeline, fit = build_timeline(missing, FEATURES[:3], 480, "09:00")
        self.assertIsNone(fit)
        self.assertIsNone(timeline[-1]["arrival_time"])
        self.assertIsNone(timeline[1]["departure_time"])

    def test_builder_rejects_untrusted_itinerary_ids(self):
        intent = fallback_intent("一天历史文化，少走路")
        route = {**ITINERARY, "optimized_order_ids": [1, 999, 2]}
        with patch("backend.app.ai.itinerary_planner.plan_itinerary", return_value=route):
            with self.assertRaises(ValueError):
                build_personalized_itinerary(FEATURES, (118.79, 32.04), intent, "auto",
                                             3, 8, "09:00", FEATURES[:3])

    def test_true_end_to_end_handler_with_mocked_postgis_and_route(self):
        intent = fallback_intent("南京一天历史游，少走路")
        with patch("backend.app.ai.router.parse_tourism_intent",
                   new=AsyncMock(return_value=(intent, "deepseek"))), \
             patch("backend.app.ai.router.query_pois", return_value=FEATURES), \
             patch("backend.app.ai.itinerary_planner.load_itinerary_places", return_value=PLACES), \
             patch("backend.app.ai.itinerary_planner.plan_itinerary", return_value=ITINERARY):
            response = asyncio.run(personalized_itinerary(PersonalizedItineraryRequest(
                query="南京一天历史游，少走路", lng=118.79, lat=32.04, max_stops=4,
                budget_hours=8, start_time="09:00",
            )))
        self.assertEqual(response["ai_mode"], "deepseek")
        self.assertEqual(response["travel_mode"], "auto")
        self.assertEqual(response["itinerary"]["optimized_order_ids"], [1, 3, 2])
        self.assertEqual(len(response["selected_places"]["features"]), 3)
        self.assertTrue(response["within_time_budget"])
        self.assertEqual(response["timeline"][0]["arrival_time"], "09:00")
        self.assertTrue(any("景区内" in item for item in response["limitations"]))

    def test_fewer_than_three_pois_422(self):
        with patch("backend.app.ai.router.parse_tourism_intent",
                   new=AsyncMock(return_value=(fallback_intent("一日游"), "rule_based"))), \
             patch("backend.app.ai.router.query_pois", return_value=FEATURES[:2]):
            with self.assertRaises(HTTPException) as failure:
                asyncio.run(personalized_itinerary(PersonalizedItineraryRequest(
                    query="一日游", lng=118.79, lat=32.04,
                )))
        self.assertEqual(failure.exception.status_code, 422)

    def test_valhalla_failure_does_not_fake_geometry(self):
        from urllib.error import URLError
        with patch("backend.app.ai.router.parse_tourism_intent",
                   new=AsyncMock(return_value=(fallback_intent("一天游"), "rule_based"))), \
             patch("backend.app.ai.router.query_pois", return_value=FEATURES), \
             patch("backend.app.ai.router.choose_candidates", return_value=FEATURES[:3]), \
             patch("backend.app.ai.router.build_personalized_itinerary",
                   side_effect=URLError("routing unavailable")):
            with self.assertRaises(HTTPException) as failure:
                asyncio.run(personalized_itinerary(PersonalizedItineraryRequest(
                    query="一天游", lng=118.79, lat=32.04,
                )))
        self.assertEqual(failure.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
