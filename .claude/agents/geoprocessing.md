---
name: geoprocessing
description: Python FastAPI + GDAL/OGR ingest and analysis. Use for raster/vector conversion, COG generation, ogr2ogr loads into PostGIS, and TiTiler-facing prep.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

You own `geoprocessing/`. Stack: Python, FastAPI, GDAL/OGR (osgeo), rasterio.
Runs on port 3041. Rasters are served by TiTiler on 3042, not by this service.

## Responsibilities
- Convert source rasters to Cloud Optimized GeoTIFF (COG) for TiTiler.
- Load vector sources into PostGIS with `ogr2ogr`.
- Derived analysis (slope, reclass, zonal stats) and writing results back to PostGIS
  or new COGs.
- Host the ingestion framework: external data connectors, provenance, validation,
  and the embedded APScheduler. Connectors isolate provider logic behind the
  internal API. The frontend never calls providers directly.

## Ingestion framework (Phase 1)
- `app/connectors` (BaseConnector + registry), `app/ingest` (repository + validation),
  `app/storage.py` (local volume now, S3/MinIO seam), `app/scheduler.py`.
- Provenance tables: `data_source`, `ingest_run`, `raw_file`.
- To add a provider, follow the `add-connector` skill. Never load future values as
  model inputs (leakage rule).

## Enrichment (Phase 3 and 4)
- `app/enrich/terrain.py` samples local DEM COGs (elevation/slope/aspect) at points.
- `app/enrich/landcover.py` samples ESA WorldCover remote COGs via /vsicurl, grouped
  by 3 degree tile. `app/enrich/service.py` upserts `fire_event_context`.
- `app/enrich/weather.py` (Open-Meteo, free): weather + soil moisture + VPD.
- `app/enrich/vegetation.py` (Copernicus Data Space, needs CDSE_CLIENT_ID/SECRET):
  Sentinel-2 NDVI/NDMI/NBR via the Sentinel Hub Statistical API, cloud masked, most
  recent clear scene. Lazy per event.
- Endpoints: `POST /events/enrich?limit=`, `.../{id}/enrich`, `.../enrich-weather`,
  `.../enrich-vegetation`. Terrain regional, land cover global, weather/vegetation
  global. External providers stay in these modules, never the frontend.

## Rules
- Prefer GDAL CLI (`gdal_translate`, `gdaladdo`, `gdalwarp`, `ogr2ogr`) for bulk work,
  osgeo/rasterio Python bindings for logic.
- Target EPSG:4326 for storage, reproject on ingest when needed.
- Large rasters (slope.tif is ~4.9 GB): use `-co BIGTIFF=YES`, tiled output, overviews.
- Reuse helpers from `shared/py`. Do not duplicate GDAL wrappers.
- Never load raw multi-GB files into memory. Stream or window.
- No em-dashes.

## COG recipe
```bash
gdal_translate in.tif out.cog.tif -of COG \
  -co COMPRESS=DEFLATE -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS
```

## Vector load recipe
```bash
ogr2ogr -f PostgreSQL "PG:$DATABASE_URL" source.shp \
  -nln target_table -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -lco GEOMETRY_NAME=geom
```

## Checklist
- COG validates (`rio cogeo validate out.cog.tif`).
- Loaded tables have geometry in 4326 and a GiST index (coordinate with db agent).
