import unittest

from backend.app.poi_tourism_service import build_tourism_card, enrich_place_properties


class TourismServiceTests(unittest.TestCase):
    def test_enrich_keeps_old_properties(self):
        result = enrich_place_properties(
            {"name": "南京博物院", "category": "博物馆"},
            {"visit_duration": 180, "tags": ["历史"]},
        )
        self.assertEqual(result["name"], "南京博物院")
        self.assertEqual(result["visit_duration"], 180)
        self.assertEqual(result["tags"], ["历史"])

    def test_card_has_stable_fields(self):
        card = build_tourism_card({"properties": {"name": "夫子庙"}})
        self.assertIn("visit_duration", card)
        self.assertEqual(card["tags"], [])


if __name__ == "__main__":
    unittest.main()
