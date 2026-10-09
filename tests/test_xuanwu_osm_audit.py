"""Offline regression for source-labelled GCJ inverse and OSM gate audit.

Synthetic OSM fixtures are deliberately NOT real Nanjing entrance claims.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_xuanwu_osm.py"
spec = importlib.util.spec_from_file_location("audit_xuanwu_osm", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
EVIDENCE = json.loads((
    ROOT / "data" / "entrance_evidence" / "xuanwu_lake_20261010.json"
).read_text(encoding="utf-8"))


def sample_osm(lng, lat):
    """One public-looking gate on a footway, one access=no, one unrelated node."""
    return {"elements": [
        {"type": "node", "id": 101, "lon": lng + .00005, "lat": lat + .00004,
         "tags": {"barrier": "gate", "foot": "yes", "name": "合成测试门"}},
        {"type": "node", "id": 102, "lon": lng + .00010, "lat": lat,
         "tags": {"entrance": "yes", "access": "private"}},
        {"type": "node", "id": 103, "lon": lng + .00007, "lat": lat + .00004},
        {"type": "node", "id": 104, "lon": lng + .00012, "lat": lat + .00004},
        {"type": "way", "id": 201, "nodes": [103, 101, 104],
         "tags": {"highway": "footway"}},
        {"type": "way", "id": 202, "nodes": [101, 102],
         "tags": {"highway": "service", "access": "private"}},
    ]}


class XuanwuOSMAuditTests(unittest.TestCase):
    def test_iterative_gcj02_inverse_matches_independent_gate_landmark(self):
        marker = EVIDENCE["candidates"][0]["raw_platform_position"]
        x, y = audit.gcj02_to_wgs84(marker["longitude"], marker["latitude"])
        self.assertAlmostEqual(x, 118.78229935, places=6)
        self.assertAlmostEqual(y, 32.07257793, places=6)
        fx, fy = audit.wgs84_to_gcj02(x, y)
        self.assertAlmostEqual(fx, marker["longitude"], places=8)
        self.assertAlmostEqual(fy, marker["latitude"], places=8)
        reference = EVIDENCE["candidates"][0]["independent_landmark_reference"]
        gap = audit.distance_m(
            (x, y),
            (reference["longitude_wgs84_reference"], reference["latitude_wgs84_reference"]),
        )
        self.assertLess(gap, 15.0)
        # Close landmark coordinates cannot prove the entrance is on a footway.
        self.assertEqual(EVIDENCE["candidates"][0]["status"], "draft")

    def test_both_gate_estimates_are_consistent(self):
        raw = EVIDENCE["candidates"][1]["raw_platform_position"]
        x, y = audit.gcj02_to_wgs84(raw["longitude"], raw["latitude"])
        self.assertAlmostEqual(x, 118.79144511, places=6)
        self.assertAlmostEqual(y, 32.06429665, places=6)

    def test_unconnected_or_restricted_gates_are_not_auto_approved(self):
        lng, lat = 118.7823, 32.07258
        report = audit.inspect_osm(sample_osm(lng, lat), lng, lat)
        self.assertEqual(report["walkable_way_count"], 1)
        self.assertEqual(report["candidate_count"], 2)
        first, second = report["gate_nodes"]
        self.assertEqual(first["osm_node_id"], 101)
        self.assertEqual(first["pedestrian_way_membership_ids"], [201])
        self.assertTrue(first["is_member_of_walkable_osm_way"])
        self.assertFalse(first["tagged_pedestrian_access_restricted"])
        self.assertTrue(first["not_automatically_approved"])
        self.assertEqual(second["osm_node_id"], 102)
        self.assertTrue(second["tagged_pedestrian_access_restricted"])
        self.assertFalse(second["is_member_of_walkable_osm_way"])
        self.assertEqual(second["status"], "candidate_requires_manual_review")

    def test_no_access_restricted_paths_count_as_walkable(self):
        lng, lat = 118.7823, 32.07258
        payload = sample_osm(lng, lat)
        payload["elements"][4]["tags"]["foot"] = "no"
        report = audit.inspect_osm(payload, lng, lat)
        self.assertEqual(report["walkable_way_count"], 0)
        self.assertFalse(report["gate_nodes"][0]["is_member_of_walkable_osm_way"])

    def test_query_explicitly_asks_for_gates_and_footpaths(self):
        query = audit.build_query(118.7823, 32.07258)
        self.assertIn('node(around:180,32.07258000,118.78230000)["entrance"]', query)
        self.assertIn("footway|pedestrian|path|steps", query)
        self.assertIn(");(._;>;);out body;", query)
        for radius in (0, 49, 351, 1000):
            with self.assertRaises(ValueError):
                audit.build_query(118.7823, 32.07258, radius)

    def test_snapshot_cli_saves_draft_json_and_qgis_geojson_not_sql(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            for candidate in EVIDENCE["candidates"]:
                raw = candidate["raw_platform_position"]
                lng, lat = audit.gcj02_to_wgs84(raw["longitude"], raw["latitude"])
                (directory / (candidate["candidate_id"] + ".json")).write_text(
                    json.dumps(sample_osm(lng, lat)), encoding="utf-8")
            output = directory / "audit.json"
            status = audit.main(["--osm-json-dir", str(directory), "--out", str(output)])
            self.assertEqual(status, 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["routing_activation"], "none")
            self.assertEqual(report["status"], "research_only_unreviewed")
            self.assertEqual(len(report["entrances"]), 2)
            self.assertEqual(report["entrances"][0]["osm_result"]["candidate_count"], 2)
            geojson = json.loads(output.with_suffix(".geojson").read_text(encoding="utf-8"))
            self.assertEqual(geojson["type"], "FeatureCollection")
            self.assertEqual(len(geojson["features"]), 6)
            self.assertTrue(all(f["properties"]["status"] != "reviewed"
                                for f in geojson["features"]))

    def test_missing_snapshot_or_invalid_coordinates_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                audit.audit(EVIDENCE, snapshots=directory)
        for lng, lat in ((120, 100), (0, 0), (float("nan"), 32), ("abc", 32)):
            with self.assertRaises(ValueError):
                audit.gcj02_to_wgs84(lng, lat)

    def test_no_implicit_network_or_database_side_effect(self):
        with self.assertRaises(ValueError):
            audit.audit(EVIDENCE)
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("UPDATE places", source)
        self.assertNotIn("status': 'reviewed'", source)


if __name__ == "__main__":
    unittest.main()
