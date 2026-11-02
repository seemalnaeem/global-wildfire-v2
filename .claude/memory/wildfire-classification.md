# Memory: event formation and wildfire classification

Follows `FIRMS_point_filtering.md`. Two stages: what becomes an event, then which
events are wildfires. FIRMS detects every thermal anomaly (flares, industrial,
agricultural burns, volcanoes), so both stages filter hard.

## Stage 1: point filter (ingest and clustering input)
Keep a detection only if `frp > FIRMS_MIN_FRP` (default 2) and confidence in
`n` (nominal) or `h` (high). Applied at ingest (`firms.py`) and again as the
clustering input WHERE (`cluster.py`), so raw detections stay stored for
provenance but weak / low-confidence ones never form events.

## Stage 2: event formation (`app/events/cluster.py`)
Full recompute over all detections (the document recomputes each run):
1. DBSCAN, `eps = FIRE_CLUSTER_DISTANCE_M` (1000 m), `minpoints =
   FIRE_CLUSTER_MIN_POINTS` (5). Noise / isolated detections do not become events.
2. FRP-sum gate: a cluster becomes an event only if `sum(frp) >=
   FIRE_MIN_CLUSTER_FRP` (20 MW). Stored in `fire_event.frp_sum`.
3. Merge pass: events whose `boundary` intersect and whose centroids are within
   `FIRE_MERGE_DISTANCE_M` (2500 m) are merged (DBSCAN can split a fire).
`fire_event.boundary` is the convex hull buffered by `FIRE_BOUNDARY_BUFFER_M`
(400 m) so it reads as a footprint. The map renders events as this polygon (fill +
red outline), not a circle. `fire_events` tile serves `boundary` as its geometry.
Cost: this DELETEs and rebuilds `fire_event`, so enrichment (context/weather/veg)
cascades away and must be repopulated after. New FIRMS events are unclassified
until land cover is enriched, then re-classify.

## Stage 3: wildfire classification (`app/events/classify.py`)
Density and energy are already gated, so classification only checks the surface:
`category = 'wildfire'` if `landcover_code IN WILDFIRE_LANDCOVER_CODES`
(default 10,20,30 = tree, shrub, grass), else `other`, or `unclassified` when land
cover is missing. Endpoint `POST /events/classify`.

## Map
Backend tiles show wildfires only: `fire_events WHERE category='wildfire'`,
`fire_detections WHERE event_id IN (wildfire events)`. Event detail and panel show
`frp_sum` (total FRP), `max_frp`, `detection_count`, and a "Wildfire" badge.

## Numbers (current dataset, ~138k raw detections)
Old loose clustering: 44,536 events. New technique: 3,803 events (all >=5 detections
and >=20 MW), of which 3,325 wildfire, 478 other. Tune via the env vars, restart
geoprocessing, then re-cluster + enrich + classify.

## Pipeline order to re-run
`POST /events/cluster` -> `POST /events/enrich?limit=N` (land cover) ->
`POST /events/classify`.
