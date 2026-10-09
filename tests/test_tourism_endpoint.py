"""Tourism route tests against a mocked PostgreSQL connection."""
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from backend.app.main import app
from backend.app.tourism_routes import get_tourism_place
from backend.app.tourism_repository import fetch_tourism_place


class TourismEndpointTests(unittest.TestCase):
    def test_router_is_mounted(self):
        paths = set(app.openapi()["paths"])
        self.assertIn("/api/tourism/places/{place_id}", paths)
        self.assertIn("/api/tourism/card", paths)
        self.assertIn("/api/places/itinerary-preview", paths)

    def test_real_database_row_is_used(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            1, "南京博物院", "博物馆", "南京市",
            "150", "true", ["历史", "展览"], "展览场馆。", ""
        )
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch("backend.app.tourism_routes.get_db_connection", return_value=connection):
            card = get_tourism_place(1)

        self.assertEqual(card["name"], "南京博物院")
        self.assertEqual(card["visit_duration"], 150)
        self.assertTrue(card["indoor"])
        self.assertEqual(card["tags"], ["历史", "展览"])
        self.assertEqual(cursor.execute.call_args.args[1], (1,))
        connection.close.assert_called_once()

    def test_missing_poi_returns_404_and_closes_connection(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch("backend.app.tourism_routes.get_db_connection", return_value=connection):
            with self.assertRaises(HTTPException) as ctx:
                get_tourism_place(999999)
        self.assertEqual(ctx.exception.status_code, 404)
        connection.close.assert_called_once()

    def test_invalid_id_does_not_query_database(self):
        with patch("backend.app.tourism_routes.get_db_connection") as connection:
            with self.assertRaises(HTTPException) as ctx:
                get_tourism_place(0)
        self.assertEqual(ctx.exception.status_code, 422)
        connection.assert_not_called()

    def test_legacy_row_without_metadata_is_supported(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (3, "中山陵", "陵园景区", None, None, None, None, None, None)
        place = fetch_tourism_place(cursor, 3)
        self.assertIsNone(place["visit_duration"])
        self.assertIsNone(place["indoor"])
        self.assertEqual(place["tags"], [])


if __name__ == "__main__":
    unittest.main()
