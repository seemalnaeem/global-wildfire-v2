# Playbook: debug tiles

When a layer does not render, isolate the failing stage.

## Vector (ST_AsMVT)
1. **DB**: run the tile query in `psql` for a known z/x/y over the data extent.
   Empty result means bad bbox filter, wrong SRID, or no data there.
2. **Backend**: `curl -s ':3040/tiles/<layer>/<z>/<x>/<y>.mvt' | wc -c`. Zero bytes
   means the query returned nothing. Check `Content-Type: application/x-protobuf`.
3. **Frontend**: confirm `source-layer` matches the `ST_AsMVT` layer name exactly.
   Check the zoom range and that the source URL uses `VITE_BACKEND_URL`.

## Raster (TiTiler)
1. `curl ':3042/cog/info?url=/data/<name>.cog.tif'`. Error means the COG path is
   wrong or the file is not a valid COG (`rio cogeo validate`).
2. Tiles need the matrix set in the path:
   `/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=...`. A bare `/cog/tiles/{z}/...`
   returns `{"detail":"Not Found"}`. A 404 on a valid path means the tile is outside
   the data bounds (check `/cog/WebMercatorQuad/tilejson.json`). If blank, check
   `rescale` and `nodata`.
3. Frontend: confirm the raster source tile template and opacity.

## Common causes
- Geometry in 4326 but tiled without `ST_Transform` to 3857.
- Missing GiST index makes tiles slow, not empty.
- CORS blocked: check the middleware allowlist for origin 5180.
