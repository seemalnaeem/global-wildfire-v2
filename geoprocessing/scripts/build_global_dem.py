"""Build global elevation + slope + aspect COGs so terrain enrichment works outside
the regional SRTM extent (which only covers a small box, leaving most fires null).

Source: AWS Terrarium terrain tiles (public, no auth). Elevation is encoded in RGB:
  elevation_m = (R * 256 + G + B / 256) - 32768
We fetch a global tile pyramid level, assemble a Web-Mercator mosaic, warp to 4326,
derive slope/aspect with gdaldem, and write three COGs into /data. Coarse (~5 km at
z5) but global, which is what event-level terrain context needs.

Run in the geoprocessing container:
  docker exec gwf-geoprocessing python /tmp/build_global_dem.py
"""
import os
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
from rasterio.transform import from_origin

DATA_DIR = os.environ.get("DATA_DIR", "/data")
Z = int(os.environ.get("DEM_ZOOM", "5"))          # z5 ~= 5 km/px at the equator
TILE = 256
N = 2 ** Z                                          # tiles per side
SIZE = N * TILE                                     # global mosaic pixels per side
WORLD = 20037508.342789244                          # half the 3857 extent (m)
NODATA = -9999.0
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def _fetch(xy):
    x, y = xy
    try:
        with urllib.request.urlopen(URL.format(z=Z, x=x, y=y), timeout=60) as r:
            buf = r.read()
        from rasterio.io import MemoryFile
        with MemoryFile(buf) as mem, mem.open() as ds:
            a = ds.read()  # (3, 256, 256) uint8
        elev = (a[0].astype(np.float32) * 256 + a[1] + a[2] / 256.0) - 32768.0
        return x, y, elev
    except Exception as e:  # noqa: BLE001
        print(f"  tile {Z}/{x}/{y} failed: {e!r}", flush=True)
        return x, y, None


def main():
    mosaic = np.full((SIZE, SIZE), NODATA, dtype=np.float32)
    tiles = [(x, y) for x in range(N) for y in range(N)]
    print(f"fetching {len(tiles)} terrarium tiles at z{Z} ...", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for x, y, elev in ex.map(_fetch, tiles):
            done += 1
            if elev is not None:
                mosaic[y * TILE:(y + 1) * TILE, x * TILE:(x + 1) * TILE] = elev
            if done % 256 == 0:
                print(f"  {done}/{len(tiles)}", flush=True)

    px = 2 * WORLD / SIZE
    transform = from_origin(-WORLD, WORLD, px, px)
    merc = os.path.join(DATA_DIR, "_dem_3857.tif")
    with rasterio.open(merc, "w", driver="GTiff", height=SIZE, width=SIZE, count=1,
                       dtype="float32", crs="EPSG:3857", transform=transform,
                       nodata=NODATA, compress="deflate") as dst:
        dst.write(mosaic, 1)
    print("wrote mercator mosaic, warping to 4326 ...", flush=True)

    dem4326 = os.path.join(DATA_DIR, "_dem_4326.tif")
    subprocess.run(["gdalwarp", "-q", "-overwrite", "-t_srs", "EPSG:4326",
                    "-dstnodata", str(NODATA), merc, dem4326], check=True)

    # Slope/aspect from the 4326 DEM. -s 111120 converts degrees to metres so the
    # gradient is in real units; -compute_edges keeps border pixels.
    slope = os.path.join(DATA_DIR, "_slope.tif")
    aspect = os.path.join(DATA_DIR, "_aspect.tif")
    subprocess.run(["gdaldem", "slope", "-q", "-s", "111120", "-compute_edges",
                    dem4326, slope], check=True)
    subprocess.run(["gdaldem", "aspect", "-q", "-compute_edges", dem4326, aspect],
                   check=True)
    print("derived slope + aspect, writing COGs ...", flush=True)

    for src, out in [(dem4326, "dem_global.cog.tif"),
                     (slope, "slope_global.cog.tif"),
                     (aspect, "aspect_global.cog.tif")]:
        subprocess.run(["gdal_translate", "-q", "-of", "COG",
                        "-co", "COMPRESS=DEFLATE", "-co", "RESAMPLING=BILINEAR",
                        src, os.path.join(DATA_DIR, out)], check=True)
        print(f"  wrote {out}", flush=True)

    for tmp in [merc, dem4326, slope, aspect]:
        try:
            os.remove(tmp)
        except OSError:
            pass
    with rasterio.open(os.path.join(DATA_DIR, "dem_global.cog.tif")) as ds:
        b = ds.bounds
        print(f"done. dem_global bounds {[round(v, 1) for v in b]} size {ds.shape}",
              flush=True)


if __name__ == "__main__":
    main()
