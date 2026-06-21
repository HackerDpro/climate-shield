import requests

# NASA EONET API for Active Global Wildfires (No key needed!)
url = "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open"

print("🛰️ Initiating uplink to NASA EONET Wildfire network...")

try:
    # 10 second timeout so we don't freeze
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        # Convert the response into a Python dictionary (JSON)
        data = response.json()
        fires = data.get('events', [])
        
        print(f"✅ Uplink Successful! Found {len(fires)} active global wildfires right now.")
        
        # Print the name and coordinates of the very first fire on the list
        if fires:
            first_fire = fires[0]
            title = first_fire.get('title')
            # Extracting the coordinates (Longitude, Latitude)
            coords = first_fire['geometry'][0]['coordinates']
            print(f"🔥 First fire on radar: {title}")
            print(f"📍 Coordinates: Longitude {coords[0]}, Latitude {coords[1]}")
            
    else:
        print(f"❌ Connection failed. NASA said: {response.status_code}")

except Exception as e:
    print(f"❌ An error occurred: {e}")