"""Build a WorldCover VRT over a bounding box from the public ESA COGs.

Serves as a TiTiler-facing land-cover layer without downloading full tiles. The
VRT references remote /vsicurl COGs, GDAL reads only what each map tile needs.

Usage (inside the geoprocessing container):
  python3 scripts/build_worldcover_vrt.py <west> <south> <east> <north> <out.vrt>
Default bbox covers the current DEM/data extent.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import urllib.request

GRID = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/esa_worldcover_grid.geojson"
BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map"


def tile_sw(name: str) -> tuple[int, int]:
    # name like N30E069 or S54E168 -> (lon, lat) of the south west corner
    lat = int(name[1:3]) * (1 if name[0] == "N" else -1)
    lon = int(name[4:7]) * (1 if name[3] == "E" else -1)
    return lon, lat


def main() -> None:
    west, south, east, north = (float(a) for a in sys.argv[1:5]) if len(sys.argv) >= 5 \
        else (60.0, 21.0, 81.0, 39.0)
    out = sys.argv[5] if len(sys.argv) >= 6 else "/data/worldcover.vrt"

    with urllib.request.urlopen(GRID, timeout=120) as resp:
        grid = json.load(resp)
    names = {f["properties"]["ll_tile"] for f in grid["features"]}

    urls = []
    for name in sorted(names):
        lon, lat = tile_sw(name)
        # Tile covers [lon, lon+3] x [lat, lat+3]. Keep it if it intersects the bbox.
        if lon + 3 > west and lon < east and lat + 3 > south and lat < north:
            urls.append(f"/vsicurl/{BASE}/ESA_WorldCover_10m_2020_v100_{name}_Map.tif")

    if not urls:
        raise SystemExit("no WorldCover tiles intersect the bbox")
    print(f"building VRT from {len(urls)} tiles -> {out}")

    env = dict(os.environ, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
               CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif")
    listfile = "/tmp/wc_tiles.txt"
    with open(listfile, "w") as fh:
        fh.write("\n".join(urls))
    subprocess.run(["gdalbuildvrt", "-input_file_list", listfile, out],
                   check=True, env=env)
    print("done")


if __name__ == "__main__":
    main()
