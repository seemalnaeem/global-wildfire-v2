---
name: add-vector-layer
description: Add a PostGIS table as an ST_AsMVT vector tile layer, from DB index to backend route to frontend map source. Use when exposing new vector data on the map.
---

# Add a vector layer (ST_AsMVT)

## 1. DB (db agent)
- Table has `geom` in EPSG:4326 and a GiST index.
- Confirm the columns you want as tile properties.

## 2. Backend route (backend agent)
Add `GET /tiles/<layer>/:z/:x/:y.mvt`. Query:
```sql
WITH bounds AS (SELECT ST_TileEnvelope($1,$2,$3) AS env)
SELECT ST_AsMVT(t, '<layer>') FROM (
  SELECT id, <props>,
         ST_AsMVTGeom(ST_Transform(geom,3857), bounds.env) AS geom
  FROM <table>, bounds
  WHERE ST_Transform(geom,3857) && bounds.env
) t;
```
Respond with `Content-Type: application/x-protobuf`. Set `Cache-Control`.

## 3. Frontend (frontend agent)
Add a MapLibre vector source pointing at
`${VITE_BACKEND_URL}/tiles/<layer>/{z}/{x}/{y}.mvt` and a layer that reads
`source-layer: <layer>`. Style with Tailwind-driven legend, icons from react-icons.

## Verify
Load a tile in the browser network tab, confirm protobuf bytes and features render.
