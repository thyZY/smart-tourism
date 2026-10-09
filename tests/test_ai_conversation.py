"""No-key conversational itinerary parsing and confirmation-preview safety tests."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.main import app
from backend.app.ai.conversation import parse_chat_edit, propose_edit, rule_operations
from backend.app.ai.router import ConversationalPreviewRequest, conversational_edit_preview


def place(ident, name, category, lon=118.79, lat=32.04):
    return {
        "type": "Feature",
        "properties": {"id": ident, "name": name, "category": category, "address": "南京"},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


CURRENT = [
    place(1, "南京博物院", "博物馆", 118.79),
    place(2, "南京总统府", "历史文化", 118.80),
    place(3, "夫子庙", "历史文化", 118.81),
    place(4, "中山陵", "陵园景区", 118.82),
]
CANDIDATES = CURRENT + [
    place(5, "玄武湖公园", "城市公园", 118.802),
    place(6, "红山森林动物园", "自然景区", 118.825),
    place(7, "江苏省美术馆", "博物馆", 118.805),
]


class ConversationPreviewTests(unittest.TestCase):
    def test_route_registered(self):
        self.assertIn("/api/ai/itinerary/chat/preview", app.openapi()["paths"])

    def test_rule_parses_multiple_contextual_ops(self):
        operations = rule_operations(
            "第二个景点换成自然风光类，但是第三站必须保留",
            [p["properties"]["name"] for p in CURRENT],
        )
        self.assertEqual([op["action"] for op in operations], ["replace", "lock"])
        self.assertEqual(operations[0]["index"], 2)
        self.assertEqual(operations[0]["category"], "自然景区")
        self.assertEqual(operations[1]["index"], 3)

    def test_plan_uses_only_verified_db_pois_and_requires_confirmation(self):
        ops = rule_operations("第二站换成自然风光类，第三站锁定",
                              [p["properties"]["name"] for p in CURRENT])
        preview = propose_edit(
            ops, [1, 2, 3, 4], [], "auto", 8, "09:00", CURRENT, CANDIDATES
        )
        self.assertTrue(preview["needs_confirmation"])
        self.assertEqual(preview["proposed"]["place_ids"], [1, 5, 3, 4])
        self.assertEqual(preview["proposed"]["locked_place_ids"], [3])
        self.assertIn("玄武湖公园", preview["selected_names"])
        self.assertFalse(any(item["properties"]["id"] == 5 for item in CURRENT),
                         "preview must not mutate the existing POI list")
        self.assertTrue(all("仅" not in msg or "预览" in msg
                            for msg in preview["warnings"] if "仅" in msg))

    def test_lock_named_stop_and_refuse_replace(self):
        ops = rule_operations("南京总统府必须保留",
                              [p["properties"]["name"] for p in CURRENT])
        preview = propose_edit(ops, [1, 2, 3, 4], [], "auto", 8, "09:00",
                               CURRENT, CANDIDATES)
        self.assertEqual(preview["proposed"]["locked_place_ids"], [2])
        with self.assertRaisesRegex(ValueError, "锁定景点不能替换"):
            propose_edit([{"action": "replace", "index": 2,
                           "category": "城市公园"}],
                         [1, 2, 3, 4], [2], "auto", 8, "09:00",
                         CURRENT, CANDIDATES)

    def test_reject_conflicting_name_and_ordinal_or_unverifiable_name(self):
        with self.assertRaisesRegex(ValueError, "冲突"):
            propose_edit([{"action": "lock", "index": 2,
                           "name": "夫子庙"}],
                         [1, 2, 3, 4], [], "auto", 8, "09:00",
                         CURRENT, CANDIDATES)
        with self.assertRaisesRegex(ValueError, "完整名称"):
            propose_edit([{"action": "lock", "name": "不存在的景点"}],
                         [1, 2, 3, 4], [], "auto", 8, "09:00",
                         CURRENT, CANDIDATES)

    def test_safeguard_first_stop_and_minimum_three(self):
        with self.assertRaisesRegex(ValueError, "第一站"):
            propose_edit([{"action": "remove", "index": 1}],
                         [1, 2, 3, 4], [], "pedestrian", 8, "09:00",
                         CURRENT, CANDIDATES)
        with self.assertRaisesRegex(ValueError, "至少保留3站"):
            propose_edit([{"action": "remove", "index": 2}],
                         [1, 2, 3], [], "pedestrian", 8, "09:00",
                         CURRENT, CANDIDATES)

    def test_mode_and_budget_followup_without_poi_change(self):
        ops = rule_operations("改成骑行，预算调整为6小时",
                              [p["properties"]["name"] for p in CURRENT])
        self.assertEqual([op["action"] for op in ops], ["mode", "budget"])
        preview = propose_edit(ops, [1, 2, 3], [3], "auto", 8, "09:00",
                               CURRENT[:3], CANDIDATES)
        self.assertEqual(preview["proposed"]["transport_mode"], "bicycle")
        self.assertEqual(preview["proposed"]["budget_hours"], 6)
        self.assertEqual(preview["proposed"]["place_ids"], [1, 2, 3])
        with self.assertRaisesRegex(ValueError, "跨越午夜"):
            propose_edit([{"action": "start", "time": "21:00"}],
                         [1, 2, 3], [], "auto", 8, "09:00",
                         CURRENT[:3], CANDIDATES)

    def test_invalid_untrusted_category_and_hallucinations(self):
        with self.assertRaisesRegex(ValueError, "类别"):
            propose_edit([{"action": "replace", "index": 2,
                           "category": "深空飞行"}],
                         [1, 2, 3], [], "auto", 8, "09:00",
                         CURRENT[:3], CANDIDATES)
        with self.assertRaisesRegex(ValueError, "PostGIS"):
            propose_edit([{"action": "replace", "index": 2,
                           "replacement_name": "虚构景点"}],
                         [1, 2, 3], [], "auto", 8, "09:00",
                         CURRENT[:3], CANDIDATES)

    def test_deepseek_untrusted_output_falls_back_to_rules(self):
        client = type("FakeClient", (), {
            "enabled": True,
            "chat_json": AsyncMock(return_value={
                "operations": [{"action": "destroy_database"}],
            }),
        })()
        ops, mode = asyncio.run(parse_chat_edit(
            "第二站换成公园", [p["properties"]["name"] for p in CURRENT],
            client=client
        ))
        self.assertEqual(mode, "rule_based_fallback")
        self.assertEqual(ops[0]["action"], "replace")

    def test_endpoint_returns_preview_not_replan(self):
        request = ConversationalPreviewRequest(
            message="第二站换成公园，第三站必须保留",
            place_ids=[1, 2, 3, 4], transport_mode="auto",
            budget_hours=8, start_time="09:00",
            history=[{"role": "user", "content": "推荐城市公园"}]
        )
        with patch("backend.app.ai.itinerary_editor.fetch_selected_features",
                   return_value=CURRENT), \
             patch("backend.app.ai.router.query_pois", return_value=CANDIDATES), \
             patch("backend.app.ai.conversation.parse_chat_edit",
                   new=AsyncMock(return_value=(
                       rule_operations(request.message,
                                       [p["properties"]["name"] for p in CURRENT]),
                       "rule_based"))), \
             patch("backend.app.ai.itinerary_editor.replan_edited_itinerary") as forbidden:
            response = asyncio.run(conversational_edit_preview(request))
        self.assertTrue(response["needs_confirmation"])
        self.assertEqual(response["base_state"]["place_ids"], [1, 2, 3, 4])
        self.assertEqual(response["proposed"]["place_ids"][1], 5)
        forbidden.assert_not_called()

    def test_endpoint_rejects_conflicts_and_bad_ids(self):
        with self.assertRaises(ValidationError):
            ConversationalPreviewRequest(message="abc", place_ids=[1, 2])
        with self.assertRaises(HTTPException) as exc:
            asyncio.run(conversational_edit_preview(
                ConversationalPreviewRequest(message="删除", place_ids=[1, 1, 3])
            ))
        self.assertEqual(exc.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
