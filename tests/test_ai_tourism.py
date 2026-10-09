"""Tests for model trust boundary, rule fallback, SQL grounding, and map preview.

No API key, network connection, or live PostgreSQL instance is required.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.app.ai.tourism_agent import (
    fallback_intent, normalize_model_intent, parse_tourism_intent,
)
from backend.app.ai.router import TourismSearchRequest, tourism_search, query_pois
from backend.app.main import app


class FakeClient:
    enabled = True

    async def chat_json(self, messages):
        return {
            "categories": ["博物馆", "不存在的分类"],
            "avoid_categories": ["城市公园"],
            "nearby": False,
            "radius_km": 2,
            "duration_days": 1,
            "walking_level": "low",
        }


class FailingClient:
    enabled = True

    async def chat_json(self, messages):
        raise OSError("temporary provider failure")


class TourismAiTests(unittest.TestCase):
    def test_existing_routes_and_new_ai_route_registered(self):
        paths = set(app.openapi()["paths"])
        for route in (
            "/api/ai/tourism-search",
            "/api/places",
            "/api/places/nearby",
            "/api/places/natural",
            "/api/places/itinerary-preview",
            "/api/tourism/places/{place_id}",
        ):
            self.assertIn(route, paths)

    def test_rule_fallback_without_key(self):
        class Disabled:
            enabled = False
        intent, mode = asyncio.run(parse_tourism_intent(
            "附近5公里博物馆，一天，少走路", client=Disabled()
        ))
        self.assertEqual(mode, "rule_based")
        self.assertEqual(intent["categories"], ["博物馆"])
        self.assertEqual(intent["radius_m"], 5000)
        self.assertEqual(intent["duration_days"], 1)
        self.assertEqual(intent["walking_level"], "low")

    def test_model_categories_whitelisted(self):
        result = normalize_model_intent({
            "categories": ["博物馆", "假的景点", "博物馆"],
            "avoid_categories": ["城市公园"],
            "nearby": True, "radius_km": 2,
            "duration_days": 3, "walking_level": "low",
        }, "附近博物馆")
        self.assertEqual(result["categories"], ["博物馆"])
        self.assertEqual(result["avoid_categories"], ["城市公园"])
        self.assertEqual(result["radius_m"], 2000)

    def test_model_never_directly_recommends_pois(self):
        intent, mode = asyncio.run(parse_tourism_intent(
            "想看博物馆", client=FakeClient()
        ))
        self.assertEqual(mode, "deepseek")
        self.assertEqual(intent["categories"], ["博物馆"])
        self.assertNotIn("name", intent)

    def test_provider_failure_falls_back(self):
        intent, mode = asyncio.run(parse_tourism_intent("历史景点", client=FailingClient()))
        self.assertEqual(mode, "rule_based_fallback")
        self.assertIn("历史文化", intent["categories"])

    def test_sql_parameters_and_genuine_features(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (1, "南京博物院", "博物馆", "中山东路", 118.7921, 32.0407),
            (2, "南京市博物馆", "博物馆", "朝天宫", 118.7701, 32.0376),
        ]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        intent = {
            "categories": ["博物馆"], "avoid_categories": [],
            "nearby": True, "radius_m": 5000,
            "duration_days": None, "walking_level": None,
        }
        with patch("backend.app.ai.router.get_db_connection", return_value=connection):
            features = query_pois(intent, (118.7921, 32.0407))
        sql, params = cursor.execute.call_args.args
        self.assertIn("= ANY(%s)", sql)
        self.assertIn("ST_DWithin", sql)
        self.assertNotIn("博物馆", sql)
        self.assertEqual(params[0], ["博物馆"])
        self.assertEqual(params[-1], 5000)
        self.assertEqual(features[0]["properties"]["name"], "南京博物院")
        connection.close.assert_called_once()

    def test_post_returns_geojson_and_clear_limitations(self):
        intent = fallback_intent("南京一天历史文化景点，少走路")
        poi = {
            "type": "Feature",
            "properties": {"id": 1, "name": "南京博物院", "category": "博物馆"},
            "geometry": {"type": "Point", "coordinates": [118.7921, 32.0407]},
        }
        with patch("backend.app.ai.router.parse_tourism_intent", new=AsyncMock(
            return_value=(intent, "rule_based")
        )), patch("backend.app.ai.router.query_pois", return_value=[poi]):
            response = asyncio.run(tourism_search(TourismSearchRequest(
                query="南京一天历史文化景点，少走路",
                lng=118.7921, lat=32.0407,
            )))
        self.assertEqual(response["candidate_count"], 1)
        self.assertEqual(response["places"]["type"], "FeatureCollection")
        self.assertEqual(response["itinerary_preview"]["stops"][0]["properties"]["id"], 1)
        self.assertIn("没有道路网络，无法保证少走路", response["unsupported"])

    def test_nearby_missing_coordinates_is_422(self):
        with patch("backend.app.ai.router.parse_tourism_intent", new=AsyncMock(
            return_value=(fallback_intent("附近的博物馆"), "rule_based")
        )):
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(tourism_search(TourismSearchRequest(query="附近的博物馆")))
        self.assertEqual(cm.exception.status_code, 422)

    def test_mismatched_coordinates_are_422(self):
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(tourism_search(TourismSearchRequest(query="南京景点", lng=118.7)))
        self.assertEqual(cm.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
