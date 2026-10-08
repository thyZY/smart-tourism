"""Deterministic itinerary preview: pure Python, no DB connection needed."""
import unittest

from backend.app.itinerary import build_preview


def feature(place_id, lng, lat):
    return {
        "type": "Feature",
        "properties": {"id": place_id, "name": f"POI-{place_id}", "category": "博物馆"},
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
    }


class PreviewTests(unittest.TestCase):
    def test_nearest_order(self):
        features = [
            feature(3, 118.83, 32.04),
            feature(2, 118.80, 32.04),
            feature(1, 118.79, 32.04),
        ]
        result = build_preview(features, (118.79, 32.04), max_stops=3)
        self.assertEqual([f["properties"]["id"] for f in result["stops"]], [1, 2, 3])
        self.assertGreater(result["between_stops_direct_km"], 0)
        self.assertEqual(result["method"], "greedy_straight_line_proximity")

    def test_deduplicates_ids(self):
        features = [feature(1, 118.79, 32.04), feature(1, 118.79, 32.04),
                    feature(2, 118.80, 32.04)]
        result = build_preview(features, (118.79, 32.04))
        self.assertEqual(len(result["stops"]), 2)

    def test_empty(self):
        result = build_preview([], (118.79, 32.04))
        self.assertEqual(result["stops"], [])
        self.assertEqual(result["from_origin_direct_km"], 0)

    def test_max_stops_limit(self):
        with self.assertRaises(ValueError):
            build_preview([], (118.79, 32.04), max_stops=7)

    def test_no_assumed_travel_time(self):
        result = build_preview([feature(1, 118.79, 32.04)], (118.79, 32.04))
        self.assertNotIn("travel_minutes", result)
        self.assertNotIn("arrival_time", result)


if __name__ == "__main__":
    unittest.main()
