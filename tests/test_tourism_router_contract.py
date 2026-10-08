"""Contract checks for tourism card structures.

These tests are intentionally independent from a local database. They verify
that the tourism module keeps a stable frontend-facing schema while database
wiring is integrated incrementally.
"""

import unittest

from backend.app.tourism_api import build_tourism_card


class TourismRouterContractTests(unittest.TestCase):
    def test_card_contains_recommendation_fields(self):
        card = build_tourism_card({
            "id": 1,
            "name": "南京博物院",
            "category": "博物馆",
            "visit_duration": 180,
            "indoor": True,
            "tags": ["历史", "文化"],
        })

        self.assertEqual(card["name"], "南京博物院")
        self.assertEqual(card["visit_duration"], 180)
        self.assertTrue(card["indoor"])
        self.assertIn("历史", card["tags"])

    def test_old_poi_payload_remains_supported(self):
        card = build_tourism_card({
            "id": 2,
            "name": "测试景点",
            "category": "景区",
        })

        self.assertEqual(card["name"], "测试景点")
        self.assertIn("tags", card)
        self.assertIn("visit_duration", card)


if __name__ == "__main__":
    unittest.main()
