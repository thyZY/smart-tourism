import unittest

from backend.app.tourism_metadata import normalize_tourism_metadata


class TourismMetadataTests(unittest.TestCase):
    def test_defaults_keep_old_poi_compatible(self):
        result = normalize_tourism_metadata({"name": "测试景点"})
        self.assertEqual(result["name"], "测试景点")
        self.assertEqual(result["tags"], [])
        self.assertIsNone(result["visit_duration"])

    def test_metadata_preserved(self):
        result = normalize_tourism_metadata({
            "visit_duration": 120,
            "indoor": True,
            "tags": ["历史", "文化"]
        })
        self.assertEqual(result["visit_duration"], 120)
        self.assertTrue(result["indoor"])
        self.assertIn("历史", result["tags"])


if __name__ == "__main__":
    unittest.main()
