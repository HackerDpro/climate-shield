# Climate Shield: Global Wildfire Predictive Dashboard

Climate Shield is a high-performance, AI-enhanced dashboard designed to monitor global wildfire activity. By integrating real-time NASA satellite data with multi-source meteorological inputs, the platform provides predictive analytics on fire behavior, including terrain-based spread projections and atmospheric impact.

[Live Demo](https://climate-shield.netlify.app/)

## 🚀 Key Features
* **High-Performance Rendering:** Utilizes HTML5 Canvas to map 6,000+ fire events instantly without browser lag.
* **Terrain-Aware AI:** Uses elevation data (Open-Meteo) to calculate "Uphill Alignment" factors, predicting spread speed based on geography.
* **Dynamic Analytics Engine:** Offers three dedicated views:
    * **Tactical:** Full dashboard with live monitoring.
    * **Orbital:** Map-focused spatial tracking.
    * **Telemetry:** In-depth data analysis including CO2 flux and risk averages.
* **On-Demand Intelligence:** Efficient API handling that fetches detailed weather and vector data only upon user interaction, respecting rate limits.

## 🛠️ Technical Stack
* **Frontend:** JavaScript, HTML5 Canvas, Leaflet.js
* **Backend:** FastAPI (Python), Render-hosted
* **APIs:** NASA EONET, OpenWeatherMap, Open-Meteo
* **AI/Methodology:** Custom spread-logic algorithms based on wind-vector and terrain elevation variables.

## 🧠 Development Log (The "Stardance" Journey)
### Day 1: Foundation
* **Concept:** Identified the need for real-time fire spread prediction.
* **Implementation:** Built the Leaflet mapping core and established the NASA FIRMS data pipeline. Integrated OpenWeatherMap for initial wind-vector visualization.

### Day 2: Scaling & Architecture
* **Scaling:** Solved massive browser performance bottlenecks (loading 6k+ fires) by switching from DOM-based markers to HTML5 Canvas.
* **Efficiency:** Implemented an "on-demand" weather fetching strategy to maintain compliance with API rate limits.
* **Advanced Analytics:** Added terrain-elevation calculations to determine fire hazard scores and spread projections.
* **UI/UX:** Structured the "Command Center" dashboard with side-panel information architecture and three distinct interface modes (Tactical, Orbital, Telemetry).

## 🤖 AI Collaboration Statement
This project was developed through a collaborative process. AI tools were utilized to:
1. **Optimize Algorithms:** Refine fire-spread calculations and terrain-impact formulas.
2. **Troubleshooting:** Identify and resolve asynchronous API conflicts and network bottlenecks.
3. **Architectural Guidance:** Strategize on efficient UI structure to ensure the dashboard remained performant while handling large data sets.

## 🛠️ How to Run Locally
1. Clone the repo: `git clone [url]`
2. Set up your backend API keys in an `.env` file (`OWM_KEY`).
3. Install dependencies: `pip install -r requirements.txt`
4. Launch via Uvicorn: `uvicorn main:app --reload`





## Little unfiltered blog (may contain some errors and be boring to read):

**Day 1:** 
I made the basics of the software, I first started by brainstorming ideas of ways I could help NASA at something, because of the summer comming and the lots of fires there are I went in the idea of making some fire prediction or just fire stats page. In the first day I brainstormed all the ideas of API's I am going to need, data I would like to show, tools that may be usefull, and making some structures for the page. After the brainstorming I got to work. I used Leaflet to add a map, added some cool back map to our site and began working. After the map came the fire pinpoints, I needed to know where the fires are at, for that I used the NASA FIRMS MAP API, it showed the current fires as I needed on the map. For the fire prediction I got into the idea of predicting the fire using the (current) weather data, that way I could use the wind speed and direction to create verctors of where the fire may spread to. For that I used the openweathermap API. Now I could not only see the points of current fires but also vectors showing the prediction of fire spread. Just how I wanted.





**Day 2:** 
In day 2 lots of things happened, I started making everything better, here is how: I started first by finding methods for the fires shown limit. I didn't say it before but at first I added a limit of calls of 500 fires, that way I could test that everything was working but that limit has another reason too, the first problem of not having a limit was that my browser would crash each time i just tried to move the map or zoom a bit, it was really slow. To stop that problem I found a methode being to show all 6k+ fires by showing them on a HTML5 canvas, that way each time you would reload the page they would almost instantly pop up and without any problems or lags. But that wasn't all, the seccond reason I still couldn't show all fires wasn't because of the fires, but because of the weather. First of my openweathermap API has a limit wich would have exceeded inmediatly if i just loaded the weather for all 6k+ fires, but thats not all, it also just woudn't have done it because that is considered as a spamming of API calls, so it would just have rejected them. The way I fixed that is by making the vectors not show onymore on the map, from now on you can click on the fires and they will then show the weather info and show the vectors, but only when the user asks for it. That way we now could display all 6k+ fires without any problems.

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