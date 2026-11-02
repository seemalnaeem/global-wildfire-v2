# Memory: glossary

- **MVT**: Mapbox Vector Tile, protobuf vector tile format. Built by `ST_AsMVT`.
- **ST_AsMVT / ST_AsMVTGeom / ST_TileEnvelope**: PostGIS functions that build a
  vector tile and its geometry for a given z/x/y.
- **COG**: Cloud Optimized GeoTIFF, internally tiled and with overviews, streamable
  by range request. Made with `gdal_translate -of COG`.
- **TiTiler**: FastAPI dynamic tile server for COGs. Serves `/cog/tiles/...`.
- **GDAL / OGR**: raster (GDAL) and vector (OGR) geospatial toolkit. `gdal_translate`,
  `gdalwarp`, `gdaladdo`, `ogr2ogr`, `ogrinfo`.
- **osgeo**: Python bindings for GDAL/OGR.
- **EPSG:4326**: lon/lat WGS84, our storage SRID.
- **EPSG:3857**: web mercator, our tiling SRID.
- **GiST index**: spatial index type for geometry columns.
- **PERN**: PostgreSQL, Express, React, Node. Plus a Python FastAPI service here.
