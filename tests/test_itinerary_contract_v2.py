"""Gate B additive contract regression without databases or paid services."""
import sys
import unittest
from pathlib import Path
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.ai.itinerary_contract import PlanningPreferences, attach_contract


class GateBContractTests(unittest.TestCase):
    def test_backwards_compatibility_and_provenance(self):
        old = {"schema_version": 1, "planning_method": "local_rule_fallback",
               "route": {"status": "unavailable"}, "stops": [{"id": 4}],
               "selected_places": {"type": "FeatureCollection", "features": []}}
        new = attach_contract(old)
        for key, value in old.items():
            self.assertEqual(new[key], value)
        self.assertEqual(new["contract_version"], 2)
        self.assertEqual(new["provenance"]["poi_source"], "postgis")
        self.assertEqual(new["provenance"]["routing_status"], "unavailable")
        self.assertEqual(new["provenance"]["schedule_status"], "not_computed")
        self.assertIsNone(new["planning_preferences"]["departure_time"])
        self.assertNotIn("distance_km", new["route"])

    def test_future_preferences_validate_but_do_not_activate_scheduling(self):
        valid = PlanningPreferences(departure_time="09:30",
                                    time_budget_hours=6, locked_place_ids=[3, 5])
        old = {"planning_method": "restored_from_verified_ids",
               "route": {"status": "verified_by_routing_service",
                         "distance_km": 2.4}}
        output = attach_contract(old, valid)
        self.assertEqual(output["planning_preferences"]["locked_place_ids"], [3, 5])
        self.assertEqual(output["provenance"]["schedule_status"], "not_computed")
        for data in (
            {"departure_time": "25:99"}, {"time_budget_hours": 1},
            {"locked_place_ids": [1, 1]}, {"locked_place_ids": [-1]},
            {"unknown_field": "invalid"},
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                PlanningPreferences(**data)


if __name__ == "__main__":
    unittest.main()
