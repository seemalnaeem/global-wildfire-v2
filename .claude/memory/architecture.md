# Memory: architecture

## Services and ports
- **db**: PostgreSQL 16 + PostGIS 3.4, database `global-wildfire`, host port 5440.
- **backend**: Express, port 3040. REST + `ST_AsMVT` vector tiles.
- **geoprocessing**: FastAPI + GDAL/OGR, port 3041. Ingest and analysis.
- **titiler**: upstream TiTiler image, port 3042. Serves COG raster tiles.
- **frontend**: React + Vite + Tailwind, port 5180. MapLibre GL map.

## Data flow
- Vectors: source file -> `ogr2ogr` -> PostGIS (4326) -> backend `ST_AsMVT` (3857)
  -> MapLibre vector source.
- Rasters: source GeoTIFF -> `gdal_translate -of COG` -> `data/` volume -> TiTiler
  -> MapLibre raster source.

## Boundaries
- Raster tiling is TiTiler only, never Express.
- Heavy geoprocessing is the FastAPI service only, never Express.
- Shared constants and helpers live in `shared/` (js and py), imported everywhere.

## SRIDs
Storage EPSG:4326. Tiling EPSG:3857 via `ST_Transform` / `ST_TileEnvelope`.
