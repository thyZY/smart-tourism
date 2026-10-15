"""No paid requests: bounded AI intent, invalid responses and DB-grounded preview."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.ai.itinerary_intent import resolve_edit_intent
from app.ai import itinerary_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient

POIS = [
    {"id": 1, "name": "南京博物院", "category": "博物馆", "address": "", "lng": 118.7, "lat": 32.0},
    {"id": 2, "name": "夫子庙", "category": "文化", "address": "", "lng": 118.8, "lat": 32.1},
    {"id": 3, "name": "中山陵", "category": "陵园", "address": "", "lng": 118.9, "lat": 32.2},
]
class FakeClient:
    payload = None
    calls = []
    def chat_json(self, system, user):
        self.calls.append((system, user))
        return self.payload


class TestBoundedIntent(unittest.TestCase):
    def resolve(self, instruction, payload):
        FakeClient.payload = payload
        FakeClient.calls = []
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only"}):
            return resolve_edit_intent(POIS, instruction, client_factory=FakeClient)

    def test_existing_id_reorder(self):
        result = self.resolve("把最后一个景点放在第二站",
                              {"operation": "move", "place_id": 3, "position": 2})
        self.assertEqual(result["place_ids"], [1, 3, 2])
        self.assertEqual(result["intent_source"], "deepseek_bounded_json")
        self.assertIn("南京博物院", FakeClient.calls[0][1])

    def test_invalid_and_untrusted_output(self):
        for output in (
            {"operation": "remove", "place_id": 999, "position": None},
            {"operation": "remove", "place_id": True, "position": None},
            {"operation": "remove", "place_id": 1, "position": 1},
            {"operation": "move", "place_id": 2, "position": 99},
            {"operation": "unsupported", "place_id": None, "position": None},
            {"operation": "move", "place_id": 2, "position": 1, "coordinates": [1,2]},
            ["unexpected"],
        ):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.resolve("修改行程", output)

    def test_no_key_rejects_unhandled_request(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "DeepSeek"):
                resolve_edit_intent(POIS, "少走一点路")

    def test_preview_endpoint_does_not_apply(self):
        app = FastAPI()
        app.include_router(itinerary_routes.router)
        client = TestClient(app)
        with patch.object(itinerary_routes, "fetch_candidates", return_value=POIS), \
             patch.object(itinerary_routes, "valhalla_route", return_value={"status":"unavailable"}), \
             patch.object(itinerary_routes, "resolve_edit_intent", return_value={
                 "place_ids": [1,3,2], "operation":"move", "matched_place_id": 3,
                 "intent_source":"deepseek_bounded_json", "instruction":"最后一站提前"}):
            response = client.post("/api/ai/itinerary/edit-preview", json={
                "place_ids": [1,2,3], "instruction":"最后一站提前"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([s["id"] for s in response.json()["stops"]], [1,3,2])
        self.assertEqual(response.json()["edit_summary"]["intent_source"], "deepseek_bounded_json")

if __name__ == "__main__":
    unittest.main()
