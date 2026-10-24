"""Request validation for GIS endpoints, independent of the live database."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient
from app.main import app


class SpatialParameterValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.connection = patch("app.main.get_db_connection", side_effect=AssertionError("invalid input reached database"))
        self.connection.start()
        self.addCleanup(self.connection.stop)

    def assert_invalid(self, path, params):
        response = self.client.get(path, params=params)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("detail", response.json())

    def test_nearby_rejects_out_of_range_coordinates(self):
        for params in (
            {"lng": 181, "lat": 32},
            {"lng": 118, "lat": -91},
        ):
            with self.subTest(params=params):
                self.assert_invalid("/api/places/nearby", params)

    def test_nearby_rejects_non_finite_coordinates_and_radius(self):
        for params in (
            {"lng": "nan", "lat": 32},
            {"lng": 118, "lat": "inf"},
            {"lng": 118, "lat": 32, "radius": "nan"},
            {"lng": 118, "lat": 32, "radius": "inf"},
        ):
            with self.subTest(params=params):
                self.assert_invalid("/api/places/nearby", params)

    def test_nearby_rejects_negative_radius(self):
        self.assert_invalid("/api/places/nearby", {"lng": 118, "lat": 32, "radius": -1})

    def test_bbox_rejects_partial_bounds(self):
        self.assert_invalid("/api/places", {"min_lng": 118, "min_lat": 32})

    def test_bbox_rejects_invalid_coordinates_and_non_finite_values(self):
        for params in (
            {"min_lng": 181, "min_lat": 32, "max_lng": 119, "max_lat": 33},
            {"min_lng": 118, "min_lat": 32, "max_lng": 119, "max_lat": 91},
            {"min_lng": "nan", "min_lat": 32, "max_lng": 119, "max_lat": 33},
        ):
            with self.subTest(params=params):
                self.assert_invalid("/api/places", params)

    def test_bbox_rejects_reversed_or_degenerate_bounds(self):
        for params in (
            {"min_lng": 119, "min_lat": 32, "max_lng": 118, "max_lat": 33},
            {"min_lng": 118, "min_lat": 33, "max_lng": 119, "max_lat": 32},
            {"min_lng": 118, "min_lat": 32, "max_lng": 118, "max_lat": 33},
        ):
            with self.subTest(params=params):
                self.assert_invalid("/api/places", params)


if __name__ == "__main__":
    unittest.main()
