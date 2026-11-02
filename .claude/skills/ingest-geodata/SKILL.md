---
name: ingest-geodata
description: Load a vector or raster source into the portal with GDAL/OGR. Use when a new data source arrives and must land in PostGIS or become a COG.
---

# Ingest geodata

Decide the type first, then follow the matching path. Always target EPSG:4326.

## Vector to PostGIS (geoprocessing + db agents)
```bash
ogrinfo -so -al source.<ext>          # inspect layers, srs, fields
ogr2ogr -f PostgreSQL "PG:$DATABASE_URL" source.<ext> \
  -nln <table> -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 \
  -lco GEOMETRY_NAME=geom -lco FID=id -lco PRECISION=NO
```
Then add a GiST index on `geom` and expose it with the `add-vector-layer` skill.

## Raster to COG (geoprocessing agent)
```bash
gdalinfo source.tif                   # check srs, bands, size, nodata
gdal_translate source.tif data/<name>.cog.tif -of COG \
  -co COMPRESS=DEFLATE -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS
```
Then expose it with the `add-raster-layer` skill.

## API sources
If the source is an external API, first check `.claude/memory/data-sources.md` for
whether we process it or proxy it live. Only process what the codebase needs.

## Verify
Vector: row count and `ST_IsValid`. Raster: `rio cogeo validate`.
