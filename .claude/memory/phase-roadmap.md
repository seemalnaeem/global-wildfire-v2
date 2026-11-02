# Memory: phase roadmap

Source: `Global_Wildfire_Monitoring_Forecasting_Explained.pdf` (proposal, 8 phases).
Rule from the user: do not change the existing architecture. Add approaches beside
it. Move one phase (and one step) at a time.

## Architecture reconciliation (proposal vs our stack)
- Proposal says "backend: Python FastAPI". We keep the PERN + FastAPI hybrid.
  Express (3040) stays the browser-facing API and tile server. The FastAPI
  `geoprocessing` service (3041) hosts connectors, ingestion, and the scheduler.
- Proposal rule "frontend never talks to providers, isolate provider logic in
  connectors behind a consistent internal API" already fits: connectors live in
  FastAPI, Express exposes the clean API, the map consumes only Express + TiTiler.
- Object storage: deferred. Using local volume behind a storage seam
  (`app/storage.py`), MinIO drops in later via STORAGE_BACKEND=s3.
- Scheduler: APScheduler embedded in FastAPI, no extra container. Off by default
  (SCHEDULER_ENABLED=true to enable).

## The 8 phases
1. Foundation: DB, storage, ingestion/connector framework, scheduler. DONE.
2. Live fire monitoring: NASA FIRMS / VIIRS connector, detections, fire events. DONE.
3. Land cover + terrain. Enrich each fire with terrain + land cover. DONE.
4. Weather, vegetation, moisture. Weather + soil moisture (Open-Meteo) DONE.
   Vegetation: NDVI map layer (NASA GIBS MODIS) DONE. Sentinel-2 NDVI/NDMI/NBR
   per-point values still need Copernicus/GEE auth.
5. Historical fire database on a common grid, leakage-safe labels. DONE.
6. Fire-risk forecasting (24/48/72h), risk rasters. DONE (strengthened, calibrated, global).
7. Fire-spread forecasting with uncertainty. DONE (Monte Carlo CA).
8. Smoke (CAMS), alerts, production hardening. DONE (GIBS AOD smoke, in-app alerts, backend hardening).

## Phase 1 status: complete
- Tables `data_source`, `ingest_run`, `raw_file` (see db/init/03_ingestion.sql).
- Connector framework: `app/connectors` (base + registry), `app/ingest`
  (repository + validation), `app/storage.py`.
- Internal API: `GET /connectors`, `GET /connectors/runs`,
  `POST /connectors/{name}/run`. `demo` connector proves the loop.

## Phase 2 status: complete
- Tables `fire_detection` (raw, deduped) and `fire_event` (grouped, permanent id).
  See db/init/04_fire.sql.
- `firms_viirs` connector: live FIRMS area API when FIRMS_MAP_KEY is set, else a
  bundled sample (offline). Parses VIIRS CSV, validates, loads detections.
- Clustering `app/events/cluster.py`: attach to nearest existing event within
  distance+time, else DBSCAN new events. Runs after each load and via
  `POST /events/cluster`. Thresholds FIRE_CLUSTER_DISTANCE_M / _TIME_HOURS.
- Backend (Express) exposes MVT layers `fire_detections` and `fire_events` with an
  optional `?from`/`?to` time window, plus `GET /events` and `GET /events/:id`
  (event + detections) for the details panel.
- Frontend: MapLibre layers for detections (colored by confidence) and events
  (sized by detection_count), a time filter (24/48/72h/All), and a click-to-open
  details panel. Verified: browser fetched fire tiles (200) over the data extent.
- Next: Phase 3, land cover + terrain. Elevation and slope COGs already served.

## Phase 3 status: complete
- Aspect COG derived from the elevation DEM (`gdaldem aspect`), served by TiTiler
  alongside elevation and slope.
- Table `fire_event_context` (elevation, slope, aspect, landcover_code/label).
  See db/init/05_context.sql.
- Terrain enrichment `app/enrich/terrain.py`: samples local DEM COGs at event
  centroids. Regional only (DEM extent), null elsewhere until a global DEM lands.
- Land cover `app/enrich/landcover.py`: ESA WorldCover 2020 (public, global, 10 m,
  no auth), remote COGs on AWS read via /vsicurl, grouped by 3 degree tile.
- Orchestration `app/enrich/service.py`, endpoint `POST /events/enrich?limit=`.
  Processes events lacking context. Backend `GET /events/:id` joins context, the
  DetailsPanel shows land cover + elevation/slope/aspect.
- Land-cover map layer: GLOBAL `data/worldcover_global.cog.tif` (~1.1 km, palette,
  20 MB) served by TiTiler, toggle in the frontend Layers control with a class
  legend. Built via global VRT (all ~2651 tiles) then 6 parallel gdalwarp bands
  merged to a COG.
- Coverage fix: all 44,536 events enriched (land cover global via WorldCover
  sampling). Per-event land cover also fills via lazy on-click enrichment (backend
  GET /events/:id calls geoprocessing `POST /events/{id}/enrich` when missing) plus
  the parallel bulk pass. Sampling parallelized (~5x, 500 events in ~40 s).
- Verification note: headless Chrome (software WebGL) will not fetch/paint the
  localhost raster land-cover layer, so it cannot be screenshotted here. Tiles are
  proven correct and fast worldwide by direct fetch. It renders in a real browser.
- Detection loader now uses COPY into a temp table then INSERT ON CONFLICT (was
  executemany, 13.5 min for 121k). Fast.
- Data freshness: FIRMS is a snapshot unless refreshed. The time filters (24/48/72h)
  are computed from now(), so if the data ages past those windows they show empty
  while All still works. The embedded scheduler now keeps it current:
  `scheduler.refresh_fires()` prunes detections older than FIRMS_RETENTION_DAYS,
  pulls fresh FIRMS, re-clusters, enriches land cover, classifies. Runs every
  FIRMS_REFRESH_HOURS (default 6). Enable with SCHEDULER_ENABLED=true IN .env (not
  just a runtime override, or it reverts on restart). Manual: POST /connectors/refresh.
- Next: Phase 4, weather, vegetation, moisture (ERA5, forecasts, Sentinel-2).

## Phase 4 status: in progress
- Weather DONE. `fire_event_weather` table (temp, RH, dew point, wind speed/dir/gust,
  precip, pressure). Source Open-Meteo (free, no auth, ERA5-based); swap for
  ERA5/ECMWF with credentials via `OPEN_METEO_URL` + `app/enrich/weather.py`.
  Lazy fetch on event open (backend GET /events/:id calls geoprocessing
  `POST /events/{id}/enrich-weather` when weather missing or older than 1 h), joined
  into the event detail, shown in the DetailsPanel weather section.
- Terrain point query: `GET /elevation?lon=&lat=` (regional 30 m DEM, else global
  2.5 km DEM). DEM click popup on the map.
- Global DEM display layer: `dem_global.cog.tif` (AWS terrain-tiles z5, ~2.5 km).
- Soil moisture + VPD (dryness) added to the current-conditions enrichment via
  Open-Meteo (`soil_moisture_0_to_1cm`, `_3_to_9cm`, `soil_temperature_0cm`,
  `vapour_pressure_deficit`), stored in `fire_event_weather`, shown in the panel
  "Moisture and dryness" section.
- Vegetation NDVI map layer: NASA GIBS MODIS Terra NDVI 8 day (public, no auth,
  `default` time = latest), toggle in Layers control. Colored greenness (visual).
- Vegetation NDVI/NDMI/NBR per-point VALUES: DONE via Copernicus Data Space
  (Sentinel-2 L2A, Sentinel Hub Statistical API). `app/enrich/vegetation.py`:
  OAuth (CDSE_CLIENT_ID/SECRET, token cached), evalscript computes the 3 indices
  with an SCL cloud mask, takes the most recent cloud-free interval over a ~1 year
  window. `fire_event_vegetation` table, `POST /events/{id}/enrich-vegetation`,
  backend lazy fetch (weekly TTL) + join, DetailsPanel "Vegetation" section.
  Note: sandbox clock is 2026 but CDSE has current data (latest scenes ~2026-09).
- Phase 4 is complete.
- Wildfire classification (added before Phase 5): FIRMS anomalies are classified
  (min detections, min FRP, wildland cover) and only `category='wildfire'` events
  show on the map. See [[wildfire-classification]]. This filters what counts as a
  wildfire for the historical dataset and forecasting too.
## Phase 5 status: foundation built
- Common grid: `grid_cell` from PostGIS ST_SquareGrid over a study-area bbox, with
  static features sampled from local COGs at centroids (land cover from
  worldcover_global, terrain from the regional DEM COGs so terrain is null outside
  that extent). `app/training/grid.py`, `POST /training/grid`.
- Leakage-safe samples: `grid_sample`, one row per (cell, prediction_time).
  Features are fire history strictly at or before the cutoff (det_past_24/48/72h,
  frp_past_24h, had_fire); the label `label_fire_next_24h` is fire occurrence in the
  next window (future only). `app/training/samples.py`, `POST /training/samples`.
  Versioned via dataset_version, regeneratable from grid + detections.
- First run: 10,201 cells (southern Africa 30..40E, -20..-10, 0.1 deg), 20,402
  samples over 2 cutoffs, 13.4% positive rate.
- Environmental features DONE: weather + soil moisture + VPD observed AT the cutoff
  (leakage safe) via NASA POWER (free, no auth; Open-Meteo free quota is too small).
  `app/training/weather_hist.py` dedupes cells to POWER's ~0.5 deg grid, fetches
  unique points in parallel, maps back. `POST /training/enrich-weather`. Signal
  checks out: fire-next cells are hotter, drier, lower soil moisture, more prior fire.
- Still to add later: vegetation (Sentinel-2 historical per cell is slow, needs a
  gridded NDVI product), global terrain (sample SRTM mosaic), lightning, human
  activity, perimeters, and longer history (archived FIRMS).

## Phase 6 status: fire-risk model built, refined, and GLOBAL
- `app/model/train.py`: HistGradientBoostingClassifier (handles NaN) on grid_sample
  features (static + fire-history + weather) -> next-24h fire probability.
- Leakage-safe eval: train on earlier cutoffs, test on the latest. Model pickled to
  data/models/. `POST /model/train`, `POST /model/predict` (writes grid_prediction).
- Served: backend `fire_risk` MVT layer (grid_cell JOIN grid_prediction, latest run),
  frontend "Fire risk (24h)" toggle with a green->red legend.
- Numpy pin: base image has Debian numpy 1.26 (pip cannot upgrade), so requirements
  pins numpy<2 for scikit-learn.
- Refinement (done): added `neigh_det_24h` feature (past-24h detections in nearby
  cells, a grid centroid self-join with ST_DWithin, `neighbor_radius_deg` ~1.5x cell
  size). Wrapped the model in CalibratedClassifierCV(isotonic, cv=3) over a stronger
  base (max_iter=400, lr=0.06, l2=1.0) for honest probabilities. New column added to
  db/init/08_grid.sql (grid_sample.neigh_det_24h) for fresh installs.
- Went GLOBAL: grid builder gained `land_only` (drops ocean/no-data cells, i.e.
  landcover NULL or code 80) via COPY-bulk-update then UPDATE FROM (scales). Global
  0.5 deg land grid = 59,311 cells (from 202,601, 143,290 ocean removed).
  118,622 samples over 2 cutoffs, 7.4% positive rate.
- Global run metrics jumped vs the southern-Africa baseline (was ROC-AUC 0.70,
  PR-AUC 0.27, Brier 0.11): ROC-AUC 0.908, PR-AUC 0.586, Brier 0.045 (base rate
  0.074). Neighborhood + fire-history features carry it; weather is null globally
  (per-cell NASA POWER for 59k cells x cutoffs is infeasible, and POWER has no
  gridded/regional endpoint), and HistGB tolerates the NaNs.
- Global pipeline (repeatable):
  `POST /training/grid {"bbox":[-180,-60,180,80],"size_deg":0.5,"land_only":true}` ->
  `POST /training/samples {"version":"v1","neighbor_radius_deg":0.75}` ->
  `POST /model/train {"version":"v1"}` -> `POST /model/predict {"version":"v1"}`.
  Risk written for all 59,311 cells (3,633 above 0.5), spread across all continents;
  fire_risk MVT serves globally (z2 tile ~600 KB). Skip enrich-weather for global.
- Forecast freshness fix (why the risk grid looked "buggy"): the served prediction
  was a single frozen cutoff (max prediction_time in grid_sample), which lags ~1 day
  because sample cutoffs need a full labeled future window. It also never followed the
  24h/48h/72h tabs (those are now()-relative PAST detection filters; risk is a FORWARD
  forecast), so red cells appeared where no current event showed. Two-part fix:
  (1) `predict_live()` in train.py + `POST /model/forecast`: features computed at
  cutoff = latest detection (temp `_fc` table, GiST-indexed centroid, set-based
  neighborhood join), weather left NaN (global model trained that way), writes
  grid_prediction at that fresh cutoff. The scheduler's refresh_fires() now re-issues
  it each cycle (best effort). (2) Backend `GET /risk/meta` returns issued_at + cells;
  the frontend risk legend shows "Forecast issued <UTC>" and states it looks 24h ahead
  and does not follow the detection time filter. Also clarified that ~half the
  high-risk cells sit on active fire (persistence) and the rest are forward/neighbor
  spread, which is expected forecast behavior, not a rendering bug.
## Model strengthening: DONE (2026-10-01)
Completed the calibration + longer-history + vegetation work:
- FIRMS history backfilled to 7 days (09-24..09-30, 245k detections) via per-day
  world pulls (geoprocessing/scripts/backfill_firms.py, retry+backoff). The endpoint
  is flaky; 09-21..09-23 lost all retries, acceptable (7 days >> the original 2.3).
- Grid re-built global (0.5 deg, land_only, 59,311 cells) now sampling vegetation:
  veg_greenness filled for 54,453 cells (92%; nulls are barren/high-lat nodata).
- Re-sampled: 11 prediction-time cutoffs (was 2), 652,421 samples, 7.3% positive.
- Retrained calibrated model (17 features incl veg_greenness). Metrics improved vs the
  2-cutoff baseline (ROC-AUC 0.908 / PR-AUC 0.586 / Brier 0.045):
  ROC-AUC 0.934, PR-AUC 0.581, Brier 0.041, ECE 0.017 (well calibrated),
  train 593k / test 59k rows, test cutoff 09-29 12:00.
- Live forecast re-issued (all 59,311 cells, issued 09-30 12:51). fire_risk MVT serves
  (z2 ~620 KB). Model pickle confirmed 17 features with veg_greenness.
- Known follow-ups (not blocking): events are 'unclassified' (land-cover enrich not
  re-run after the big backfill); per-cell weather still null globally (infeasible).

## RESUME POINT (model strengthening, paused 2026-09-30 for PC shutdown)
Task in flight: "strengthen the model (calibration, more prediction times / longer
history, vegetation features) then start Phase 7". State:
- DONE (persisted on disk / in the gwf_pgdata volume):
  - Vegetation greenness COG built: `data/veg_greenness.cog.tif` (global, EPSG:4326,
    uint8 0..100, nodata 255). Derived from GIBS MODIS_Terra_NDVI_8Day RGB as
    greenness = clip(G-R). No auth. A proxy for NDVI, documented as such.
  - `grid_cell.veg_greenness smallint` added to db/init/08_grid.sql AND to the live
    DB (ALTER TABLE already applied).
  - grid.py samples veg_greenness (added to TERRAIN list + the COPY/_gf update).
  - train.py: veg_greenness added to FEATURES (now 17) and to _SELECT, _LIVE_FEATURES,
    _LIVE_SELECT; _LIVE_N=11. ECE (expected calibration error) + n_cutoffs added to
    train metrics. Calibration (isotonic cv=3) was already in place.
- BACKFILL DONE but PARTIAL (finished 2026-09-30 before shutdown). Detections now
  count 167,316, span 09-25..09-30. Per-day result: 09-30/29/28/27/25 parsed OK;
  09-26, 09-24, 09-23, 09-22, 09-21 FAILED with transient network errors
  (IncompleteRead / read timeout on the large world CSVs). So there is a gap at
  09-26 and nothing before 09-25. Re-run geoprocessing/scripts/backfill_firms.py
  tomorrow to retry the 5 failed days (idempotent, ON CONFLICT DO NOTHING); it may
  need a couple of retries or a longer urlopen timeout / per-day retry loop for the
  flaky fetches. Even as-is, ~6 days >> the original 2.3, so ~9 cutoffs are available.
  Note: clustering ran (6565 events) but they are all 'unclassified' (land-cover
  enrichment not run); the model uses raw detections so this does not block training,
  but run POST /events/enrich + classify if the map's wildfire events should show.
- NOT YET DONE (tomorrow, in order):
  1. Rebuild geoprocessing (running container predates the veg/ECE code edits):
     `docker compose up -d --build geoprocessing`.
  2. (optional) finish the FIRMS backfill for 09-24..09-21 (per-day loop, MSYS_NO_PATHCONV=1
     for docker cp/exec of the /tmp script; open_pool() at top). Or accept ~6 days.
  3. Re-grid global: POST /training/grid {"bbox":[-180,-60,180,80],"size_deg":0.5,
     "land_only":true} (now also samples veg_greenness).
  4. Re-sample: POST /training/samples {"version":"v1","neighbor_radius_deg":0.75}
     (more days -> many more cutoffs -> stronger time split + calibration).
  5. Retrain: POST /model/train {"version":"v1"} (check pr_auc/roc_auc/brier/ece vs
     the ROC-AUC 0.908 / PR-AUC 0.586 / Brier 0.045 baseline).
  6. Re-issue live forecast: POST /model/forecast {"model_version":"m1"}.
  7. Update this memory, then START PHASE 7 (fire-spread forecasting).
- SAFETY: shut down normally or `docker compose stop`. Do NOT `docker compose down -v`
  (wipes gwf_pgdata = all detections/grid/models). Scratchpad backfill.py is session
  temp and may be gone tomorrow; recreate from the notes above if needed.
- Next after this: Phase 7 (fire spread) and Phase 8 (smoke, alerts, production).

## Phase 7 status: fire-spread forecasting built
- Approach: Monte Carlo cellular automaton per active fire complex on a local fine
  grid (~2 km, 0.02 deg), 24h horizon. Spread driven by wind (direction + speed, from
  Open-Meteo current), fuel (WorldCover flammability x veg_greenness) and dryness
  (VPD). Fuel burnout (a cell spreads only while a fresh front, active_steps=4) keeps
  it a moving front, not a blob. Uncertainty = ensemble: fraction of members (default
  30, perturbed wind) that burn a cell is its burn_prob; mean ignition step is arrival_h.
  app/spread/simulate.py, POST /spread/forecast. Fixed RNG seed (no wallclock in CA).
- Tuning: base_p=0.12 gives a realistic probability gradient (not saturation) and
  wind-driven directional elongation (verified: asymmetric extent around the origin).
  First run: 20 complexes (biggest active fires), ~12k burn cells, buckets spread
  across 0.05..1.0. Runs in ~5 s. Guardrail: skips any local grid > 20k cells.
- Storage: db/init/10_spread.sql `fire_spread_forecast` (event_id, geom Polygon 4326,
  burn_prob, arrival_h, horizon_h, run_time, params). Rebuilt per run (delete+insert).
- Served: backend `fire_spread` MVT layer (mvt.js whitelist). Frontend "Fire spread
  (24h)" toggle, yellow->dark-red burn-probability legend, click popup (burn chance +
  arrival time). layers.js SPREAD_LAYER/spreadPaint, MapView, LayersControl, App.
- Scheduler: refresh_fires() now also re-runs forecast_spread() (best effort) so the
  spread map stays fresh alongside FIRMS + risk. Off unless SCHEDULER_ENABLED=true.
- Notes / future: terrain (slope/aspect) is regional so upslope anisotropy is mostly
  neutral globally; ignites from all active complexes. Could add multi-horizon layers
  (6/12/24h), spotting, and firebreak/suppression effects.

## Gotcha: classification depends on enrichment (automated now)
- cluster_detections() does a full recompute (DELETE FROM fire_event), which cascades
  away all context, so after any (re)clustering every event is 'unclassified' until
  land-cover enrichment runs. The map layers fire_events / fire_detections filter to
  category='wildfire', so they come up EMPTY until enrich + classify run. This bit us
  after the big backfill (6563 events all unclassified -> blank layers).
- Fix / automation: both bulk-ingest paths now enrich then classify:
  - scheduler.refresh_fires(): prune -> connector run (cluster) -> enrich_events ->
    classify_events -> live risk forecast -> spread forecast.
  - geoprocessing/scripts/backfill_firms.py: ...COPY days -> cluster -> enrich_events
    -> classify_events.
  (Routine connector runs stay fast; enrichment is orchestrated at these entry points,
  matching the "fast ingest, separate/lazy enrichment" design.)
- After the 2026-10-01 fix: 5659 wildfire + 904 other events; all three vector layers
  (events, detections, spread) serve again. If events ever look blank, check
  `SELECT category, count(*) FROM fire_event GROUP BY 1` and run POST /events/enrich
  then /events/classify.

## Global terrain + weather robustness (2026-10-01, pre-Phase-8)
Fixed "elevation/slope/aspect/weather/moisture/dryness blank for all events":
- Root causes: (1) terrain COGs were REGIONAL (elevation/slope/aspect.cog.tif cover
  only ~60.9-79.3E, 23.8-37.1N; no fires there -> null everywhere). (2) weather is
  lazy on open AND the fetch crashed (500) on Open-Meteo HTTP 429 (free-tier daily
  quota exhausted).
- Weather fix: fetch_weather now catches URLError/timeout and returns None per point
  (graceful). enrich-weather returns 200 {"weather":0} instead of 500. Values stay
  blank until the Open-Meteo quota resets (external limit); kept lazy, not bulk.
- Terrain fix (global): geoprocessing/scripts/build_global_dem.py fetches AWS Terrarium
  tiles (public, no auth) at z5 (~5 km), decodes RGB elevation, mosaics 3857, warps to
  4326, derives slope (gdaldem -s 111120) + aspect, writes dem_global.cog.tif /
  slope_global.cog.tif / aspect_global.cog.tif to /data (persisted in ./data).
  terrain.py now samples regional high-res first, global coarse as fallback.
  Re-sampled all events: elevation 6563/6563, slope 6563/6563, aspect 6553/6563
  (missing = flat areas). Values verified realistic (E African highlands 3566 m, etc).
- Auto for the future: enrich_events() uses sample_terrain (now global), so the
  backfill script and scheduler fill global terrain on new events automatically; the
  re-sample was only to backfill existing events without re-doing slow land cover.
- Caveats: z5 DEM is coarse so slope is smoothed (mostly 0-5 deg); bump DEM_ZOOM to 6/7
  for finer slope (4x/16x tiles). A few Terrarium tiles failed (transient SSL) leaving
  small nodata gaps. The risk-model GRID still samples only regional terrain (grid.py);
  wiring the global DEM there (then re-grid/re-train) is an optional follow-up.

## Phase 8 status: smoke + alerts + hardening DONE (2026-10-01)
- Smoke/air quality (8a): raster overlay of Aerosol Optical Depth (smoke+haze proxy)
  from NASA GIBS MODIS_Combined_Value_Added_AOD (no auth, global, GoogleMapsCompatible
  _Level6). layers.js SMOKE_LAYER + smokeTileUrl() (CAMS-pluggable via
  VITE_SMOKE_TILE_URL), overlay source/layer, MapView visibility, LayersControl toggle
  + legend ("Smoke / aerosol"). User chose GIBS-now; CAMS (ADS key) is the upgrade seam.
- Alerts (8b, in-app): db/init/11_alerts.sql `alert` table (kind/severity/event_id/
  centroid/title/message/value/status, UNIQUE(kind,event_id)). app/alerts/engine.py
  evaluate_alerts(): rules large_fire (wildfire frp_sum >= 2000 warn / 5000 crit, active
  within 24h) and spread_threat (>= 300 cells at burn_prob>=0.5); upserts qualifying,
  resolves stale. POST /alerts/evaluate; scheduler runs it each refresh. Backend GET
  /alerts (sorted critical-first). Frontend AlertsPanel.jsx (bell + badge, list, click
  flies map via App `focus` -> MapView flyTo + opens event). First run: 9 critical, 19
  warning. NOTE psycopg: literal % in SQL must be %% (hit this in the spread message).
- Hardening (8c, backend): helmet (CSP off since JSON/MVT; CORP cross-origin so the
  separate-origin frontend can read tiles; HSTS/nosniff/frameguard), compression (gzip),
  express-rate-limit (600/min on /events /risk /alerts /elevation; /tiles + /health
  exempt so the map is never throttled), express.json limit 1mb, /health/live (liveness)
  + / (readiness, DB ping), graceful SIGTERM/SIGINT shutdown (drain + pool.end), error
  handler returns generic message on 5xx (no SQL/stack leak). Added deps: helmet,
  compression, express-rate-limit.
- Remaining (deployment-time, not app code): frontend PROD build (currently Vite dev
  server + HMR mount; swap to vite build + static/nginx for prod), TLS/reverse proxy,
  metrics/monitoring. Geoprocessing stays internal (backend proxies it).
- All 8 phases complete. Browser needs one refresh to load the smoke base-style source
  and the AlertsPanel.

## Final developer rule (from proposal)
Do not start with AI. Make the data pipeline reliable first: every fire has a
source, time, location, and quality. Enrich, then build the training set, then
train models.
