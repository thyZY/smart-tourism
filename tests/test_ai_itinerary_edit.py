"""Offline tests for user-edited AI tours, locked stops and honest time budgets."""
import asyncio
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.main import app
from backend.app.ai.router import EditItineraryRequest, edited_itinerary
from backend.app.ai.itinerary_editor import (
    BudgetConflict, fetch_selected_features, replan_edited_itinerary,
)


def feature(ident):
    return {
        "type": "Feature",
        "properties": {"id": ident, "name": f"数据库景点{ident}",
                       "category": "历史文化", "address": "南京"},
        "geometry": {"type": "Point", "coordinates": [118.79 + ident * .001, 32.04]},
    }


DURATIONS = {1: 150, 2: 120, 3: 90, 4: 120, 5: 60}


def mocked_route(ids, mode, mins=5):
    legs = [{"type": "Feature", "properties": {
        "duration_minutes": mins, "from_id": ids[i], "to_id": ids[i + 1],
    }, "geometry": {
        "type": "LineString",
        "coordinates": [[118.79 + ids[i] * .001, 32.04],
                        [118.79 + ids[i + 1] * .001, 32.04]],
    }} for i in range(len(ids) - 1)]
    dwell = sum(DURATIONS[i] or 0 for i in ids)
    missing = sum(DURATIONS[i] is None for i in ids)
    return {
        "mode": mode, "optimized_order_ids": list(ids),
        "ordered_stops": [{"id": i, "name": f"数据库景点{i}",
                           "visit_duration": DURATIONS[i]} for i in ids],
        "distance_km": 3.2, "duration_minutes": (len(ids) - 1) * mins,
        "total_plan_minutes": dwell + (len(ids) - 1) * mins if not missing else None,
        "geometry": {"type": "FeatureCollection", "features": legs},
    }


class EditItineraryTests(unittest.TestCase):
    def setUp(self):
        self.provider = patch.multiple(
            "backend.app.ai.itinerary_editor",
            fetch_selected_features=lambda ids: [feature(i) for i in ids],
            load_itinerary_places=lambda ids: [
                {"id": i, "visit_duration": DURATIONS[i]} for i in ids],
            plan_itinerary=mocked_route,
        )
        self.provider.start()
        self.addCleanup(self.provider.stop)

    def test_endpoint_registered(self):
        self.assertIn("/api/ai/itinerary/replan", app.openapi()["paths"])

    def test_edited_three_to_six_stops_and_replacement_by_db_ids(self):
        result = replan_edited_itinerary(
            [1, 5, 3], [5], "auto", 8, "09:00"
        )
        self.assertEqual(result["itinerary"]["optimized_order_ids"], [1, 5, 3])
        self.assertEqual(result["locked_place_ids"], [5])
        self.assertEqual(result["travel_mode"], "auto")
        self.assertEqual([p["properties"]["id"]
                          for p in result["selected_places"]["features"]], [1, 5, 3])
        self.assertTrue(result["within_time_budget"])
        self.assertEqual(len(result["timeline"]), 3)
        self.assertEqual(result["timeline"][0]["arrival_time"], "09:00")

    def test_budget_trims_last_unlocked_after_real_road_check(self):
        called = []
        def counting(ids, mode):
            called.append(list(ids))
            return mocked_route(ids, mode)
        with patch("backend.app.ai.itinerary_editor.plan_itinerary", side_effect=counting):
            result = replan_edited_itinerary([1, 2, 3, 4], [], "auto", 8, "09:00")
        self.assertEqual(result["dropped_place_ids"], [4])
        self.assertEqual(result["itinerary"]["optimized_order_ids"], [1, 2, 3])
        self.assertEqual(called, [[1, 2, 3]], "known dwell overrun trimmed before expensive road calls")
        self.assertTrue(result["within_time_budget"])

    def test_lock_prevents_auto_removal_and_first_is_always_fixed(self):
        result = replan_edited_itinerary([1, 2, 3, 4], [4], "bicycle", 8, "09:00")
        self.assertEqual(result["dropped_place_ids"], [3])
        self.assertEqual(result["itinerary"]["optimized_order_ids"], [1, 2, 4])
        self.assertIn(4, result["locked_place_ids"])
        self.assertEqual(result["selected_places"]["features"][0]["properties"]["id"], 1)

    def test_locked_overrun_rejected_as_409_without_fake_route(self):
        with self.assertRaises(BudgetConflict):
            replan_edited_itinerary([1, 2, 3, 4], [2, 3, 4], "auto", 8, "09:00")
        with self.assertRaises(HTTPException) as result:
            asyncio.run(edited_itinerary(EditItineraryRequest(
                place_ids=[1, 2, 3, 4], locked_place_ids=[2, 3, 4],
                budget_hours=8,
            )))
        self.assertEqual(result.exception.status_code, 409)

    def test_without_auto_trim_overrun_is_disclosed(self):
        result = replan_edited_itinerary([1, 2, 3, 4], [], "pedestrian",
                                         8, "09:00", False)
        self.assertIs(result["within_time_budget"], False)
        self.assertEqual(result["dropped_place_ids"], [])
        self.assertTrue(any("超出预算" in msg for msg in result["limitations"]))

    def test_unknown_dwell_lower_bound_can_prove_overrun(self):
        prev = DURATIONS[4]
        DURATIONS[4] = None
        try:
            with patch("backend.app.ai.itinerary_editor.plan_itinerary",
                       side_effect=lambda ids, mode: mocked_route(ids, mode, mins=25)):
                result = replan_edited_itinerary([1, 2, 3, 4], [], "auto", 7, "09:00")
            self.assertEqual(result["dropped_place_ids"], [4])
            self.assertTrue(result["within_time_budget"])
        finally:
            DURATIONS[4] = prev

    def test_invalid_inputs_are_422(self):
        bad_cases = [
            {"place_ids": [1, 1, 3]},
            {"place_ids": [1, 2, 3], "locked_place_ids": [4]},
            {"place_ids": [1, -2, 3]},
            {"place_ids": [1, 2, 3], "budget_hours": 8, "start_time": "22:00"},
        ]
        for payload in bad_cases:
            with self.subTest(payload=payload):
                with self.assertRaises(HTTPException) as err:
                    asyncio.run(edited_itinerary(EditItineraryRequest(**payload)))
                self.assertEqual(err.exception.status_code, 422)
        with self.assertRaises(ValidationError):
            EditItineraryRequest(place_ids=[1, 2, 3], transport_mode="transit")
        with self.assertRaises(ValidationError):
            EditItineraryRequest(place_ids=[1, 2])

    def test_missing_db_id_is_404(self):
        with patch("backend.app.ai.itinerary_editor.fetch_selected_features",
                   side_effect=LookupError("not found")):
            with self.assertRaises(HTTPException) as err:
                asyncio.run(edited_itinerary(EditItineraryRequest(place_ids=[1, 2, 3])))
        self.assertEqual(err.exception.status_code, 404)

    def test_network_error_is_502_not_straight_line(self):
        with patch("backend.app.ai.itinerary_editor.plan_itinerary",
                   side_effect=URLError("Valhalla offline")):
            with self.assertRaises(HTTPException) as err:
                asyncio.run(edited_itinerary(EditItineraryRequest(place_ids=[1, 2, 3])))
        self.assertEqual(err.exception.status_code, 502)


class DatabaseGroundingTests(unittest.TestCase):
    def test_sql_uses_parameterized_real_place_ids_and_preserves_order(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (3, "库中景点3", "历史文化", "南京", 118.793, 32.04),
            (1, "库中景点1", "博物馆", "南京", 118.791, 32.04),
            (2, "库中景点2", "博物馆", "南京", 118.792, 32.04),
        ]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch("backend.app.ai.itinerary_editor.get_db_connection",
                   return_value=connection):
            result = fetch_selected_features([1, 2, 3])
        self.assertEqual([r["properties"]["id"] for r in result], [1, 2, 3])
        sql, values = cursor.execute.call_args.args
        self.assertIn("WHERE id = ANY(%s)", sql)
        self.assertEqual(values, ([1, 2, 3],))
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
