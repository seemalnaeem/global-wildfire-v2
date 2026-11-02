# How FIRMS Points Are Filtered

This document describes how fire detection points from NASA FIRMS are filtered
before they are stored in the database. It reflects the logic in
[ingest_firms_noaa20_last5days.py](ingest_firms_noaa20_last5days.py).

## Source of the data

- **Provider:** NASA FIRMS (Fire Information for Resource Management System)
- **Dataset:** `VIIRS_NOAA20_NRT` — VIIRS active-fire detections from the
  NOAA-20 satellite, Near Real-Time (NRT) product.
- **Coverage:** `world` (global)
- **Time window:** the last **5 days**
- **Endpoint:** the FIRMS Area API returns a CSV file, which is streamed and
  parsed row by row ([ingest_firms_noaa20_last5days.py:55-61](ingest_firms_noaa20_last5days.py#L55-L61)).

Every row in the CSV is one candidate fire-detection point. Each point is
evaluated against the filters below, in order. A point is **kept** only if it
passes *all* of the checks; otherwise it is discarded (`continue`) and never
inserted.

## The filtering pipeline

Filtering happens in the per-row loop at
[ingest_firms_noaa20_last5days.py:61-74](ingest_firms_noaa20_last5days.py#L61-L74).

### 1. Validity / completeness filter (implicit)

Three fields are parsed up front:

| Field       | Parsed as | Used for |
|-------------|-----------|----------|
| `latitude`  | float     | location |
| `longitude` | float     | location |
| `frp`       | float     | Fire Radiative Power |

```python
if lat is None or lon is None or frp is None:
    continue
```

A point is **dropped** if any of latitude, longitude, or FRP is missing,
blank, `"NA"`, or otherwise not parseable as a number. The `to_float()` helper
returns `None` for those cases, so a point with no usable coordinates or no FRP
value cannot proceed. This guarantees every stored point has a real location
and a real fire-intensity value.

### 2. Fire Radiative Power (FRP) threshold

```python
if frp <= 2:
    continue
```

Points with **FRP of 2 (megawatts) or less** are dropped. FRP is a measure of
how much energy the fire is radiating, i.e. its intensity. This threshold
removes very weak/low-energy detections that are more likely to be noise,
tiny/insignificant heat sources, or false alarms, keeping only detections
representing meaningful fire activity (FRP strictly greater than 2).

### 3. Confidence filter

```python
conf = (row.get("confidence") or "").strip().lower()
...
if conf not in ("n", "h"):
    continue
```

FIRMS assigns each VIIRS detection a confidence class:

- `l` — **low** confidence
- `n` — **nominal** confidence
- `h` — **high** confidence

Only **nominal (`n`)** and **high (`h`)** detections are kept. **Low (`l`)**
confidence points — and anything with a blank or unrecognized confidence value
— are discarded. The value is normalized (`strip().lower()`) before comparison,
so casing or stray whitespace in the source data does not affect the result.

## Summary: a point is kept only if all of these are true

1. `latitude`, `longitude`, and `frp` are all present and numeric.
2. `frp > 2`.
3. `confidence` is `n` (nominal) or `h` (high).

Points that pass all three are collected and upserted into the
`firms_viirs_noaa20_nrt` table. If no points survive filtering, the script
reports `"No rows after filtering."` and inserts nothing
([ingest_firms_noaa20_last5days.py:94-96](ingest_firms_noaa20_last5days.py#L94-L96)).

## What is stored (not a filter, but for reference)

For each surviving point the following columns are written:
`dataset, latitude, longitude, acq_date, acq_time, satellite, instrument,
confidence, frp, bright_ti4, bright_ti5, scan, track, version, daynight`.

Inserts use an **upsert** keyed on
`(dataset, acq_date, acq_time, latitude, longitude)`, so re-running the ingest
for overlapping time windows updates existing points instead of creating
duplicates ([ingest_firms_noaa20_last5days.py:20-40](ingest_firms_noaa20_last5days.py#L20-L40)).

---

# How Clusters Form and Become "Events"

Once filtered points are on the map, the frontend groups nearby detections into
**wildfire incidents** (called *events*). This is done in
[index.js](index.js). The same logic runs twice: for the **24-hour** view
(`updateWildfireIncidents`,
[index.js:162-271](index.js#L162-L271)) and for the **5-day** view
(`updateWildfireIncidents5`,
[index.js:561-626](index.js#L561-L626)). They behave the same except for one
extra merge step in the 24-hour path.

## Configuration

All thresholds come from `WILDFIRE_CONFIG`
([index.js:6-12](index.js#L6-L12)):

| Setting           | Value    | Meaning |
|-------------------|----------|---------|
| `clusterRadiusKm` | `1` km   | DBSCAN neighborhood radius — how close points must be to join a cluster |
| `minPoints`       | `5`      | minimum detections needed to form a cluster |
| `minClusterFRP`   | `20` MW  | minimum combined FRP for a cluster to become an event |
| `pointBufferKm`   | `0.75`   | per-point buffer (rendering) |
| `matchDistanceKm` | `5`      | proximity used for matching/merging |

## Step 1 — DBSCAN clustering

Points are grouped using Turf.js **DBSCAN**
([index.js:175-179](index.js#L175-L179)):

```js
clustered = turf.clustersDbscan(
  geojson,
  WILDFIRE_CONFIG.clusterRadiusKm,   // 1 km
  { minPoints: WILDFIRE_CONFIG.minPoints, units: "kilometers" }  // 5
);
```

DBSCAN (Density-Based Spatial Clustering) assigns every point either:

- a **cluster id** — if it lies within **1 km** of enough neighbors to reach the
  **5-point** density threshold, or
- **noise** — if it is too isolated (no `cluster` property).

So a cluster is essentially *"a dense knot of at least 5 fire detections, each
within 1 km of the group."* Isolated or sparse detections are treated as noise
and never become events.

## Step 2 — Group points by cluster id

Each returned feature carries `properties.cluster`. Points are bucketed by that
id, and **noise points (no cluster id) are dropped**
([index.js:186-192](index.js#L186-L192) /
[index.js:574-580](index.js#L574-L580)):

```js
clustered.features.forEach(f => {
  const cid = f.properties.cluster;
  if (cid === undefined || cid === null) return; // noise points
  clusters[cid] = clusters[cid] || [];
  clusters[cid].push(f);
});
```

## Step 3 — Turn each qualifying cluster into one event

For every cluster ([index.js:195-233](index.js#L195-L233)):

1. **Sum the FRP** of all its points.
2. **FRP gate** — if the combined FRP is below **20 MW**, the cluster is
   discarded (`if (frpSum < WILDFIRE_CONFIG.minClusterFRP) return;`). This drops
   dense-but-weak clusters so only energetically significant fires become
   events.
3. **Deduplicate** points inside the cluster using a key built from
   `acq_date | acq_time | satellite | lon | lat`
   (`makePointKey`, [index.js:135-144](index.js#L135-L144)) — this prevents the
   same detection being counted twice.
4. **Build geometry** — a `centroid` (event center) and a `boundary` polygon.

Each surviving cluster becomes **exactly one incident/event object** stored in
`wildfireIncidents` (24 h) or `wildfireIncidents5` (5 day), with a stable id
`WF24-<clusterId>` or `WF5-<clusterId>`
([index.js:220-232](index.js#L220-L232) /
[index.js:609-620](index.js#L609-L620)):

```js
const incident = {
  id: `WF24-${cid}`,
  points: uniq,        // deduped detections in this event
  frpSum,              // total Fire Radiative Power
  centroid,            // event center point
  boundary,            // event area polygon
  created, updated,
  country: "Unknown"   // resolved later during table render
};
```

### How the event boundary polygon is built

`buildIncidentPolygon` ([index.js:147-160](index.js#L147-L160)) draws the event
footprint by:

1. computing a **convex hull** around the cluster's points,
2. falling back to a **bounding-box polygon** if the hull fails, then
3. applying a small **0.4 km buffer** so the area reads as a shape rather than a
   thin line.

## Step 4 — Merge adjacent events (24-hour view only)

Because DBSCAN can split one physical fire into neighboring clusters, the
24-hour path runs a cleanup pass ([index.js:237-266](index.js#L237-L266)): any
two events whose **boundaries intersect** *and* whose **centroids are within
2.5 km** are merged into a single event (points combined, FRP summed, geometry
rebuilt). The 5-day path does not do this extra merge.

## Step 5 — Rendered as events

Each incident is drawn on the map (`renderWildfireLayer` / `...Layer5`) and
listed as a row in the **events table** (`renderWildfireTable` / `...Table5`),
which shows the country, detection count (`points.length`), total Fire Radiative
Power (`frpSum`), and last-updated time
([index.js:395-417](index.js#L395-L417) /
[index.js:484-505](index.js#L484-L505)).

## Summary: a cluster becomes an event only if

1. DBSCAN groups **≥ 5 detections** each within **1 km** of the group
   (isolated/noise points excluded), and
2. the cluster's **combined FRP ≥ 20 MW**.

Qualifying clusters are deduplicated, given a centroid + buffered hull polygon,
(24 h) merged with any overlapping neighbor within 2.5 km, and then surfaced as
one row in the events table and one shape on the map.
