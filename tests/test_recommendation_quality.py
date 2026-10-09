"""Regression tests for grounded, diversified and explainable itinerary ranking."""
import unittest
from unittest.mock import patch

from backend.app.ai.itinerary_planner import choose_candidates, build_timeline

ORIGIN = (118.790, 32.040)


def poi(ident, lon, lat, category):
    return {"type": "Feature", "properties": {
        "id": ident, "name": f"景点{ident}", "category": category,
    }, "geometry": {"type": "Point", "coordinates": [lon, lat]}}


FEATURES = [
    poi(1, 118.7900, 32.0400, "博物馆"),
    poi(2, 118.7901, 32.0400, "博物馆"),
    poi(3, 118.7970, 32.0430, "古迹遗址"),
    poi(4, 118.7903, 32.0402, "城市公园"),
    poi(5, 118.7905, 32.0400, "博物馆"),
    poi(6, 118.8000, 32.0440, "历史文化"),
]
METADATA = [
    {"id": 1, "tags": ["展览", "馆藏"], "visit_duration": 90, "indoor": True},
    {"id": 2, "tags": ["展览"], "visit_duration": 90, "indoor": True},
    {"id": 3, "tags": ["古迹", "城墙", "历史"], "visit_duration": 75, "indoor": False},
    {"id": 4, "tags": ["自然", "休闲"], "visit_duration": 90, "indoor": False},
    {"id": 5, "tags": [], "visit_duration": None, "indoor": None},
    {"id": 6, "tags": ["历史", "街区"], "visit_duration": 90, "indoor": None},
]


def rank(items=FEATURES, intent=None, query="", stops=4, budget=480, metadata=METADATA):
    with patch("backend.app.ai.itinerary_planner.load_itinerary_places",
               side_effect=lambda ids: [m for m in metadata if m["id"] in ids]):
        return choose_candidates(items, ORIGIN, stops, budget, intent or {}, query)


class RecommendationQualityTests(unittest.TestCase):
    def test_explicit_interests_can_outweigh_small_distance_advantage(self):
        chosen = rank(
            intent={"categories": ["博物馆", "古迹遗址"]},
            query="喜欢博物馆和古迹", stops=3,
        )
        ids = [f["properties"]["id"] for f in chosen]
        self.assertIn(3, ids, "ancient site must not be displaced by closer identical museums")
        self.assertGreaterEqual(len({f["properties"]["category"] for f in chosen}), 2)
        self.assertTrue(all(id_ in {f["properties"]["id"] for f in FEATURES} for id_ in ids))

    def test_evidence_only_uses_real_tags(self):
        chosen = rank(
            intent={"categories": ["博物馆", "古迹遗址"]},
            query="博物馆和古迹", stops=3,
        )
        by_id = {f["properties"]["id"]: f["properties"]["recommendation"] for f in chosen}
        self.assertIn(3, by_id)
        self.assertTrue(set(by_id[3]["matched_tags"]).issubset(set(METADATA[2]["tags"])))
        self.assertIn("已录入标签", by_id[3]["reason"])
        self.assertIn("直线近似", by_id[3]["reason"])
        self.assertEqual(by_id[3]["source"], "postgis_tourism_metadata")
        self.assertFalse(any("分钟步行" in item["reason"] for item in by_id.values()))

    def test_missing_tags_do_not_turn_into_fictional_evidence(self):
        items = [poi(11, 118.790, 32.040, "博物馆"),
                 poi(12, 118.791, 32.041, "博物馆"),
                 poi(13, 118.792, 32.042, "历史文化")]
        data = [{"id": i, "tags": [], "visit_duration": None, "indoor": None} for i in (11, 12, 13)]
        selected = rank(items=items, metadata=data, stops=3, query="博物馆和历史文化",
                        intent={"categories": ["博物馆", "历史文化"]}, budget=480)
        self.assertEqual(len(selected), 3)
        for f in selected:
            evidence = f["properties"]["recommendation"]
            self.assertEqual(evidence["matched_tags"], [])
            self.assertIn("游览时长资料缺失", evidence["reason"])
            self.assertNotIn("匹配已录入标签", evidence["reason"])
            self.assertFalse(evidence["indoor_match"])

    def test_deterministic_and_no_mutation_of_original_features(self):
        before = repr(FEATURES)
        first = rank()
        second = rank()
        self.assertEqual([f["properties"]["id"] for f in first],
                         [f["properties"]["id"] for f in second])
        self.assertEqual(repr(FEATURES), before)
        self.assertTrue(all("recommendation" in p["properties"] for p in first))

    def test_budget_and_exclusions_apply_to_ranked_candidates(self):
        selected = rank(intent={"categories": ["博物馆", "古迹遗址"],
                                "avoid_categories": ["城市公园"]},
                        query="博物馆和古迹，不要城市公园", budget=290)
        self.assertTrue(all(f["properties"]["category"] != "城市公园" for f in selected))
        self.assertGreaterEqual(len(selected), 3)
        with self.assertRaises(ValueError):
            rank(intent={"categories": ["博物馆"]}, query="博物馆",
                 stops=5, budget=45)

    def test_more_distant_poi_with_relevant_tag_is_eligible(self):
        # Previous algorithm restricted all candidates to 18 closest IDs.
        many = [poi(i, 118.790 + i * 0.00005, 32.040, "城市公园")
                for i in range(1, 21)]
        many.append(poi(99, 118.798, 32.045, "古迹遗址"))
        metadata = [
            {"id": f["properties"]["id"],
             "tags": ["古迹", "遗址"] if f["properties"]["id"] == 99 else ["自然"],
             "visit_duration": 60, "indoor": None}
            for f in many
        ]
        selected = rank(items=many, metadata=metadata,
                        intent={"categories": ["古迹遗址"]}, query="古迹", stops=3)
        self.assertIn(99, [x["properties"]["id"] for x in selected])

    def test_grounded_reason_used_in_existing_timeline(self):
        selected = rank(
            intent={"categories": ["博物馆", "古迹遗址"]},
            query="博物馆和古迹", stops=3,
        )
        ordered = selected
        plan = {
            "ordered_stops": [{"id": f["properties"]["id"],
                               "name": f["properties"]["name"],
                               "visit_duration": 60} for f in ordered],
            "geometry": {"features": [
                {"properties": {"duration_minutes": 8}},
                {"properties": {"duration_minutes": 12}},
            ]},
            "total_plan_minutes": 200,
        }
        timeline, feasible = build_timeline(plan, ordered, 480, "09:00")
        self.assertTrue(feasible)
        self.assertEqual(timeline[0]["reason"],
                         ordered[0]["properties"]["recommendation"]["reason"])
        self.assertIsInstance(timeline[0]["recommendation_score"], float)


if __name__ == "__main__":
    unittest.main()
