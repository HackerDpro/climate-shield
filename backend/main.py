from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from collections import Counter
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OWM_KEY = "4bd2d6b15fa80df855ee6a25038c7b92"

# 🛰️ NEW: Live NASA Instrument Status
@app.get("/api/satellites")
def get_satellite_sources():
    url = "https://eonet.gsfc.nasa.gov/api/v3/sources"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            sources = res.json().get("sources", [])
            # Return a list of active NASA/NOAA instruments
            return {"status": "success", "instruments": [s['id'] for s in sources[:6]]}
    except Exception:
        pass
    return {"status": "error", "instruments": ["TERRA", "AQUA", "SUOMI-NPP", "NOAA-20"]}

@app.get("/api/wind")
def get_wind_data(lat: float, lon: float):
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

# 🌍 NEW: Real Atmospheric Contamination API
@app.get("/api/air_quality")
def get_air_quality(lat: float, lon: float):
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm2_5,carbon_monoxide"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json().get('current', {})
            return {
                "status": "success",
                "pm2_5": data.get("pm2_5", 0),
                "co": data.get("carbon_monoxide", 0)
            }
    except Exception:
        pass
    return {"status": "offline", "pm2_5": "N/A", "co": "N/A"}

# ⛰️ UPGRADED: Rock-solid Open-Meteo Topography API
@app.get("/api/analyze_terrain")
def analyze_terrain(lat: float, lon: float, wind_dir: float):
    offset = 0.01  
    # Open-Meteo allows arrays in a single fast call
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
        print(f"Elevation API Error: {e}")
        pass
        
    return {"status": "fallback", "elevation_meters": "Unknown", "terrain_status": "TERRAIN DATA OFFLINE", "spread_multiplier": 1.0}

@app.get("/api/fires")
def get_active_fires():
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
                    clean_fires.append({
                        "title": title.replace("Wildfire", "").strip(),
                        "lat": lat, "lon": lon
                    })
            
            grid_counter = Counter()
            for fire in clean_fires:
                grid_x, grid_y = round(fire['lon'] / 1.0), round(fire['lat'] / 1.0)
                grid_counter[(grid_x, grid_y)] += 1
                
            for fire in clean_fires:
                grid_x, grid_y = round(fire['lon'] / 1.0), round(fire['lat'] / 1.0)
                fire['density_score'] = grid_counter[(grid_x, grid_y)]
                
            clean_fires.sort(key=lambda x: x['density_score'], reverse=True)
            return {"status": "success", "total_global": len(clean_fires), "fires": clean_fires}
        else:
            return {"status": "error", "message": "NASA uplink rejected."}
    except Exception as e:
        return {"status": "error", "message": str(e)}