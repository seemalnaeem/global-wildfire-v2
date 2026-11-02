---
name: add-raster-layer
description: Publish a raster as TiTiler tiles, from COG conversion to frontend tile layer. Use when adding elevation, slope, or any GeoTIFF to the map.
---

# Add a raster layer (TiTiler)

## 1. Make a COG (geoprocessing agent)
```bash
gdal_translate data/<name>.tif data/<name>.cog.tif -of COG \
  -co COMPRESS=DEFLATE -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS
rio cogeo validate data/<name>.cog.tif
```
COGs live in `data/` and are mounted read-only into TiTiler at `/data`.

## 2. TiTiler tile URL
TiTiler needs the TileMatrixSet in the path:
`/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=/data/<name>.cog.tif`.
Add colormap/rescale as query params, for example
`&colormap_name=terrain&rescale=0,3000`.

## 3. Frontend (frontend agent)
Use `cogTemplate()` from `#shared` (it inserts `WebMercatorQuad`) to build the
MapLibre raster source. Expose opacity and colormap controls, icons from react-icons.

## Verify
- `GET :3042/cog/info?url=/data/<name>.cog.tif` returns metadata.
- `GET :3042/cog/WebMercatorQuad/tilejson.json?url=...` gives min/max zoom and bounds.
- A tile in the bounds returns a PNG (200). Outside the bounds returns 404, expected.
