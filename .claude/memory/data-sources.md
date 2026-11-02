# Memory: data sources

Track every source: type, SRS, destination, and process vs proxy. Append on ingest.

## Rasters (local, in `data/`)
| Name      | File              | Size    | SRS       | Status                     |
|-----------|-------------------|---------|-----------|----------------------------|
| Elevation | elevation.cog.tif | ~1.3 GB | EPSG:4326 | COG built, validated, served|
| Slope     | slope.cog.tif     | ~3.3 GB | EPSG:4326 | COG built, validated, served|

- elevation: 66368x47807, int16, band `b1`. Data extent is regional, roughly
  lon 60.87..79.31, lat 23.81..37.09 (Pakistan / Central Asia), not global. Tiles
  outside that box return 404, which is expected. Serve zoom 4..12.
  Serve URL: `/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=/data/elevation.cog.tif`.
- slope: same 66368x47807 grid, Float32, nodata -9999, same extent as elevation.
  Serve URL: `/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=/data/slope.cog.tif`.
  Suggested rescale 0,60 (degrees of slope).
- aspect (Phase 3): `aspect.cog.tif`, derived with `gdaldem aspect` from elevation,
  degrees 0..360, same regional extent. Served by TiTiler.
  NOTE: when writing a build script from Windows, strip CRLF (`sed -i 's/\r$//'`)
  and pass container paths inside `bash -lc '...'` so Git Bash does not mangle them.
- The regional `elevation.cog.tif` (30 m, 1 arc-sec, user provided) stays for terrain
  enrichment (elevation/slope/aspect sampling). A coarse global COG existed briefly
  (AWS terrain-tiles z5) but was removed: the DEM is SRTM 30 m only now.
- **SRTM GL1 30 m** (the DEM layer + point queries): USGS/NASA SRTM 1 arc-second,
  public no-auth via OpenTopography S3
  (`https://opentopography.s3.sdsc.edu/raster/SRTM_GL1/...`). Served DYNAMICALLY by
  TiTiler (a global 30 m COG would be terabytes). Reproduce: download the ready-made
  global VRT `SRTM_GL1_srtm.vrt`, rewrite its relative `SRTM_GL1_srtm/<tile>.tif`
  paths to absolute `/vsicurl/...` (`/data/srtm_global.vrt`), then build a
  quadkey-indexed MosaicJSON over the 14,280 tiles (`/data/srtm_mosaic.json`, quadkey
  zoom 7) so TiTiler's `/mosaicjson` endpoint only reads the few tiles a map tile
  needs. Flat-VRT serving was ~8 s/tile (re-parsed 14k sources); the mosaic is
  ~2-4 s cold, ~2 s warm over this slow link (sub-second on a fast network).
  TiTiler needs VSI caching env (see docker-compose titiler). Covers 60N-56S.
  Frontend DEM layer is SRTM 30 m only, gated to layer minzoom 6 (30 m is too many
  tiles to serve at global zoom over this slow link). `/elevation` uses SRTM only
  (null outside 60N-56S, e.g. oceans and high latitudes).

## Land cover (ESA WorldCover, Phase 3)
Public global 10 m land cover, 2020 baseline, no auth. COGs on AWS Open Data in
3 degree tiles: `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/
map/ESA_WorldCover_10m_2020_v100_{TILE}_Map.tif`. Chosen over Copernicus LCM-10
because LCM-10 needs registration; WorldCover is open and global.

Two uses:
- **Per-event value**: sampled at event centroids (`app/enrich/landcover.py`), full
  10 m, remote /vsicurl, grouped by tile, parallel. Global coverage.
- **Map layer**: `data/worldcover_global.cog.tif`, a downsampled (~1.1 km, mode)
  GLOBAL COG (36000x14400, palette preserved, ~20 MB). Served by TiTiler, fast
  (~50 ms) worldwide. Toggle in the map Layers control with a class legend.
  Build: global VRT over all ~2651 tiles, then 6 parallel gdalwarp bands (60 deg
  lon each) merged to a COG (single warp was too slow, ~70 min, latency bound).
  A ~110 m regional COG (`worldcover.cog.tif`) also exists for higher detail.
  IMPORTANT: the band warps MUST set HTTP retries or transient S3 failures (DNS,
  bad reads) abort a band and leave nodata gaps. Use
  `GDAL_HTTP_MAX_RETRY=10 GDAL_HTTP_RETRY_DELAY=2 GDAL_HTTP_TIMEOUT=60` plus a
  per-band retry loop that checks for `100 - done` before merging. Two bands (3, 5)
  failed silently on the first build and had to be re-warped.

## Vectors
None loaded yet. Add rows as sources arrive: name, table, srs, geometry type.

## Ingestion framework (Phase 1)
External sources are ingested through connectors in the FastAPI service, not the
frontend. Every fetch is recorded: `data_source` (registry), `ingest_run` (audit),
`raw_file` (provenance, points at the stored original). Originals are saved to
object storage (local `/data/objstore` now, MinIO later). Add providers with the
`add-connector` skill. The `demo` connector proves the loop; FIRMS is Phase 2.

## External APIs
- **NASA FIRMS / VIIRS** (Phase 2, live): connector `firms_viirs`. Live via the
  FIRMS area API when `FIRMS_MAP_KEY` is set (source `VIIRS_SNPP_NRT`, area, days
  from env), else offline sample mode. Lands in `fire_detection`, grouped into
  `fire_event`. Key held in `.env` (not committed). World/1day VIIRS is about
  17k detections and clusters to about 5k events in under a minute (set based).

## Basemap (Mapbox)
Frontend uses a Mapbox raster basemap via MapLibre when `VITE_MAPBOX_TOKEN` is set
(`.env`), else a plain dark background. The token must have the `styles:tiles`
scope and allow the app URL (add `http://localhost:5180` to the token's allowed
URLs in the Mapbox account). A token that is valid but URL/scope restricted returns
`Not Authorized - Invalid Token` on tile requests and the basemap stays blank.

- **Open-Meteo** (Phase 4, weather + moisture): free, no auth, ERA5-based. Fetches
  current temp, RH, dew point, wind speed/dir/gusts, precip, pressure, plus soil
  moisture (0-1 cm, 3-9 cm), soil temperature, and VPD at fire points
  (`app/enrich/weather.py`, batchable). Stand-in for ERA5/ECMWF + NASA-USDA soil
  moisture; swap via `OPEN_METEO_URL` when credentials are available.
- **NASA GIBS MODIS NDVI** (Phase 4, vegetation layer): MODIS Terra NDVI 8 day WMTS,
  public, no auth, global. Frontend NDVI map layer via `ndviTileUrl` (GIBS EPSG:3857
  REST WMTS, `default` time = latest, GoogleMapsCompatible_Level9, ~250 m). Visual only.
- **Copernicus Data Space / Sentinel Hub** (Phase 4, vegetation values): Sentinel-2
  L2A per-point NDVI/NDMI/NBR. OAuth client credentials in `.env`
  (`CDSE_CLIENT_ID`/`CDSE_CLIENT_SECRET`), token at
  identity.dataspace.copernicus.eu, Statistical API at sh.dataspace.copernicus.eu.
  `app/enrich/vegetation.py` runs an evalscript (SCL cloud mask) over a ~1 year
  window, P30D intervals, and returns the most recent cloud-free interval. Stats
  come back as strings (skip "NaN"). SH Catalog `sortby` is rejected, so we let the
  Statistical API discover the time. Lazy on event open, weekly refresh.

When a new API arrives, decide:
- **Process**: fetch, transform, store in PostGIS or as COG (only if the codebase
  needs it persisted or analyzed).
- **Proxy**: pass through live via backend, no storage (for volatile feeds).

Record the decision and endpoint here so it is not re-litigated.
