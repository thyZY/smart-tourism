"""Deterministic diagnostic metrics, including edge cases and provenance."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.ai.recommendation_quality import evaluate_recommendation


class RecommendationQualityTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"id": 1, "name": "历史博物馆", "category": "博物馆"},
            {"id": 2, "name": "城门", "category": "古迹遗址"},
            {"id": 3, "name": "湖边公园", "category": "城市公园"},
        ]

    def test_determinism_and_denominators(self):
        a = evaluate_recommendation(self.candidates, self.candidates[:2],
                                    "历史文化", "南京", "local_rule_fallback")
        b = evaluate_recommendation(self.candidates, self.candidates[:2],
                                    "历史文化", "南京", "local_rule_fallback")
        self.assertEqual(a, b)
        self.assertEqual(a["selected_count"], 2)
        self.assertEqual(a["candidate_count"], 3)
        self.assertEqual(a["category_diversity_ratio"], 1.0)
        self.assertEqual(a["rule_keyword_match_count"], 2)
        self.assertTrue(a["rule_is_actual_ranker"])

    def test_specialist_itinerary_has_low_diversity_without_failure(self):
        rows = [
            {"id": 1, "name": "甲", "category": "博物馆"},
            {"id": 2, "name": "乙", "category": "博物馆"},
        ]
        score = evaluate_recommendation(rows, rows, "博物馆", "南京",
                                        "deepseek_ranked_verified_ids")
        self.assertEqual(score["category_diversity_ratio"], 0.5)
        self.assertFalse(score["rule_is_actual_ranker"])
        self.assertEqual(score["rule_keyword_match_count"], 2)

    def test_rejects_untrusted_ids_and_duplicates(self):
        with self.assertRaises(ValueError):
            evaluate_recommendation(self.candidates, [], "", "", "local_rule_fallback")
        with self.assertRaises(ValueError):
            evaluate_recommendation(self.candidates, self.candidates[:1]*2,
                                    "", "", "local_rule_fallback")
        with self.assertRaises(ValueError):
            evaluate_recommendation(self.candidates, [{"id": 99, "category": "博物馆"}],
                                    "", "", "local_rule_fallback")


if __name__ == "__main__":
    unittest.main()
