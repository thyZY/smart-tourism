"""Keep external entrance research explicitly unreviewed and coordinate-safe."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "entrance_evidence" / "xuanwu_lake_20261010.json"
DRAFT_SQL = ROOT / "database" / "reviews" / "xuanwu_lake_20261010_draft.sql"


class XuanwuLakeEntranceEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DATASET.read_text(encoding="utf-8"))
        cls.sql = DRAFT_SQL.read_text(encoding="utf-8")

    def test_data_is_grounded_in_real_specific_sources(self):
        evidence = self.dataset
        self.assertEqual(evidence["poi_name"], "玄武湖公园")
        self.assertEqual(evidence["dataset_status"], "draft_requires_manual_spatial_review")
        self.assertEqual({c["candidate_id"] for c in evidence["candidates"]},
                         {"xuanwumen_west", "jiefangmen_south"})
        for entry in evidence["candidates"]:
            self.assertEqual(entry["status"], "draft")
            self.assertEqual(entry["travel_modes_under_review"], ["pedestrian"])
            self.assertGreaterEqual(len(entry["remaining_checks"]), 3)
            self.assertTrue(entry["park_page_url"].startswith("https://www.xuanwuhu.net/"))
            self.assertIn("amap.com", urlsplit(
                entry["raw_platform_position"]["source_url"]).hostname)
            self.assertIn("do_not_use_as_WGS84", entry["raw_platform_position"]["coordinate_system"])

    def test_gcj_coords_stay_as_provenance_not_routing_wgs84(self):
        for entry in self.dataset["candidates"]:
            raw = entry["raw_platform_position"]
            self.assertGreater(raw["longitude"], 118)
            self.assertGreater(raw["latitude"], 32)
            self.assertNotIn("lng", entry)
            self.assertNotIn("lat", entry)
            if entry["independent_landmark_reference"] is not None:
                self.assertIn("gate", entry["independent_landmark_reference"]["warning"])
                self.assertNotIn("reviewed", entry)

    def test_draft_sql_does_not_activate_or_overwrite_reviewed_point(self):
        sql = self.sql
        self.assertIn("'status', 'draft'", sql)
        self.assertIn("routing_access -> 'pedestrian' ->> 'status' = 'draft'", sql)
        self.assertIn("routing_access -> 'pedestrian' IS NULL", sql)
        self.assertIn("WHERE name = '玄武湖公园'", sql)
        self.assertNotIn("'status', 'reviewed'", sql)
        self.assertNotIn("'lng',", sql)
        self.assertNotIn("'lat',", sql)
        self.assertNotIn("UPDATE places SET geom", sql.upper())

    def test_no_unverified_automotive_access(self):
        vehicle = self.dataset["motor_vehicle_policy"]
        self.assertIsNone(vehicle["auto_entry"])
        self.assertEqual(vehicle["status"], "not_proven")
        self.assertEqual(self.dataset["routing_activation"], "none; this research file does not change PostGIS or Valhalla routing")


if __name__ == "__main__":
    unittest.main()
