# The README file is divided in two sections, the first one is a summary made by AI (Gemini 3.1 Pro), the second section is a more detailed blog written by me.

# 🌍 CLIMATE SHIELD: Planetary Multi-Hazard Observation Terminal

**Climate Shield** is a high-performance, real-time command dashboard designed to monitor, predict, and analyze global environmental threats. Moving beyond simple reactive map markers, Climate Shield ingests raw multi-spectral satellite telemetry, cross-references it with live atmospheric and topographical data, and utilizes empirical physics equations to predict disaster spread and logistical resource requirements.

[Live Demo](https://climate-shield.netlify.app/) *(Link your actual Netlify/Vercel URL here)*

---

## 🤖 AI Collaboration Statement
*The technical architecture, asynchronous Web Worker threading, and scientific Python physics algorithms for this platform were developed in direct collaboration with **Google Gemini**.* AI was utilized as a pair-programming architect to:
1. Translate standard NASA/USGS JSON structures into high-performance `Float32Array` WebGL inputs.
2. Formulate real-world thermodynamic models (e.g., Byram's Fireline Intensity, Volumetric Soil Hydrology).
3. Debug asynchronous CORS mapping errors and optimize zero-lag browser performance for massive dataset rendering.

---

## 💻 The Three Command Views
Climate Shield operates across three distinct visual engines:
1. **TACTICAL (2D Command):** The primary geographic interface. Click on any global threat to open its HUD, fetch localized weather vectors, and calculate empirical hazard scores.
2. **ORBITAL (3D WebGL):** A hardware-accelerated, 3D rotating globe featuring real-time solar shading (Day/Night terminator lines) and physical height-mapped thermal pillars.
3. **TELEMETRY (Analytics):** A pure-data dashboard rendering planetary Key Performance Indicators (KPIs), global carbon emission estimates, and threat threshold charts.

---

## 📖 Scientific Feature Manual (How to Use)
Climate Shield is designed for Earth System Scientists. Here is a breakdown of the live environmental physics and tracking arrays built into the system:

### 1. Pre-Crime Predictive Scanning (Ignition AI)
* **How to use:** Click anywhere on an empty landmass on the Tactical Map. 
* **What it does:** The system draws an 80km scanning radius and pings Open-Meteo and OpenWeatherMap. It cross-references current Temperature, Wind Speed, Relative Humidity, and **Volumetric Soil Moisture**. 
* **The Science:** By analyzing soil dryness alongside heat and wind, the AI calculates a literal percentage-based probability of a wildfire igniting in that exact sector within 48 hours. Heavy live precipitation immediately suppresses the risk score.

### 2. Live Fire Logistics & Tactical Routing
* **How to use:** Click on any active Wildfire marker. Click the "Calculate Resource Requirements" button.
* **What it does:** Generates a real-time engineering report and draws a Safe Evacuation Corridor.
* **The Science:** * **Uphill Alignment:** Fire spreads drastically faster uphill as heat rises and pre-bakes the fuel. Our backend fetches the exact terrain elevation and slope angle to calculate a spread multiplier.
  * **Fireline Intensity & Suppressants:** Calculates the thermal output ($kW/m$) and the literal volume of water (in Liters) required to break the thermal feedback loop based on the fire's density.
  * **Evacuation Routing:** Uses the Open Source Routing Machine (OSRM) to find the nearest drivable road that moves *perpendicular or opposite* to the live wind direction, ensuring safe civilian egress.

### 3. Multi-Spectral Sensor Arrays (Bottom Dock)
Toggle these layers to observe cross-sphere planetary interactions. Data is processed using a background CPU Web Worker to ensure zero UI lag even with thousands of data points.

* **⚠️ Mudslides (Landslides):** When wildfires burn a mountain, roots die and soil becomes hydrophobic (glass-like). This radar finds active fires located on steep slopes (>600m elevation) and flags them as Critical Mudslide Risk Zones for when the next rainstorm hits.
* **🌀 Cyclones (Hurricanes):** Hurricanes are giant heat engines fueled by ocean water warmer than 26.5°C. This sensor tracks Deep-Ocean Sea Surface Temperature (SST) anomalies to visualize where future storms will spawn.
* **💥 Earthquakes:** Taps directly into the USGS live lithospheric feed, isolating and mapping significant tectonic fractures (Magnitude > 4.5).
* **🌋 Ash Clouds (Volcanoes):** Ingests NASA EONET data to track stratospheric ash injections, which pose severe threats to global aviation and regional climate cooling.
* **🛰️ Satellite Heat (Raw Radiometry):** Bypasses standard fire warnings to ingest raw CSV data from NASA MODAPS. It maps **Fire Radiative Power (FRP)** in Megawatts, allowing scientists to measure the exact physical thermal output of a disaster, not just its location.

---

## 🛠️ Technical Stack
* **Frontend:** Vanilla JavaScript, HTML5 Canvas, Leaflet.js, Globe.gl (Three.js/WebGL), Chart.js
* **Backend Pipeline:** FastAPI (Python), Hosted on Render
* **Performance:** Multi-threaded Web Workers, asynchronous API fetching, Blob URLs.
* **Live API Integrations:** * *NASA EONET* (Volcanoes, Base Fires)
  * *NASA FIRMS MODAPS* (Raw Radiometry/FRP)
  * *USGS* (Real-time Seismic)
  * *OpenWeatherMap* (Atmospheric Vectors)
  * *Open-Meteo* (Soil Hydrology, PM2.5 Air Quality, Topographical Elevation)
  * *OSRM* (Dynamic Road Routing)

---

## 🚀 How to Run Locally

1. Clone the repository: `git clone [url]`
2. Set up your backend environment variables in an `.env` file:
   ```env
   OWM_KEY=your_open_weather_map_key
   FIRMS_KEY=your_nasa_firms_map_key





## Little unfiltered blog (may contain some errors and be boring to read):

**Day 1:** 
I made the basics of the software. I first started by brainstorming ideas of ways I could help NASA. Due to the summer coming and the high fire risk I decided to make a fire prediction page (or just fire stats). In the first day I brainstormed all the ideas of API's I was going to need, data I would like to show, tools that may be useful, and making the structure of the page. Later I got to work. I used Leaflet to add a map and added some cool black map to our site. After the map, I added the fire pinpoints. I needed to know where the fires were at, therefore I used the NASA FIRMS MAP API, that showed the current fires. For the fire prediction I got into the idea of predicting the fire risk using the (current) weather data, in that way I could use the wind speed and direction to calculate vectors of where the fire might spread to. For that I used the openweathermap API. In conclusion, my maps are able to show the points of current fires as well as the vectors covering fire risk areas,just how I wanted.

**Day 2:** 
In day 2 lots of things happened. I started improving everything, here is how: I first started by finding a method to increase the number of fire events shown at once. I corrected the previous limit of calls of 500 fires that I was using for testing other aspects of my code, otherwise my browser would have crashed repeatedly as I would try to move the map or zoom. I found a method to display all 6K+ fires by showing them on a HTML5 canvas, in that way each time that a user would reload the page it would almost instantly pop up without any problems or lags. But that wasn't all, the second reason I still couldn't show all fires at first was the weather. My openweathermap API has a limit that would have been exceeded when loading 6k+ fires. On top of it, it would have considered the calls as spamming. The way I fixed that was by making the vectors not show anymore on the map. From now on you can click on the fires and they will then show the weather info and show the vectors, but only when the user asks for it. That way we now could display all 6k+ fires without any problems.

So next I started working on the page cause this wasn't meant to just be a map, it was a dashboard. I started to make a structure for info shown, I found the best way was to make two vertical panels on the sides of the screen (left, right). Now we needed to add data to those panels, I've tried different things but in the end I finnished with just a simple structure at the left-panel showing: Active prediction (how many fires/predictions have been detected and located), Satellite Array Status (showing if each API is working as it should) and last AI Real-Time Stream (showing the status of the AI used in my web, I'll talk about it later). At the right-panel I thought that showing the top 5 most dangerous fires would be good enough for now, you can also click on them to show them on the map and view more info about.

Next I got back working on the fires displayed, I made the fires have a different color (green, orange, red) depending on how dangerous they may be and made them a bit bigger with a bigger hitbox so it would be easier to click them without missing your first 10 clicks.

Next I started working on getting more data, something that changes the speed of fire spread by much is... The terrain, if a fire goes uphill it spreads much quickly than a fire on normal or downhill terrain. To see the terrain a fire is on we used the open-meteo to calculate the elevation of the location of a fire, using other calcuations too later too see how much the terrain affects the spread of fire.

So now when you click on a fire you can see the following stats (example of one of the most dangerous fires at the moment):



RX FORKS 5 Prescribed Fire, Montgomery, Arkansas



💨 WIND VECTOR: 14.5 km/h @ 187°

⛰️ ALTITUDE: 292 m

🤖 TERRAIN AI: CRITICAL UPHILL ALIGNMENT (+108% SPREAD)

☠️ ATMOSPHERE (PM2.5): 4.4 µg/m³

📈 24H PROJECTION: ~44.44 km linear spread

📊 HAZARD SCORE: 100 / 100



But it didn't end here, I also added 3 buttons at the top of the page: Tactical (deafault), Orbital (only map) abd Telemetry (only data). Tactical is the deafault page with teh map in the middle and the two panels at the sides, the Orbital page is the same thing but without the two panels at the side, but at Telemetry it starts getting interesting.

We can't show everything on the same page, so we made the Telemetry data (Predictive AI Analytics Engine Core Matrix) to show the extra data that you may want to see. First we have the "TOTAL ATMOSPHERIC CARBON FLUX" to be honest I am not sure why somebody would want to see that but if someone does then there it is (current: 933.80 MT). Next the "CRITICAL EMERGENCY OUTBREAKS" these are the total amount of critical fire (shown red on the map). Next the "AI PREDICTIVE RISK AVERAGE", this speaks for itself, its a average off all predicted risks calculated. Next there is a "Planetary Threat Threshold Spread" graphical illustration, with this circel illustration I want to show the balance between the 3 different levels of extremety of fire (red, orange, green on the map), click on one of the colors in the legende to remove it from the illustration and click on a color of the illustration to show how many fire of that level there are. Next "Atmospheric CO2 Trajectory (Est. Megatons)", another graphical illustration that shows the path of the estimated atmospheric CO2 made by fire in the last days (in Megatons). Last we have the "Deep Analytics Data Grid Summary (Top 10 Active Outbreaks)", as it says it is a list of the 10 worst fires currently, with their location (long, lat) and status (probably red, critical outbrake unless there are currently few fires int he world). 