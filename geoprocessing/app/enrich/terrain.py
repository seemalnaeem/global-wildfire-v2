"""Terrain enrichment. Samples local DEM COGs at points.

Each field has a regional high-res COG (preferred) and a global coarse COG fallback,
tried in order. A point gets the high-res value inside the regional extent, else the
global value, else nothing (e.g. flat areas have no aspect). All COGs are EPSG:4326.
"""
from __future__ import annotations

import os

import rasterio

DATA_DIR = os.environ.get("DATA_DIR", "/data")
# Preferred regional COG first, global coarse COG second.
RASTERS = {
    "elevation": ["elevation.cog.tif", "dem_global.cog.tif"],
    "slope": ["slope.cog.tif", "slope_global.cog.tif"],
    "aspect": ["aspect.cog.tif", "aspect_global.cog.tif"],
}


def sample_terrain(points: list[tuple[float, float]]) -> list[dict[str, float]]:
    """Return one dict per point with any of elevation/slope/aspect that exist."""
    out: list[dict[str, float]] = [{} for _ in points]
    for key, fnames in RASTERS.items():
        for fname in fnames:
            path = os.path.join(DATA_DIR, fname)
            if not os.path.exists(path):
                continue
            need = [(i, *points[i]) for i in range(len(points)) if key not in out[i]]
            if not need:
                break  # every point already has this field from the preferred COG
            with rasterio.open(path) as ds:
                b, nod = ds.bounds, ds.nodata
                inside = [(i, lon, lat) for i, lon, lat in need
                          if b.left <= lon <= b.right and b.bottom <= lat <= b.top]
                if not inside:
                    continue
                coords = [(lon, lat) for _, lon, lat in inside]
                for (i, _, _), val in zip(inside, ds.sample(coords)):
                    v = float(val[0])
                    if nod is not None and v == nod:
                        continue
                    out[i][key] = v
    return out
