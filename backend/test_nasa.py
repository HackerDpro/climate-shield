import unittest
from unittest.mock import patch

import main
from main import _first_lat_lon


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "events": [
                {"title": "Point event", "geometry": [{"coordinates": [-112.5, 35.2]}]},
                {"title": "Polygon event", "geometry": [{"coordinates": [[[-112.4, 35.3], [-112.3, 35.4]]]}]},
                {"title": "Invalid event", "geometry": [{"coordinates": []}]},
                {"title": "Missing geometry", "geometry": None},
            ]
        }


class CoordinateParsingTests(unittest.TestCase):
    def test_parses_point(self):
        self.assertEqual(_first_lat_lon([-112.5, 35.2]), (35.2, -112.5))

    def test_parses_nested_polygon_coordinates(self):
        self.assertEqual(_first_lat_lon([[[-112.5, 35.2], [-112.4, 35.3]]]), (35.2, -112.5))

    def test_rejects_empty_invalid_and_out_of_range_coordinates(self):
        self.assertIsNone(_first_lat_lon([]))
        self.assertIsNone(_first_lat_lon(["bad", 20]))
        self.assertIsNone(_first_lat_lon([181, 20]))

    @patch("main.requests.get", return_value=FakeResponse())
    def test_events_normalize_point_and_polygon_geometries(self, _mock_get):
        result = main.get_nasa_events("floods")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["events"][1]["lat"], 35.3)
        self.assertEqual(result["events"][1]["lon"], -112.4)


if __name__ == "__main__":
    unittest.main()