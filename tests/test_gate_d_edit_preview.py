"""Offline Gate D confirmed-edit contract tests."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.ai.itinerary_edit import edit_stop_ids
from app.ai import itinerary_routes

POIS = [
    {"id": 1, "name": "南京博物院", "category": "博物馆", "address": "A", "lng": 118.7, "lat": 32.0},
    {"id": 2, "name": "夫子庙", "category": "历史文化", "address": "B", "lng": 118.8, "lat": 32.1},
    {"id": 3, "name": "中山陵", "category": "陵园", "address": "C", "lng": 118.9, "lat": 32.2},
]
class GateDEditTests(unittest.TestCase):
    def test_remove_and_reorder(self):
        out = edit_stop_ids(POIS, "删除中山陵")
        self.assertEqual(out["place_ids"], [1, 2])
        self.assertEqual(out["operation"], "remove")
        out = edit_stop_ids(POIS, "将中山陵调整到第2站")
        self.assertEqual(out["place_ids"], [1, 3, 2])
        self.assertEqual(out["operation"], "move")

    def test_no_guessing_or_invalid_edits(self):
        for sentence in ("尽量少步行", "删除不存在的景点", "保留夫子庙", "把中山陵放到第5站"):
            with self.subTest(sentence=sentence), self.assertRaises(ValueError):
                edit_stop_ids(POIS, sentence)
        with self.assertRaises(ValueError):
            edit_stop_ids(POIS[:2], "删除夫子庙")

    def test_verified_api_preview_never_mutates_original(self):
        app = FastAPI()
        app.include_router(itinerary_routes.router)
        client = TestClient(app)
        with patch.object(itinerary_routes, "fetch_candidates", return_value=POIS), \
             patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""}), \
             patch.object(itinerary_routes, "valhalla_route", return_value={
                 "status": "unavailable", "message": "offline test"}):
            original = [1, 2, 3]
            res = client.post("/api/ai/itinerary/edit-preview", json={
                "place_ids": original, "instruction": "删除中山陵", "travel_mode": "pedestrian"})
            self.assertEqual(res.status_code, 200, res.text)
            payload = res.json()
            self.assertEqual(original, [1, 2, 3])
            self.assertEqual([s["id"] for s in payload["stops"]], [1, 2])
            self.assertEqual(payload["planning_method"], "confirmed_edit_preview")
            self.assertEqual(payload["provenance"]["planning_method"], "confirmed_edit_preview")
            self.assertEqual(payload["route"]["status"], "unavailable")
            self.assertEqual(client.post("/api/ai/itinerary/edit-preview", json={
                "place_ids": [1, 999], "instruction": "删除夫子庙"}).status_code, 409)
            self.assertEqual(client.post("/api/ai/itinerary/edit-preview", json={
                "place_ids": [1, 2, 3], "instruction": "去游泳"}).status_code, 422)

if __name__ == "__main__":
    unittest.main()
