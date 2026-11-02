# Memory: decisions

Durable choices and the reason behind each.

- **Vectors via `ST_AsMVT`, not GeoJSON**: MVT is compact and fast at scale, tiles
  cache well, PostGIS builds them in the database.
- **Rasters via TiTiler + COG, not tiles in Express**: TiTiler is purpose built for
  dynamic COG tiling, keeps Node out of raster IO.
- **GDAL CLI for bulk, osgeo/rasterio for logic**: CLI is faster and memory safe for
  multi-GB files; bindings are clearer for per-pixel logic.
- **Store 4326, tile 3857**: one canonical storage SRID, reproject at tile time.
- **react-icons, not lucide**: project standard, explicitly required.
- **Tailwind + Vite**: utility CSS and fast dev server, no CSS modules.
- **Fixed ports (5440 / 3040 / 3041 / 3042 / 5180)**: required by the environment,
  wired into compose and env.
- **Self contained**: no cross-project imports, all context lives in this repo.
- **slope.tif is ~4.9 GB**: must use BIGTIFF, tiling, overviews, and streaming.
- **Clustering is set based, not per-row**: attach to nearest event, then DBSCAN new
  clusters into a temp table with sequence-preallocated ids, then bulk insert and
  assign. Handles world-sized FIRMS batches (about 17k/day) in under a minute.
- **Mapbox basemap through MapLibre**: use Mapbox raster tiles as the basemap, keep
  MapLibre as the renderer. Architecture stays React + MapLibre + Vite.
- **Secrets live in `.env` only**: FIRMS key, Mapbox token, and CDSE client
  id/secret are gitignored. `.env.example` holds placeholders. Never commit keys.
- **Only wildfires shown on the map**: FIRMS detects all thermal anomalies, so
  events are classified (min detections, min FRP, wildland cover) and the map shows
  `category='wildfire'` only. See [[wildfire-classification]]. Thresholds are env
  tunable and re-runnable without re-clustering.
