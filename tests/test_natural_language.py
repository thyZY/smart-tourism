"""Pure parser tests: no database or external AI account required."""
import unittest
from backend.app.natural_language import parse_intent


class IntentTests(unittest.TestCase):
    def test_museum_request(self):
        result = parse_intent("我想找附近5公里的博物馆")
        self.assertEqual(result.categories, ("博物馆",))
        self.assertEqual(result.radius_m, 5000)
        self.assertTrue(result.nearby)

    def test_history_and_limits(self):
        result = parse_intent("南京历史文化景点，一天，少走路，预算有限")
        self.assertIn("古迹遗址", result.categories)
        self.assertIn("行程安排", result.unsupported)
        self.assertIn("步行负担", result.unsupported)
        self.assertIn("预算筛选", result.unsupported)

    def test_no_fabricated_constraints(self):
        result = parse_intent("我想去夫子庙")
        self.assertEqual(result.categories, ())
        self.assertFalse(result.nearby)

    def test_exclusions_not_inverted(self):
        result = parse_intent("我不喜欢公园，想逛景点")
        self.assertEqual(result.categories, ())
        self.assertFalse(result.generic)
        self.assertIn("排除式偏好", result.unsupported)

    def test_radius_validation(self):
        with self.assertRaises(ValueError):
            parse_intent("附近100公里的公园")

    def test_default_radius(self):
        self.assertEqual(parse_intent("周边寺庙").radius_m, 5000)


if __name__ == "__main__":
    unittest.main()
