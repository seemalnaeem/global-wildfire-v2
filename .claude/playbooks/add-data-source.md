# Playbook: add a data source

Use when a new vector, raster, or external API source arrives.

## 1. Classify
- Vector file (shp, geojson, gpkg) to PostGIS.
- Raster file (GeoTIFF) to COG for TiTiler.
- External API: decide process vs proxy. Check `.claude/memory/data-sources.md`.
  Only process sources the codebase actually needs.

## 2. Inspect
- Vector: `ogrinfo -so -al <file>`.
- Raster: `gdalinfo <file>`.
Record SRS, extent, fields, band count, nodata.

## 3. Ingest
Follow the `ingest-geodata` skill. Target EPSG:4326 storage.

## 4. Expose
- Vector: `add-vector-layer` skill (DB index, backend MVT route, frontend source).
- Raster: `add-raster-layer` skill (COG, TiTiler URL, frontend raster source).

## 5. Record
Append the source to `.claude/memory/data-sources.md`: name, type, srs, table or
COG path, and whether we process or proxy it.
