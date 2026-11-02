# Global Wildfire Portal: How It Works

A reference for the whole system: the architecture, how data flows and when it updates,
how every map layer is produced, which dataset comes from which provider, and the
resolution of each raster. (No em-dashes anywhere, per project convention.)

---

## 1. What the portal is

A full stack geospatial dashboard for wildfire monitoring and forecasting. It pulls
live satellite fire detections, enriches them with terrain, land cover, weather and
vegetation, groups them into fire events, and runs two models: a next 24h fire risk
forecast (where new fires are likely) and a fire spread forecast (where active fires
are likely to move). It also raises alerts and shows smoke/aerosol.

---

## 2. Services and ports

Five containers in the `global-wildfire-portal` Compose stack.

| Service        | Port | Stack                         | Responsibility |
|----------------|------|-------------------------------|----------------|
| PostgreSQL/PostGIS | 5440 | Postgres 16 + PostGIS 3.4 | Stores everything geospatial. Builds vector tiles with `ST_AsMVT`. DB name `global-wildfire`. |
| Backend (Express)  | 3040 | Node.js + Express         | Browser facing REST API and vector tile server. The only API the map calls for data. |
| Geoprocessing      | 3041 | Python FastAPI + GDAL/rasterio | All external providers, ingestion, enrichment, the models, the scheduler. |
| TiTiler            | 3042 | FastAPI (developmentseed)  | Serves raster tiles from Cloud Optimized GeoTIFFs (COGs). |
| Frontend           | 5180 | React + Vite + Tailwind + MapLibre | The dashboard UI. |

Rule of thumb: vectors are served as MVT by Express (`ST_AsMVT`), rasters are served as
COG tiles by TiTiler. Geometry is stored in EPSG:4326 and tiled in EPSG:3857.

---

## 3. How the data is connected (flow)

```
                 external providers (keys / heavy processing)
   NASA FIRMS, Open-Meteo, NASA POWER, Copernicus (Sentinel-2),
   ESA WorldCover (AWS), AWS Terrarium DEM, NASA GIBS
                              |
                              v
        +---------------------------------------------+
        |  Geoprocessing (FastAPI, 3041)              |
        |  connectors -> ingest -> enrich -> classify |
        |  -> risk model -> spread model -> alerts     |
        |  (APScheduler runs this on a timer)          |
        +----------------------+----------------------+
                 writes rows   |   writes COGs to /data
                               v                      \
                        PostGIS (5440) <----+          v
                               ^            |      TiTiler (3042)
             ST_AsMVT, REST    |            |      raster COG tiles
                               |            |            ^
        +----------------------+--+         |            |
        |  Backend (Express, 3040)|---------+            |
        |  MVT tiles + REST JSON  |                      |
        +------------+------------+                      |
                     ^                                   |
                     |  tiles + JSON                     | raster tiles
        +------------+-----------------------------------+------------+
        |  Frontend (MapLibre, 5180)                                  |
        |  also reads public tile services directly:                 |
        |  NASA GIBS (NDVI, smoke), Mapbox (basemap)                 |
        +------------------------------------------------------------+
```

Key points:
- The map talks to Express (vectors + REST) and TiTiler (our rasters) for portal data.
- Providers that need API keys or heavy processing (FIRMS, Open-Meteo, Copernicus,
  NASA POWER) are isolated inside geoprocessing. The browser never calls them.
- Public, no auth tile services (NASA GIBS NDVI and smoke, the Mapbox basemap) are read
  directly by the map as display overlays.
- All queries into PostGIS are parameterized and go through one shared pool per service.

---

## 4. When data updates (cadence)

Three independent clocks.

**A. The pipeline (geoprocessing scheduler).** APScheduler embedded in FastAPI.
Controlled by env: `SCHEDULER_ENABLED=true`, `FIRMS_REFRESH_HOURS` (currently 2). Every
cycle runs the full refresh (see section 5). The first run fires one interval after
startup, not on boot. A heartbeat logs every 15 minutes. You can also run it on demand
with `POST /connectors/refresh`.

**B. Lazy enrichment (on demand).** Current weather and Sentinel-2 vegetation for a
single event are fetched the first time that event's details panel is opened, then
cached (weather for 1 hour, vegetation for 1 week). This keeps routine ingestion fast.

**C. The UI (polling).** The alerts bell and the status bar each poll the backend every
60 seconds. The status bar (bottom left) shows how old the data and forecast are
(green dot, or amber "stale" when older than 24h).

Retention: each refresh prunes detections older than `FIRMS_RETENTION_DAYS` (5 days), so
the live dataset is a rolling window. Events and alerts track that same window.

---

## 5. The processing pipeline (logic)

One refresh cycle, in order:

1. **Prune** detections older than the retention window.
2. **Ingest** NASA FIRMS VIIRS active fire detections (last day, world). Points are
   filtered to FRP greater than 2 and confidence in (nominal, high), loaded via COPY.
3. **Cluster** detections into fire events (`ST_ClusterDBSCAN`, eps 1 km, min 5 points),
   gated so a cluster becomes an event only if its summed FRP is at least 20 MW, then
   nearby events are merged (within 2.5 km). The event footprint is the buffered convex
   hull of its detections.
4. **Enrich** each event with terrain (elevation, slope, aspect) and land cover.
5. **Classify** events: `wildfire` if the land cover is wildland (tree, shrub, grass =
   codes 10, 20, 30), else `other`. Only wildfire events are drawn on the map.
6. **Risk forecast** (`predict_live`): score every land grid cell worldwide for the
   probability of a new fire in the next 24 hours, write to `grid_prediction`.
7. **Spread forecast**: for the most active fire complexes, run a Monte Carlo spread
   simulation and write per cell burn probabilities.
8. **Alerts**: re-evaluate the alert rules against the fresh events and spread.

See section 9 for the two models and section 10 for alerts.

---

## 6. The map layers

Vector layers come from Express as MVT (`ST_AsMVT`). Raster layers come from TiTiler
(our COGs) or directly from a public WMTS. Toggle them in the Layers panel.

| Layer (UI name)       | Kind   | Served by | Source table / dataset | What it shows |
|-----------------------|--------|-----------|------------------------|---------------|
| Fire events           | vector | Express   | `fire_event.boundary` (wildfire only) | Red footprints of grouped wildfires. Click for details. Time filter applies. |
| Detections            | vector | Express   | `fire_detection` (wildfire only) | Raw satellite hotspots, colored by confidence. Time filter applies. |
| Fire risk (next 24h)  | vector | Express   | `grid_cell` + `grid_prediction` | Green to red forecast of new fire probability. A forecast, independent of the time filter. |
| Fire spread (next 24h)| vector | Express   | `fire_spread_forecast` | Yellow to dark red burn probability around active fires. A forecast, independent of the time filter. |
| Land cover            | raster | TiTiler   | `worldcover_global.cog.tif` | ESA WorldCover classes (palette). |
| Vegetation (NDVI)     | raster | NASA GIBS | MODIS Terra NDVI 8 day | Greenness. |
| Terrain (DEM)         | raster | TiTiler   | `srtm_mosaic.json` (SRTM) | Elevation color ramp, from mid zoom in. Click for an elevation popup. |
| Smoke / aerosol       | raster | NASA GIBS | MODIS Combined AOD | Aerosol optical depth (smoke and haze). CAMS can replace it via `VITE_SMOKE_TILE_URL`. |
| Basemap               | raster | Mapbox    | Mapbox dark style | Background map. |

The time filter (All, 72h, 48h, 24h) is a past window and only affects the detections
and events layers. The two forecast layers look 24 hours ahead, so they do not change
with it.

---

## 7. Data sources, providers and native resolution

| Dataset | Provider / website | Access | Native resolution | Used for |
|---------|--------------------|--------|-------------------|----------|
| VIIRS active fire (S-NPP NRT) | NASA FIRMS, firms.modaps.eosdis.nasa.gov | area CSV API, needs a free MAP_KEY | 375 m sensor pixel (stored as points) | Detections, events, all fire logic |
| ESA WorldCover 2020 | ESA, esa-worldcover.org (tiles on AWS S3) | public COGs via /vsicurl | 10 m | Land cover (enrichment + display) |
| SRTM GL1 elevation | NASA/USGS via OpenTopography | VRT -> MosaicJSON | 30 m | DEM display layer, regional terrain |
| Terrarium terrain tiles | AWS Open Data, elevation-tiles-prod | public XYZ PNG, no auth | tile z5 (see section 8) | Global terrain fallback (elevation/slope/aspect) |
| MODIS NDVI 8 day | NASA GIBS, gibs.earthdata.nasa.gov | WMTS, no auth | about 250 m (display) | Vegetation layer; also the greenness grid feature |
| MODIS Combined AOD | NASA GIBS | WMTS, no auth | about 10 km (coarse) | Smoke / aerosol layer |
| Current weather, soil, VPD | Open-Meteo, open-meteo.com (ERA5 based) | REST, no auth (daily quota) | point | Per event current conditions (lazy) |
| Historical weather | NASA POWER, power.larc.nasa.gov | REST, no auth | about 0.5 degree | Training set weather features |
| Sentinel-2 L2A (NDVI/NDMI/NBR) | Copernicus Data Space, dataspace.copernicus.eu | Statistical API, OAuth (CDSE key) | 10 m | Per event vegetation indices (lazy) |
| Basemap | Mapbox, mapbox.com | raster tiles, public token | n/a | Background map |

Keys live in `.env` and are never committed: `FIRMS_MAP_KEY`, `CDSE_CLIENT_ID` /
`CDSE_CLIENT_SECRET`, `VITE_MAPBOX_TOKEN`. Open-Meteo, NASA POWER, GIBS and the AWS
datasets need no key.

---

## 8. Local raster COGs and their resolution

Files under `data/`, sampled by geoprocessing and served by TiTiler. All are EPSG:4326.

| File | Source | Pixel size | Approx. ground | Extent | Purpose |
|------|--------|-----------|----------------|--------|---------|
| `worldcover_global.cog.tif` | ESA WorldCover (downsampled) | 0.0100 deg | about 1.1 km | global | Land cover display layer |
| `worldcover.cog.tif` | ESA WorldCover (regional) | 0.0010 deg | about 110 m | regional | Higher res land cover sample |
| `elevation.cog.tif` | SRTM GL1 | 0.0003 deg | about 30 m | regional (about 61-79 E, 24-37 N) | High res terrain where available |
| `slope.cog.tif` | derived from SRTM | 0.0003 deg | about 30 m | same regional | High res slope |
| `aspect.cog.tif` | derived from SRTM | 0.0003 deg | about 30 m | same regional | High res aspect |
| `dem_global.cog.tif` | AWS Terrarium (z5) | 0.0344 deg | about 3.8 km | global | Global elevation fallback |
| `slope_global.cog.tif` | derived from global DEM | 0.0344 deg | about 3.8 km | global | Global slope fallback |
| `aspect_global.cog.tif` | derived from global DEM | 0.0344 deg | about 3.8 km | global | Global aspect fallback |
| `veg_greenness.cog.tif` | NASA GIBS MODIS NDVI | 0.1000 deg | about 11 km | global | Vegetation greenness grid feature (0..100) |
| `srtm_mosaic.json` | SRTM GL1 (remote) | 30 m tiles | about 30 m | near global land | DEM display mosaic (TiTiler) |

Terrain enrichment samples the regional 30 m COGs first and falls back to the global
3.8 km COGs, so every event gets elevation/slope/aspect even outside the SRTM extent.
Slope from the 3.8 km DEM is smoothed; raise `DEM_ZOOM` to 6 or 7 to sharpen it.

---

## 9. The two models

**Fire risk (Phase 6).** A scikit-learn `HistGradientBoostingClassifier` wrapped in
isotonic calibration, trained on a global 0.5 degree land grid. One row per (cell,
cutoff time). Features (17): terrain (elevation, slope, aspect), land cover, vegetation
greenness, fire history in the cell (past 24/48/72h detection counts, past 24h FRP,
had_fire), neighborhood fire pressure (nearby cells), and weather (temp, RH, wind,
precip, VPD, soil moisture). The label is whether a new fire starts in the cell in the
next 24 hours. Training is leakage safe (features at or before the cutoff, label after)
with a time based split. Latest metrics: ROC-AUC 0.934, PR-AUC 0.58, Brier 0.041, ECE
0.017 (well calibrated). Prediction is run live from the latest detections, so the map
reflects the current situation, not a stale cutoff.

**Fire spread (Phase 7).** A Monte Carlo cellular automaton. For each active fire
complex, a local fine grid (about 2 km cells) is seeded at the current fire, then fire
spreads to neighbors each step with a probability driven by wind (direction and speed),
fuel (land cover times vegetation), dryness (VPD) and slope, with fuel burnout so the
fire is a moving front, not a blob. Thirty ensemble members with perturbed wind give the
uncertainty: the fraction of members that burn a cell is its burn probability. Output is
per cell burn probability plus mean arrival time, over a 24 hour horizon.

---

## 10. Alerts

Rule based, in app, regenerated every refresh and kept in sync with the displayed data.

- **large_fire**: a wildfire event whose summed FRP is at least 2000 MW (critical at
  5000 MW) and that is still within the data retention window (so it is still on the
  map). Any significant displayed wildfire has an alert.
- **spread_threat**: a fire whose spread forecast covers at least 300 cells at 50 percent
  or higher burn probability.

When new data arrives, alerts for events that age out of the dataset are resolved and new
ones appear, so the list always matches the current fires. The frontend bell polls
`GET /alerts` every 60 seconds and clicking an alert flies the map to it.

---

## 11. Useful endpoints and config

**Backend (Express, 3040):** `GET /tiles/{layer}/{z}/{x}/{y}.mvt`, `GET /events`,
`GET /events/:id`, `GET /alerts`, `GET /risk/meta`, `GET /status`, `GET /elevation`,
`GET /health` (readiness), `GET /health/live` (liveness). Security headers, gzip and API
rate limiting are on; the map tile endpoint is not rate limited.

**Geoprocessing (FastAPI, 3041):** `POST /connectors/refresh`, `POST /model/forecast`,
`POST /spread/forecast`, `POST /alerts/evaluate`, `POST /training/*`, `POST /events/*`.

**Key env knobs (`.env`):** `SCHEDULER_ENABLED`, `FIRMS_REFRESH_HOURS`,
`FIRMS_RETENTION_DAYS`, `FIRMS_MAP_KEY`, `CDSE_CLIENT_ID/SECRET`, `VITE_MAPBOX_TOKEN`,
`ALERT_FRP_WARNING/CRITICAL`, `DEM_ZOOM`, `VITE_SMOKE_TILE_URL` (to swap in CAMS).

---

## 12. How to read the dashboard

- The map opens on a global view. Red footprints are wildfire events, colored dots are
  raw detections.
- Use the time filter to limit detections and events to the last 24/48/72 hours or All.
- Turn on Fire risk to see where new fires are likely in the next 24 hours, Fire spread
  to see where active fires may move. Both are forecasts and ignore the time filter.
- Land cover, Vegetation, Terrain and Smoke are context overlays.
- The bell (top right) lists active alerts. The status bar (bottom left) shows how fresh
  the data and forecast are.
- Click any event footprint for its full details: terrain, weather, moisture, vegetation
  and the underlying detections.
