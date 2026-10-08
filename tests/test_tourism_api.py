import unittest

from backend.app.tourism_api import build_tourism_card


class TourismApiTests(unittest.TestCase):
    def test_card_keeps_spatial_and_tourism_fields(self):
        card = build_tourism_card({
            "id": 1,
            "name": "南京博物院",
            "category": "博物馆",
            "address": "南京",
            "visit_duration": 180,
            "indoor": True,
            "tags": ["历史", "文化"],
        })
        self.assertEqual(card["name"], "南京博物院")
        self.assertEqual(card["visit_duration"], 180)
        self.assertTrue(card["indoor"])
        self.assertIn("历史", card["tags"])

    def test_old_poi_is_compatible(self):
        card = build_tourism_card({"id": 2, "name": "旧景点"})
        self.assertEqual(card["tags"], [])
        self.assertIsNone(card["visit_duration"])


if __name__ == "__main__":
    unittest.main()
