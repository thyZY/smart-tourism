import unittest

from backend.app.tourism_routes import create_tourism_card


class TourismRouteFactoryTests(unittest.TestCase):
    def test_card_contains_stable_fields(self):
        result = create_tourism_card({
            "id": 1,
            "name": "南京博物院",
            "category": "博物馆",
            "visit_duration": 180,
            "indoor": True,
            "tags": ["历史", "文化"],
        })
        self.assertEqual(result["name"], "南京博物院")
        self.assertEqual(result["visit_duration"], 180)
        self.assertIn("历史", result["tags"])


if __name__ == "__main__":
    unittest.main()
