---
name: backend
description: Node.js + Express REST API and ST_AsMVT vector tile endpoints. Use for routes, controllers, DB queries, and tile serving on the 3040 port range.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

You own `backend/`. Stack: Node.js, Express, `pg` (node-postgres).

## Rules
- Runs on port 3040. Do not move off the 3040 range.
- Vector tiles are served from PostGIS `ST_AsMVT`. Return `application/x-protobuf`.
  See `.claude/skills/add-vector-layer`.
- Use a shared `pg` pool from `backend/src/db/pool.js`. Never open ad hoc clients.
- Parameterize every query. No string interpolation of user input into SQL.
- Reuse `shared/js` constants (SRIDs, tile sizes). Do not redefine them.
- Do raster work through TiTiler, not in Express. Do heavy geoprocessing through
  the FastAPI service, not here.
- No em-dashes.

## Tile endpoint contract
`GET /tiles/:layer/:z/:x/:y.mvt` returns MVT bytes. `z/x/y` are validated integers.
Query PostGIS with `ST_TileEnvelope(z, x, y)` and `ST_AsMVT`. Layers are whitelisted
in `src/tiles/mvt.js` (table, geometry column, props, optional time column). Layers
with a time column accept `?from`/`?to` (ISO) time filtering.

## Fire events (Phase 2)
- Layers: `fire_detections` (geom), `fire_events` (centroid). Both time filterable.
- `GET /events?limit=` recent events. `GET /events/:id` returns the event plus its
  detections for the details panel. Coordinates via `ST_X`/`ST_Y`.

## Point queries
- `GET /elevation?lon=&lat=` returns elevation in meters at a point. Queries TiTiler
  `/cog/point`, preferring the precise regional DEM and falling back to the global
  DEM (`source` field says which). Used by the DEM click popup on the map.

## Where things go
- Routes: `backend/src/routes`
- Controllers: `backend/src/controllers`
- DB pool and SQL: `backend/src/db`
- Tile logic: `backend/src/tiles`

## Checklist
- Health route `GET /health` returns 200.
- Tiles return protobuf with correct content type.
- All queries parameterized and use the shared pool.
