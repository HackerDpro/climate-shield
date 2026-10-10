import unittest
from unittest.mock import patch

import main
from main import _first_lat_lon, _merge_fire_sources, _merge_gdacs_earthquakes, _merge_reported_events, _parse_firms_csv


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


class FakeFirmsResponse:
    status_code = 200
    text = (
        "latitude,longitude,bright_ti4,frp,confidence,acq_date,acq_time,"
        "satellite,instrument,daynight\n"
        "45,10,320,8.2,n,2026-10-10,0412,N,VIIRS,D\n"
    )


class FakeXmlResponse:
    status_code = 200
    content = b"""<?xml version="1.0"?><rss xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#" xmlns:georss="http://www.georss.org/georss"><channel><item><title>Green flood alert</title><link>https://gdacs.org/test</link><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate><geo:Point> </geo:Point><georss:point>52.0 5.0</georss:point><gdacs:eventtype>FL</gdacs:eventtype><gdacs:eventid>123</gdacs:eventid><gdacs:alertlevel>Green</gdacs:alertlevel><gdacs:country>Netherlands</gdacs:country></item></channel></rss>"""

    def raise_for_status(self):
        return None


class CoordinateParsingTests(unittest.TestCase):
    def test_parses_point(self):
        self.assertEqual(_first_lat_lon([-112.5, 35.2]), (35.2, -112.5))

    def test_parses_nested_polygon_coordinates(self):
        self.assertEqual(_first_lat_lon([[[-112.5, 35.2], [-112.4, 35.3]]]), (35.2, -112.5))

    def test_rejects_empty_invalid_and_out_of_range_coordinates(self):
        self.assertIsNone(_first_lat_lon([]))
        self.assertIsNone(_first_lat_lon(["bad", 20]))
        self.assertIsNone(_first_lat_lon([181, 20]))

    @patch("main._fetch_gdacs_events", return_value=[])
    @patch("main.requests.get", return_value=FakeResponse())
    def test_events_normalize_point_and_polygon_geometries(self, _mock_get, _mock_gdacs):
        result = main.get_nasa_events("floods")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["events"][1]["lat"], 35.3)
        self.assertEqual(result["events"][1]["lon"], -112.4)

    def test_firms_csv_keeps_time_and_sensor_metadata(self):
        csv_text = (
            "latitude,longitude,bright_ti4,frp,confidence,acq_date,acq_time,"
            "satellite,instrument,daynight\n"
            "35.2,-112.5,323.4,12.1,n,2026-10-10,0412,N,VIIRS,D\n"
        )
        points = _parse_firms_csv(csv_text)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["observed_at"], "2026-10-10T04:12:00Z")
        self.assertEqual(points[0]["satellite"], "N")

    def test_firms_merges_only_nearby_recent_incidents(self):
        eonet = [{
            "title": "Reported fire",
            "lat": 35.2,
            "lon": -112.5,
            "observed_at": "2026-10-10T04:00:00Z",
        }]
        firms = [
            {"lat": 35.2005, "lon": -112.5, "observed_at": "2026-10-10T04:12:00Z", "frp": 12},
            {"lat": 35.2, "lon": -112.5, "observed_at": "2026-10-08T04:00:00Z", "frp": 8},
            {"lat": 45.0, "lon": 10.0, "observed_at": "2026-10-10T04:12:00Z", "frp": 5},
        ]
        result = _merge_fire_sources(eonet, firms)
        incident = next(fire for fire in result if fire["event_type"] == "reported_incident")
        detections = [fire for fire in result if fire["event_type"] == "thermal_detection"]
        self.assertEqual(incident["detection_count"], 1)
        self.assertIn("NASA FIRMS", incident["sources"])
        self.assertEqual(len(detections), 2)
        self.assertTrue(all(fire["source"] == "NASA FIRMS" for fire in detections))

    def test_gdacs_merge_keeps_source_and_does_not_merge_stale_or_distant_events(self):
        eonet = [{"title": "Reported flood", "lat": 52.0, "lon": 5.0, "observed_at": "2026-10-10T10:00:00Z", "source": "NASA EONET", "sources": ["NASA EONET"]}]
        gdacs = [
            {"title": "Nearby flood alert", "lat": 52.01, "lon": 5.0, "observed_at": "2026-10-10T11:00:00Z", "source": "GDACS"},
            {"title": "Old flood alert", "lat": 52.0, "lon": 5.0, "observed_at": "2026-10-08T10:00:00Z", "source": "GDACS"},
            {"title": "Distant flood alert", "lat": 55.0, "lon": 10.0, "observed_at": "2026-10-10T11:00:00Z", "source": "GDACS"},
        ]
        result = _merge_reported_events(eonet, gdacs)
        self.assertEqual(len(result), 3)
        self.assertIn("GDACS", result[0]["sources"])
        self.assertEqual(len(result[0]["corroborating_reports"]), 1)

    def test_wildfire_sources_keep_distinct_incidents_five_km_apart(self):
        eonet = [{"title": "Fire A", "lat": 35, "lon": -90, "observed_at": "2026-10-10T10:00:00Z", "source": "NASA EONET"}]
        gdacs = [{"title": "Fire B", "lat": 35, "lon": -89.94, "observed_at": "2026-10-10T10:00:00Z", "source": "GDACS"}]
        result = _merge_reported_events(eonet, gdacs, max_distance_km=5)
        self.assertEqual(len(result), 2)
        self.assertEqual([event["source"] for event in result], ["NASA EONET", "GDACS"])

    @patch("main.requests.get", return_value=FakeXmlResponse())
    def test_gdacs_rss_parser_normalizes_open_alerts(self, _mock_get):
        result = main._fetch_gdacs_events({"FL"})
        cached_result = main._fetch_gdacs_events({"FL"})
        self.assertEqual(len(result), 1)
        self.assertEqual(len(cached_result), 1)
        self.assertEqual(_mock_get.call_count, 1)
        self.assertEqual((result[0]["lat"], result[0]["lon"]), (52.0, 5.0))
        self.assertEqual(result[0]["source"], "GDACS")
        self.assertEqual(result[0]["alert_level"], "Green")

    def test_gdacs_earthquake_matching_preserves_usgs_and_standalone_alerts(self):
        usgs = {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0, 10]},
            "properties": {"mag": 5.2, "title": "USGS quake", "time": 1791626400000, "sources": ",us,"},
        }]}
        gdacs = [
            {"id": "near", "title": "Magnitude 5.2M", "lat": 52.01, "lon": 5.0, "observed_at": "2026-10-10T11:00:00Z", "alert_level": "Green"},
            {"id": "far", "title": "Magnitude 6M", "lat": 10.0, "lon": 20.0, "observed_at": "2026-10-10T11:00:00Z"},
            {"id": "stale", "title": "Magnitude 5M", "lat": 52.0, "lon": 5.0, "observed_at": "2026-10-08T10:00:00Z"},
            {"id": "unknown-mag", "title": "Earthquake warning", "lat": -20.0, "lon": 30.0, "observed_at": "2026-10-10T11:00:00Z"},
        ]
        result = _merge_gdacs_earthquakes(usgs, gdacs)
        self.assertEqual(len(result["features"]), 4)
        self.assertEqual(result["features"][0]["properties"]["sources"], ["USGS", "GDACS"])
        unknown_magnitude = result["features"][-1]["properties"]["mag"]
        self.assertIsNone(unknown_magnitude)
        self.assertEqual(result["features"][0]["properties"]["usgs_source_codes"], ",us,")
        self.assertEqual(result["metadata"]["count"] if "metadata" in result else 3, 3)

    @patch("main._fetch_gdacs_events", return_value=[])
    @patch("main.requests.get")
    @patch("main.FIRMS_KEY", "test-key")
    def test_fires_endpoint_returns_incidents_and_labeled_thermal_clusters(self, _mock_get, _mock_gdacs):
        _mock_get.side_effect = lambda url, **_kwargs: FakeResponse() if "eonet" in url else FakeFirmsResponse()
        result = main.get_active_fires()
        self.assertEqual(result["source_status"]["NASA EONET"], "success")
        self.assertEqual(result["thermal_detection_count"], 1)
        self.assertTrue(any(fire["event_type"] == "reported_incident" for fire in result["fires"]))
        self.assertTrue(any(fire["event_type"] == "thermal_detection" for fire in result["fires"]))

    @patch("main._fetch_gdacs_events", return_value=[{"id": "gdacs-fire", "title": "GDACS wildfire", "lat": 10, "lon": 20, "source": "GDACS", "sources": ["GDACS"], "event_type": "WF", "observed_at": "2026-10-10T10:00:00Z"}])
    @patch("main.requests.get", side_effect=RuntimeError("EONET offline"))
    @patch("main.FIRMS_KEY", None)
    def test_fires_endpoint_uses_gdacs_when_eonet_is_offline(self, _mock_get, _mock_gdacs):
        result = main.get_active_fires()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source_status"]["NASA EONET"], "error")
        self.assertTrue(any(fire["source"] == "GDACS" for fire in result["fires"]))

    @patch("main._fetch_gdacs_events", return_value=[{"title": "GDACS flood", "lat": 10.0, "lon": 20.0, "source": "GDACS", "observed_at": "2026-10-10T10:00:00Z"}])
    @patch("main.requests.get", return_value=FakeResponse())
    def test_events_endpoint_returns_supplemental_source_records(self, _mock_get, _mock_gdacs):
        result = main.get_nasa_events("floods")
        self.assertEqual(result["total"], len(result["events"]))
        self.assertTrue(any(event["source"] == "GDACS" for event in result["events"]))

    @patch("main._fetch_gdacs_events", return_value=[{"title": "GDACS flood", "lat": 10.0, "lon": 20.0, "source": "GDACS", "observed_at": "2026-10-10T10:00:00Z"}])
    @patch("main.requests.get", side_effect=RuntimeError("EONET offline"))
    def test_event_endpoint_falls_back_to_gdacs(self, _mock_get, _mock_gdacs):
        result = main.get_nasa_events("floods")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source_status"]["NASA EONET"], "error")
        self.assertEqual(result["events"][0]["source"], "GDACS")


if __name__ == "__main__":
    unittest.main()