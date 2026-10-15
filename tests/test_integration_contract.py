"""Protect the current itinerary API while legacy routing branches are reconciled.

Offline OpenAPI assertions; this does NOT mean the two divergent branches are
merged or that PostgreSQL/Valhalla/DeepSeek have been tested end to end.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app


class IntegrationContractTests(unittest.TestCase):
    def test_current_itinerary_contract_is_unambiguous(self):
        paths = app.openapi()["paths"]
        generate = paths["/api/ai/itinerary/generate"]["post"]
        restore = paths["/api/ai/itinerary/restore"]["post"]
        self.assertIn("requestBody", generate)
        self.assertIn("requestBody", restore)
        schema = app.openapi()["components"]["schemas"]["ItineraryRequest"]
        props = schema["properties"]
        self.assertIn("excluded_place_ids", props)
        self.assertIn("travel_mode", props)
        self.assertIn("max_stops", props)
        self.assertEqual(props["excluded_place_ids"]["maxItems"], 40)

    def test_no_duplicate_method_path_registrations(self):
        keys = [
            (method, route.path)
            for route in app.routes
            for method in (getattr(route, "methods", None) or [])
            if route.path.startswith("/api/")
        ]
        self.assertEqual(len(keys), len(set(keys)), "API route collisions need explicit resolution")

    def test_no_silent_assumption_of_legacy_endpoints(self):
        paths = app.openapi()["paths"]
        # Legacy branch exposes a DIFFERENT POST /api/ai/itinerary contract.
        # It must not be represented as integrated until schema reconciliation.
        self.assertNotIn("/api/ai/itinerary", paths)
        self.assertNotIn("/api/ai/itinerary/chat/preview", paths)
        self.assertNotIn("/api/routing/itinerary", paths)


if __name__ == "__main__":
    unittest.main()
