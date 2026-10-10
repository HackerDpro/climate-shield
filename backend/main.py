from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import math
import csv
import re
import time
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from io import StringIO
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔒 SECURE SERVER ENVIRONMENT VARIABLES
OWM_KEY = os.getenv("OWM_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
FIRMS_KEY = os.getenv("FIRMS_KEY") 
_GDACS_CACHE_LOCK = threading.Lock()
_GDACS_CACHE = {"expires_at": 0, "events": []}


def _first_lat_lon(coordinates):
    while isinstance(coordinates, list) and coordinates and isinstance(coordinates[0], list):
        coordinates = coordinates[0]
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    try:
        lon, lat = float(coordinates[0]), float(coordinates[1])
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _first_geometry_lat_lon(geometry):
    if not isinstance(geometry, list):
        return None
    for item in geometry:
        if isinstance(item, dict):
            point = _first_lat_lon(item.get("coordinates"))
            if point:
                return point
    return None


def _latest_geometry(geometry):
    candidates = []
    for item in geometry or []:
        if not isinstance(item, dict):
            continue
        point = _first_lat_lon(item.get("coordinates"))
        if point:
            candidates.append((str(item.get("date") or ""), point))
    return max(candidates, key=lambda candidate: candidate[0]) if candidates else None


def _parse_firms_timestamp(date, acquisition_time):
    try:
        time_text = str(acquisition_time or "0").strip().zfill(4)
        observed = datetime.strptime(f"{date} {time_text}", "%Y-%m-%d %H%M")
        return observed.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return None


def _parse_firms_csv(csv_text, limit=2000):
    points = []
    for row in csv.DictReader(StringIO(csv_text)):
        if len(points) >= limit:
            break
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            brightness = float(row["bright_ti4"])
            frp = float(row["frp"])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            points.append({
                "lat": lat,
                "lon": lon,
                "brightness": brightness,
                "frp": frp,
                "confidence": row.get("confidence", "unknown"),
                "observed_at": _parse_firms_timestamp(row.get("acq_date"), row.get("acq_time")),
                "satellite": row.get("satellite", "unknown"),
                "instrument": row.get("instrument", "VIIRS"),
                "daynight": row.get("daynight", "unknown"),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return points


def _distance_km(first, second):
    lat1, lon1 = math.radians(first["lat"]), math.radians(first["lon"])
    lat2, lon2 = math.radians(second["lat"]), math.radians(second["lon"])
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _timestamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except (AttributeError, TypeError, ValueError):
        return None


def _xml_child_text(element, local_name):
    for child in element:
        text = (child.text or "").strip()
        if child.tag.rsplit("}", 1)[-1].lower() == local_name.lower() and text:
            return text
    return ""


def _fetch_gdacs_events(event_types):
    if not event_types:
        return []
    with _GDACS_CACHE_LOCK:
        now = time.monotonic()
        if _GDACS_CACHE["expires_at"] > now:
            all_events = _GDACS_CACHE["events"]
        else:
            try:
                response = requests.get("https://www.gdacs.org/xml/rss.xml", timeout=8)
                response.raise_for_status()
                root = ET.fromstring(response.content)
                all_events = []
                for item in root.findall("./channel/item"):
                    event_type = _xml_child_text(item, "eventtype").upper()
                    point_text = _xml_child_text(item, "point").split()
                    if len(point_text) < 2:
                        continue
                    try:
                        lat, lon = float(point_text[0]), float(point_text[1])
                    except ValueError:
                        continue
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    try:
                        observed_at = parsedate_to_datetime(item.findtext("pubDate", default="")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    except (AttributeError, TypeError, ValueError, OverflowError):
                        observed_at = None
                    all_events.append({
                        "id": _xml_child_text(item, "eventid") or item.findtext("guid"),
                        "title": item.findtext("title", default="GDACS event"),
                        "lat": lat,
                        "lon": lon,
                        "observed_at": observed_at,
                        "source": "GDACS",
                        "sources": ["GDACS"],
                        "event_type": event_type,
                        "category": _xml_child_text(item, "eventname") or event_type,
                        "country": _xml_child_text(item, "country"),
                        "alert_level": _xml_child_text(item, "alertlevel"),
                        "link": item.findtext("link"),
                    })
                _GDACS_CACHE["events"] = all_events
                _GDACS_CACHE["expires_at"] = now + 300
            except Exception as e:
                print(f"[API ERROR] Fetching GDACS events: {e}")
                all_events = _GDACS_CACHE["events"]

        return [dict(event) for event in all_events if event["event_type"] in event_types]


def _merge_reported_events(primary_events, supplemental_events, max_distance_km=25):
    merged = list(primary_events)
    for event in merged:
        event.setdefault("sources", [event.get("source", "NASA EONET")])
        event.setdefault("corroborating_reports", [])
    for supplemental in supplemental_events:
        event_time = _timestamp(supplemental.get("observed_at"))
        matches = []
        if event_time:
            for primary in merged:
                primary_time = _timestamp(primary.get("observed_at"))
                if not primary_time or abs((event_time - primary_time).total_seconds()) > 24 * 60 * 60:
                    continue
                distance = _distance_km(primary, supplemental)
                if distance <= max_distance_km:
                    matches.append((distance, primary))
        if matches:
            _, primary = min(matches, key=lambda match: match[0])
            if supplemental.get("source") not in primary["sources"]:
                primary["sources"].append(supplemental.get("source", "Additional source"))
            primary["corroborating_reports"].append(supplemental)
        else:
            event_copy = dict(supplemental)
            event_copy.setdefault("corroborating_reports", [])
            merged.append(event_copy)
    return merged


def _merge_gdacs_earthquakes(geojson, gdacs_events):
    features = list(geojson.get("features") or [])
    for feature in features:
        properties = feature.setdefault("properties", {})
        raw_sources = properties.get("sources")
        if isinstance(raw_sources, list):
            properties["sources"] = list(raw_sources)
            if "USGS" not in properties["sources"]:
                properties["sources"].append("USGS")
        else:
            if raw_sources:
                properties["usgs_source_codes"] = raw_sources
            properties["sources"] = ["USGS"]

    for event in gdacs_events:
        event_time = _timestamp(event.get("observed_at"))
        if not event_time:
            continue
        matches = []
        for feature in features:
            coordinates = (feature.get("geometry") or {}).get("coordinates", [])
            properties = feature.get("properties", {})
            usgs_time = properties.get("time")
            if len(coordinates) < 2 or usgs_time is None:
                continue
            try:
                usgs_observed = datetime.fromtimestamp(float(usgs_time) / 1000, timezone.utc)
            except (TypeError, ValueError, OSError, OverflowError):
                continue
            if abs((event_time - usgs_observed).total_seconds()) > 6 * 60 * 60:
                continue
            distance = _distance_km(
                {"lat": coordinates[1], "lon": coordinates[0]}, event
            )
            if distance <= 50:
                matches.append((distance, feature))

        if matches:
            _, feature = min(matches, key=lambda match: match[0])
            properties = feature["properties"]
            if "GDACS" not in properties["sources"]:
                properties["sources"].append("GDACS")
            properties["gdacs_alert_level"] = event.get("alert_level")
            properties["gdacs_event_id"] = event.get("id")
            continue

        magnitude_match = re.search(r"magnitude\s*([\d.]+)\s*m", event.get("title", ""), re.IGNORECASE)
        magnitude = float(magnitude_match.group(1)) if magnitude_match else None
        features.append({
            "type": "Feature",
            "id": f"GDACS_{event.get('id') or len(features)}",
            "geometry": {"type": "Point", "coordinates": [event["lon"], event["lat"], 0]},
            "properties": {
                "mag": magnitude,
                "title": event.get("title", "GDACS earthquake"),
                "place": event.get("country") or "Location reported by GDACS",
                "time": int(event_time.timestamp() * 1000),
                "sources": ["GDACS"],
                "alert_level": event.get("alert_level"),
            },
        })

    geojson["features"] = features
    if isinstance(geojson.get("metadata"), dict):
        geojson["metadata"]["count"] = len(features)
    return geojson


def _merge_fire_sources(eonet_fires, firms_points):
    eonet_cells = defaultdict(list)
    incident_counts = Counter()
    for fire in eonet_fires:
        fire.setdefault("source", "NASA EONET")
        fire.setdefault("sources", ["NASA EONET"])
        fire.setdefault("event_type", "reported_incident")
        fire.setdefault("satellite_observations", [])
        cell = (math.floor(fire["lat"] / 0.02), math.floor(fire["lon"] / 0.02))
        eonet_cells[cell].append(fire)
        incident_counts[(round(fire["lon"]), round(fire["lat"]))] += 1

    unmatched_cells = defaultdict(list)
    for point in firms_points:
        observed_at = _timestamp(point.get("observed_at"))
        point_cell = (math.floor(point["lat"] / 0.02), math.floor(point["lon"] / 0.02))
        candidates = []
        if observed_at:
            for latitude_cell in range(point_cell[0] - 1, point_cell[0] + 2):
                for longitude_cell in range(point_cell[1] - 1, point_cell[1] + 2):
                    candidates.extend(eonet_cells.get((latitude_cell, longitude_cell), []))

        matches = []
        for fire in candidates:
            event_time = _timestamp(fire.get("observed_at"))
            if not event_time or abs((observed_at - event_time).total_seconds()) > 24 * 60 * 60:
                continue
            distance = _distance_km(fire, point)
            if distance <= 0.75:
                matches.append((distance, fire))

        if matches:
            _, fire = min(matches, key=lambda match: match[0])
            fire["satellite_observations"].append(point)
            if "NASA FIRMS" not in fire["sources"]:
                fire["sources"].append("NASA FIRMS")
        else:
            group_key = (
                math.floor(point["lat"] / 0.01),
                math.floor(point["lon"] / 0.01),
                (point.get("observed_at") or "unknown")[:10],
            )
            unmatched_cells[group_key].append(point)

    thermal_clusters = []
    for observations in unmatched_cells.values():
        count = len(observations)
        thermal_clusters.append({
            "title": f"Satellite heat detection cluster ({count})",
            "lat": sum(point["lat"] for point in observations) / count,
            "lon": sum(point["lon"] for point in observations) / count,
            "density_score": count,
            "source": "NASA FIRMS",
            "sources": ["NASA FIRMS"],
            "event_type": "thermal_detection",
            "observed_at": max((point.get("observed_at") or "" for point in observations), default=None) or None,
            "detection_count": count,
            "satellite_observations": observations,
        })

    for fire in eonet_fires:
        fire["density_score"] = incident_counts[(round(fire["lon"]), round(fire["lat"]))]
        fire["detection_count"] = len(fire["satellite_observations"])

    return sorted(
        eonet_fires + thermal_clusters,
        key=lambda fire: (fire["event_type"] == "thermal_detection", -fire["density_score"]),
    )


@app.get("/api/satellites")
def get_satellite_sources():
    """Fetches ACTUAL live satellite sensor sources from NASA EONET"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/sources"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            sources = res.json().get("sources", [])
            return {"status": "success", "instruments": [s['id'] for s in sources[:8]]}
    except Exception as e:
        print(f"[API ERROR] Fetches Satellite Sources: {e}")
    return {"status": "error", "message": "NASA EONET uplink failed."}

@app.get("/api/wind")
def get_wind_data(lat: float, lon: float):
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "ms",
            },
            timeout=5,
        )
        response.raise_for_status()
        wind = response.json().get("current", {})
        return {
            "speed": float(wind["wind_speed_10m"]),
            "direction": float(wind["wind_direction_10m"]),
        }
    except Exception as e:
        print(f"[API ERROR] Fetching Wind Data: {e}")
    return {"speed": 0, "direction": 0, "error": "Wind data unavailable"}

@app.get("/api/air_quality")
def get_air_quality(lat: float, lon: float):
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,carbon_monoxide"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json().get('current', {})
            return {"status": "success", "pm2_5": data.get("pm2_5", 0), "co": data.get("carbon_monoxide", 0)}
    except Exception as e:
        print(f"[API ERROR] Fetching Air Quality: {e}")
    return {"status": "offline", "pm2_5": "N/A", "co": "N/A"}

@app.get("/api/analyze_terrain")
def analyze_terrain(lat: float, lon: float, wind_dir: float):
    offset = 0.01  
    lats = f"{lat},{lat+offset},{lat-offset},{lat},{lat}"
    lons = f"{lon},{lon},{lon},{lon+offset},{lon-offset}"
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            elevations = response.json().get('elevation', [])
            if len(elevations) == 5:
                center, north, south, east, west = elevations
                slope_n = north - center
                slope_e = east - center
                aspect_rad = math.atan2(slope_e, slope_n)
                aspect_deg = (math.degrees(aspect_rad) + 360) % 360
                max_slope = math.sqrt(slope_n**2 + slope_e**2)
                angle_diff = abs((wind_dir - aspect_deg + 180) % 360 - 180)
                
                multiplier = 1.0
                terrain_status = "FLAT TERRAIN / NO INFLUENCE"
                
                if max_slope > 10: 
                    if angle_diff < 45:
                        multiplier = 1.8 + (max_slope / 100) 
                        terrain_status = f"CRITICAL UPHILL ALIGNMENT (+{int((multiplier-1)*100)}% SPREAD)"
                    elif angle_diff > 135:
                        multiplier = 0.6 
                        terrain_status = "DOWNHILL RESISTANCE (SPREAD REDUCED)"
                    else:
                        terrain_status = "CROSS-SLOPE WIND (LATERAL SPREAD)"
                return {
                    "status": "success",
                    "elevation_meters": round(center, 1),
                    "terrain_status": terrain_status,
                    "spread_multiplier": multiplier
                }
    except Exception as e:
        print(f"[API ERROR] Analyzing Terrain: {e}")
    return {"status": "fallback", "elevation_meters": "Unknown", "terrain_status": "TERRAIN DATA OFFLINE", "spread_multiplier": 1.0}

@app.get("/api/fires")
def get_active_fires():
    """Core wildfire endpoint with spatial density grouping"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open"
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            eonet_future = executor.submit(requests.get, url, timeout=10)
            gdacs_future = executor.submit(_fetch_gdacs_events, {"WF"})
            firms_future = executor.submit(get_raw_firms)

            clean_fires = []
            eonet_status = "error"
            try:
                response = eonet_future.result()
                if response.status_code == 200:
                    eonet_status = "success"
                    for fire in response.json().get("events") or []:
                        geometry = _latest_geometry(fire.get("geometry"))
                        if not geometry:
                            continue
                        observed_at, (lat, lon) = geometry
                        clean_fires.append({
                            "id": fire.get("id"),
                            "title": (fire.get("title") or "Unknown Wildfire").replace("Wildfire", "").strip(),
                            "lat": lat,
                            "lon": lon,
                            "observed_at": observed_at or None,
                            "source": "NASA EONET",
                            "sources": ["NASA EONET"],
                            "event_type": "reported_incident",
                        })
            except Exception as e:
                print(f"[API ERROR] Fetching EONET fires: {e}")

            gdacs_fires = gdacs_future.result()
            firms_result = firms_future.result()

        firms_points = firms_result.get("data", []) if firms_result.get("status") == "success" else []
        if eonet_status != "success" and not gdacs_fires and not firms_points:
            return {"status": "error", "message": "No wildfire data source is currently available."}

        reported_fires = _merge_reported_events(clean_fires, gdacs_fires, max_distance_km=5)
        unified_fires = _merge_fire_sources(reported_fires, firms_points)
        incident_count = sum(fire["event_type"] != "thermal_detection" for fire in unified_fires)
        thermal_count = sum(fire["event_type"] == "thermal_detection" for fire in unified_fires)
        matched_firms_count = sum(fire["detection_count"] for fire in unified_fires if fire["event_type"] != "thermal_detection")
        return {
            "status": "success",
            "total_global": len(unified_fires),
            "incident_count": incident_count,
            "thermal_cluster_count": thermal_count,
            "thermal_detection_count": len(firms_points),
            "matched_thermal_detection_count": matched_firms_count,
            "source_status": {
                "NASA EONET": eonet_status,
                "NASA FIRMS": firms_result.get("status", "error"),
                "GDACS": "success" if gdacs_fires else "empty_or_unavailable",
            },
            "fires": unified_fires,
        }
    except Exception as e:
        print(f"[API ERROR] Fetching Fires: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/events")
def get_nasa_events(category: str):
    """Combines NASA EONET events with matching GDACS alerts when available."""
    url = f"https://eonet.gsfc.nasa.gov/api/v3/events?category={category}&status=open"
    gdacs_codes = {
        "severeStorms": {"TC"},
        "floods": {"FL"},
        "wildfires": {"WF"},
        "volcanoes": {"VO"},
        "drought": {"DR"},
    }
    clean_events = []
    eonet_status = "error"
    event_types = gdacs_codes.get(category, set())
    with ThreadPoolExecutor(max_workers=2) as executor:
        eonet_future = executor.submit(requests.get, url, timeout=10)
        gdacs_future = executor.submit(_fetch_gdacs_events, event_types)
        try:
            response = eonet_future.result()
            if response.status_code == 200:
                eonet_status = "success"
                for event in response.json().get("events") or []:
                    geometry = _latest_geometry(event.get("geometry"))
                    if not geometry:
                        continue
                    observed_at, (lat, lon) = geometry
                    clean_events.append({
                        "id": event.get("id"),
                        "title": event.get("title", "Unknown Event"),
                        "lat": lat,
                        "lon": lon,
                        "category": category,
                        "observed_at": observed_at or None,
                        "source": "NASA EONET",
                        "sources": ["NASA EONET"],
                    })
        except Exception as e:
            print(f"[API ERROR] Fetching NASA Events for {category}: {e}")
        gdacs_events = gdacs_future.result()

    merged_events = _merge_reported_events(clean_events, gdacs_events)
    for event in merged_events:
        event.setdefault("category", category)
    if not merged_events and eonet_status != "success":
        return {"status": "error", "message": "No event source is currently available."}
    return {
        "status": "success",
        "total": len(merged_events),
        "events": merged_events,
        "source_status": {
            "NASA EONET": eonet_status,
            "GDACS": "success" if gdacs_events else "empty_or_unavailable",
        },
    }

@app.get("/api/ignition_risk")
def calculate_ignition_risk(lat: float, lon: float):
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
                "hourly": "soil_moisture_0_to_7cm",
                "forecast_days": 1,
            },
            timeout=5,
        )
        response.raise_for_status()
        weather_data = response.json()
        current = weather_data["current"]
        temp_c = float(current["temperature_2m"])
        humidity = float(current["relative_humidity_2m"])
        wind_speed_kmh = float(current["wind_speed_10m"])
        precipitation = float(current.get("precipitation", 0))

        hourly = weather_data.get("hourly", {})
        times = hourly.get("time", [])
        moisture_values = hourly.get("soil_moisture_0_to_7cm", [])
        current_time = current.get("time")
        try:
            soil_index = times.index(current_time)
            soil_moisture = float(moisture_values[soil_index])
        except (ValueError, IndexError):
            soil_moisture = float(moisture_values[0]) if moisture_values else 0.5

        temp_factor = min(max(temp_c, 0) / 40.0, 1.0) * 0.35
        wind_factor = min(max(wind_speed_kmh, 0) / 50.0, 1.0) * 0.25
        dryness_factor = (100 - min(max(humidity, 0), 100)) / 100.0 * 0.20
        soil_dryness_factor = max(0, (0.5 - soil_moisture) * 2) * 0.20

        raw_probability = temp_factor + wind_factor + dryness_factor + soil_dryness_factor
        if precipitation > 2.0: raw_probability *= 0.1
        ignition_risk_percent = round(raw_probability * 100, 1)

        status = "CRITICAL IGNITION WARNING" if ignition_risk_percent >= 75 else "ELEVATED RISK" if ignition_risk_percent >= 50 else "NOMINAL"
        return {"status": "success", "lat": lat, "lon": lon, "ignition_probability": f"{ignition_risk_percent}%", "telemetry": {"temp_c": temp_c, "humidity": f"{humidity}%", "wind_kmh": round(wind_speed_kmh, 1), "soil_moisture_vsw": soil_moisture}, "ai_status": status}
    except Exception as e:
        print(f"[API ERROR] Calculating Ignition Risk: {e}")
        return {"status": "error", "error": f"Failed to calculate risk: {str(e)}"}

@app.get("/api/tle")
def get_satellite_orbits():
    """PHASE 3: Fetches Two-Line Elements."""
    url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return {"status": "success", "tle_data": res.text}
        return {"status": "error", "message": "CelesTrak rejected connection."}
    except Exception as e:
        print(f"[API ERROR] Fetching TLE: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/biomass")
def get_biomass_data(lat: float, lon: float):
    """PHASE 5: Fuel Moisture & Predictive Bio-Mass Matrix"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_moisture_0_to_7cm,evapotranspiration,vapor_pressure_deficit&forecast_days=1"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json().get('hourly', {})
            
            sm = data.get("soil_moisture_0_to_7cm", [0.5])[0]
            et = data.get("evapotranspiration", [0])[0]
            vpd = data.get("vapor_pressure_deficit", [0])[0]
            
            drought_index = max(0, min(100, ((0.5 - sm) * 100) + (vpd * 10)))
            
            health_status = "HEALTHY / MOIST"
            if drought_index > 75: health_status = "CRITICAL DROUGHT (TINDERBOX)"
            elif drought_index > 50: health_status = "ELEVATED DRYNESS"

            return {
                "status": "success",
                "soil_moisture": sm,
                "evapotranspiration": et,
                "vpd": vpd,
                "drought_index": round(drought_index, 1),
                "health_status": health_status
            }
        return {"status": "error", "message": "Bio-Mass telemetry offline."}
    except Exception as e:
        print(f"[API ERROR] Fetching Biomass: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/earthquakes")
def get_earthquakes():
    """Combines the USGS earthquake feed with distinct GDACS alerts."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
    geojson = {"type": "FeatureCollection", "features": []}
    usgs_status = "error"
    with ThreadPoolExecutor(max_workers=2) as executor:
        usgs_future = executor.submit(requests.get, url, timeout=5)
        gdacs_future = executor.submit(_fetch_gdacs_events, {"EQ"})
        try:
            response = usgs_future.result()
            if response.status_code == 200:
                geojson = response.json()
                usgs_status = "success"
        except Exception as e:
            print(f"[API ERROR] Fetching Earthquakes: {e}")
        gdacs_events = gdacs_future.result()
    merged = _merge_gdacs_earthquakes(geojson, gdacs_events)
    if not merged["features"]:
        return {"status": "error", "message": "No earthquake source is currently available."}
    merged["source_status"] = {
        "USGS": usgs_status,
        "GDACS": "success" if gdacs_events else "empty_or_unavailable",
    }
    return merged

@app.get("/api/volcanoes")
def get_volcanoes():
    """Fetches NASA EONET Volcanic Eruptions & Ash Advisories"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events?category=volcanoes&status=open"
    try:
        res = requests.get(url, timeout=5)
        return res.json()
    except Exception as e:
        print(f"[API ERROR] Fetching Volcanoes: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/raw_firms")
def get_raw_firms():
    """Parses Raw NASA MODAPS Multi-Spectral Data (Requires FIRMS_KEY)"""
    if not FIRMS_KEY:
        return {"status": "error", "message": "Missing NASA FIRMS Key in Render Environment."}
    
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}/VIIRS_SNPP_NRT/world/1"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return {"status": "error", "message": "FIRMS API rejected connection."}
        
        thermal_points = _parse_firms_csv(res.text)
        return {"status": "success", "data": thermal_points}
    except Exception as e:
        print(f"[API ERROR] Fetching Raw FIRMS: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/co2_history")
def get_co2_history():
    """Fetches genuine historic planetary CO2 data from NOAA/Mauna Loa"""
    url = "https://global-warming.org/api/co2-api"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return {"status": "success", "data": data.get("co2", [])}
        return {"status": "error", "message": "NOAA CO2 Observatory rejected connection."}
    except Exception as e:
        print(f"[API ERROR] Fetching CO2 History: {e}")
        return {"status": "error", "message": str(e)}


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)