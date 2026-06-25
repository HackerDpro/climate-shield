from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import math
import csv
from io import StringIO
from collections import Counter
from dotenv import load_dotenv

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

@app.get("/api/satellites")
def get_satellite_sources():
    """Fetches ACTUAL live satellite sensor sources from NASA EONET"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/sources"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            sources = res.json().get("sources", [])
            return {"status": "success", "instruments": [s['id'] for s in sources[:8]]}
    except Exception:
        pass
    return {"status": "error", "message": "NASA EONET uplink failed."}

@app.get("/api/wind")
def get_wind_data(lat: float, lon: float):
    if not OWM_KEY:
        return {"speed": 0, "direction": 0, "error": "Missing OWM API Key"}
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OWM_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            wind = data.get('wind', {'speed': 0, 'deg': 0})
            return {"speed": wind.get('speed', 0), "direction": wind.get('deg', 0)}
    except Exception:
        pass
    return {"speed": 0, "direction": 0}

@app.get("/api/air_quality")
def get_air_quality(lat: float, lon: float):
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,carbon_monoxide"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json().get('current', {})
            return {"status": "success", "pm2_5": data.get("pm2_5", 0), "co": data.get("carbon_monoxide", 0)}
    except Exception:
        pass
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
    except Exception:
        pass
    return {"status": "fallback", "elevation_meters": "Unknown", "terrain_status": "TERRAIN DATA OFFLINE", "spread_multiplier": 1.0}

@app.get("/api/fires")
def get_active_fires():
    """Core wildfire endpoint with spatial density grouping"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            fires = data.get('events', [])
            clean_fires = []
            for fire in fires:
                title = fire.get('title', 'Unknown Wildfire')
                geometry = fire.get('geometry', [])
                if not geometry: continue
                coords = geometry[0].get('coordinates', [])
                if len(coords) < 2: continue
                lon, lat = coords[0], coords[1]
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    clean_fires.append({"title": title.replace("Wildfire", "").strip(), "lat": lat, "lon": lon})
            
            grid_counter = Counter()
            for fire in clean_fires:
                grid_x, grid_y = round(fire['lon'] / 1.0), round(fire['lat'] / 1.0)
                grid_counter[(grid_x, grid_y)] += 1
            for fire in clean_fires:
                grid_x, grid_y = round(fire['lon'] / 1.0), round(fire['lat'] / 1.0)
                fire['density_score'] = grid_counter[(grid_x, grid_y)]
            clean_fires.sort(key=lambda x: x['density_score'], reverse=True)
            return {"status": "success", "total_global": len(clean_fires), "fires": clean_fires}
        return {"status": "error", "message": "NASA uplink rejected."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/events")
def get_nasa_events(category: str):
    """UNIVERSAL ROUTE: Fetches any specified category from NASA EONET"""
    url = f"https://eonet.gsfc.nasa.gov/api/v3/events?category={category}&status=open"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            clean_events = []
            for event in events:
                title = event.get('title', 'Unknown Event')
                geometry = event.get('geometry', [])
                if not geometry: continue
                coords = geometry[0].get('coordinates', [])
                if isinstance(coords[0], list):
                    coords = coords[0][0]
                if len(coords) < 2: continue
                lon, lat = coords[0], coords[1]
                clean_events.append({"title": title, "lat": lat, "lon": lon, "category": category})
            return {"status": "success", "total": len(clean_events), "events": clean_events}
        elif response.status_code == 503:
            return {"status": "error", "message": "NASA EONET API 503: Service Unavailable / Overloaded."}
        return {"status": "error", "message": f"NASA API Error: {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/ignition_risk")
def calculate_ignition_risk(lat: float, lon: float):
    if not OWM_KEY:
        return {"status": "error", "error": "Missing OpenWeatherMap API Key in Render environment."}
    try:
        url_weather = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric"
        res_weather = requests.get(url_weather, timeout=5)
        if res_weather.status_code != 200:
            return {"status": "error", "error": f"OWM API rejected request: {res_weather.status_code}"}
        
        weather_data = res_weather.json()
        temp_c = weather_data["main"]["temp"]
        humidity = weather_data["main"]["humidity"]
        wind_speed_kmh = weather_data["wind"]["speed"] * 3.6

        # FIXED: Open-Meteo moved soil_moisture to the hourly array. We extract the first hour [0]
        url_soil = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_moisture_0_to_7cm,precipitation&forecast_days=1"
        res_soil = requests.get(url_soil, timeout=5).json().get("hourly", {})
        
        soil_moisture = res_soil.get("soil_moisture_0_to_7cm", [0.5])[0]
        precipitation = res_soil.get("precipitation", [0.0])[0]

        temp_factor = min(temp_c / 40.0, 1.0) * 0.35 
        wind_factor = min(wind_speed_kmh / 50.0, 1.0) * 0.25 
        dryness_factor = ((100 - humidity) / 100.0) * 0.20
        soil_dryness_factor = max(0, (0.5 - soil_moisture) * 2) * 0.20

        raw_probability = temp_factor + wind_factor + dryness_factor + soil_dryness_factor
        if precipitation > 2.0: raw_probability *= 0.1
        ignition_risk_percent = round(raw_probability * 100, 1)

        status = "CRITICAL IGNITION WARNING" if ignition_risk_percent >= 75 else "ELEVATED RISK" if ignition_risk_percent >= 50 else "NOMINAL"
        return {"status": "success", "lat": lat, "lon": lon, "ignition_probability": f"{ignition_risk_percent}%", "telemetry": {"temp_c": temp_c, "humidity": f"{humidity}%", "wind_kmh": round(wind_speed_kmh, 1), "soil_moisture_vsw": soil_moisture}, "ai_status": status}
    except Exception as e:
        return {"status": "error", "error": f"Failed to calculate risk: {str(e)}"}

@app.get("/api/tle")
def get_satellite_orbits():
    """PHASE 3: Fetches Two-Line Elements. Switched to 'resource' for Landsat, Sentinel, Terra, Aqua"""
    url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return {"status": "success", "tle_data": res.text}
        return {"status": "error", "message": "CelesTrak rejected connection."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/biomass")
def get_biomass_data(lat: float, lon: float):
    """PHASE 5: Fuel Moisture & Predictive Bio-Mass Matrix"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_moisture_0_to_7cm,evapotranspiration,vapor_pressure_deficit&forecast_days=1"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json().get('hourly', {})
            
            # Extract first hour [0] from arrays
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
        return {"status": "error", "message": str(e)}

@app.get("/api/earthquakes")
def get_earthquakes():
    """Fetches USGS Real-Time Lithospheric Data (> 4.5 Mag)"""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
    try:
        res = requests.get(url, timeout=5)
        return res.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/volcanoes")
def get_volcanoes():
    """Fetches NASA EONET Volcanic Eruptions & Ash Advisories"""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events?category=volcanoes&status=open"
    try:
        res = requests.get(url, timeout=5)
        return res.json()
    except Exception as e:
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
        
        csv_reader = csv.DictReader(StringIO(res.text))
        thermal_points = []
        for index, row in enumerate(csv_reader):
            if index > 2000: break # Limit payload size to maintain extreme high performance
            try:
                thermal_points.append({
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "brightness": float(row["bright_ti4"]),
                    "frp": float(row["frp"]),
                    "confidence": row["confidence"]
                })
            except ValueError:
                continue
        return {"status": "success", "data": thermal_points}
    except Exception as e:
        return {"status": "error", "message": str(e)}