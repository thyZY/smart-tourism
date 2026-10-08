"""Catalog checks require no PostgreSQL server."""
import unittest

from scripts.import_tourism_metadata import load_records


class TourismCatalogTests(unittest.TestCase):
    def test_all_40_names_are_present_and_valid(self):
        records = load_records()
        self.assertEqual(len(records), 40)
        self.assertEqual(len({item["name"] for item in records}), 40)
        self.assertTrue(all(15 <= item["visit_duration"] <= 480 for item in records))

    def test_mixed_indoor_places_remain_unknown(self):
        records = {item["name"]: item for item in load_records()}
        self.assertIsNone(records["夫子庙"]["indoor"])
        self.assertIsNone(records["中山陵"]["indoor"])

    def test_unknown_best_time_is_not_fabricated(self):
        self.assertTrue(all(item["best_time"] == "" for item in load_records()))


if __name__ == "__main__":
    unittest.main()
