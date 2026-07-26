# Here is a summary of the project, have fun reading it (a little blog is in blog.md but only has day 1 and 2).

# CLIMATE SHIELD

I created Climate Shield because I had in mind the idea of creating a dashboard that could show how the world is going, what is happening, and what might happen.
I also learned a lot of new things about the climate in the process making this.

[Test it here](https://climate-shield.netlify.app/) *(Update: I recently changed the backend from Render.com to a  Hack Club Nest server, so you no longer have to wait for the server to "wake up"! It's fast and always online.)*

-------------
![Climate Shield Dashboard](screenshot.png)
-------------

## First I want to make something clear, I did use AI to help me with it, here's how and what for:

1. To translate standard NASA/USGS JSON structures into `Float32Array` WebGL inputs for the globe (orbital).
2. To formulate calculations (I am just a programmer, not a scientist. I am unknown of the formules and calculations for predictions I show in my web).
3. To debug errors/bugs and optimize no-lag browser performance for all the data's being calculated.
4. Not always but I did use AI for styling elements

----------

## I split the web up in 3 sections/pages
1. **TACTICAL (2D dashboard):** This is the primary page where you should go to if you to have all data visualized but also want more information, a bit like a all-in-one dashboard.
2. **ORBITAL (3D WebGL globe):** This is where you go if you want just a visualisation, you see a globe of the earth and pilars having the color of the category of a fire and the height depending on the density of a fire.
3. **TELEMETRY ((raw) data):** This is where to go when you are some kind of scientist who just wants (raw) data, Every time I add some new data API's or similar I will try to also categorise the data in here (for nerds)

----------

## Features
* **Live Telemetry:** Tracks over 6,000 active wildfires, mapping them using HTML5 Canvas to prevent browser lag.
* **Tactical Threat Dropdown:** A new interactive dropdown system to change between NASA data for Earthquakes, Volcanoes, Severe Storms, Floods, and Raw Satellite Heat.
* **Predictive Scanning:** Click on any empty land to run a real-time biomass, soil moisture, and weather calculation that predicts 48-hour ignition probability.
* **Tactical Fire Reports:** Click an active fire to calculate its downhill/uphill spread multiplier, projected 24-hour path, and a estimate of how many liters of water are needed to extinguish it.
* **Orbital WebGL globe:** A fully 3D globe visualization of the Earth's current fire threats.

----------

## How it works
* **Layers Dropdowns:** I recently added a tactical dropdown to toggle specific disasters (Floods, Earthquakes, etc.). The challenge was that using these API calls would wipe out my wildfire density data. I solved this by building specific layer logics (toggleSpecificLayer) that isolates the fires from the rest of the Leaflet layer groups.

* **Background Web Workers:** Parsing raw spectral data from NASA MODAPS (FIRMS) and mapping global fault lines was lagging the main UI thread. I removed the heavy data parsing to a JavaScript Web Worker (analyticsWorker), which parses the data silently in the background and only messages the main thread when the markers are ready to render.

* **Server Change:** Hosting on Render (free-tier) meant the server would go to sleep. I SSH'd into a Linux server (Hack Club Nest) and set up the backend permanently using pm2 to ensure the live NASA uplinks never goes to sleep.

----------

## Credits:
* **NASA EONET & MODAPS** for the live telemetry.
* **USGS** For the real-time lithospheric eathquake data.
* **Open-Meteo & OpenWeatherMap** for the topography, soil hydrology and wind data.
* **Hack Club Nest** for the backend server hosting.
* **Gemini (3.1 Pro)** Used to help translate complex JSON structures into WebGL inputs and to help optimize the Javascript performance to handle thousands of data points without lagging. (more info right under the screenshot)

----------

## In the future:
* Currently I am working on adding more telemetry while keeping the UI clean and not too overcomplicated or not-understandable.

----------

## Run it locally:

1. Clone the repository:
  git clone https://github.com/HackerDpro/climate-shield.git
  cd climate-shield/backend
2. Install the Python packages:
  pip install -r requirements.txt
3. Set up your env variables in a .env file:
  OWM_KEY=open_weather_map_key
  HF_TOKEN=hugging_face_token (currently not used in project so it is optional but may be used in later updates)
  FIRMS_KEY=nasa_firms_map_key
4. Start the FastAPI backend:
  uvicorn main:app --reload
5. Open index.html in your browser.