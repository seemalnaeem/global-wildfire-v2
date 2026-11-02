"""Land-cover enrichment from ESA WorldCover (public, global, 10 m, no auth).

WorldCover is split into 3 degree COG tiles on AWS Open Data. We group points by
tile so each remote COG is opened once and all its points sampled together. Ocean
tiles do not exist, so open failures are treated as no land cover.
"""
from __future__ import annotations

import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import rasterio

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map"

# ESA WorldCover 2020 class codes.
CLASSES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare / sparse vegetation", 70: "Snow and ice",
    80: "Permanent water", 90: "Herbaceous wetland", 95: "Mangroves",
    100: "Moss and lichen",
}

# GDAL settings for efficient remote COG reads.
_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif")


def _tile(lon: float, lat: float) -> str:
    tlat = int(math.floor(lat / 3.0)) * 3
    tlon = int(math.floor(lon / 3.0)) * 3
    ns = "N" if tlat >= 0 else "S"
    ew = "E" if tlon >= 0 else "W"
    return f"{ns}{abs(tlat):02d}{ew}{abs(tlon):03d}"


def _url(tile: str) -> str:
    return f"/vsicurl/{BASE}/ESA_WorldCover_10m_2020_v100_{tile}_Map.tif"


def _sample_tile(tile: str, items: list[tuple[int, float, float]]) -> list[tuple[int, int, str]]:
    """Open one WorldCover tile and sample all its points. Returns (idx, code, label)."""
    results: list[tuple[int, int, str]] = []
    try:
        with rasterio.Env(**_ENV):
            with rasterio.open(_url(tile)) as ds:
                coords = [(lon, lat) for _, lon, lat in items]
                for (idx, _, _), val in zip(items, ds.sample(coords)):
                    code = int(val[0])
                    if code in CLASSES:
                        results.append((idx, code, CLASSES[code]))
    except Exception:
        # Tile missing (ocean) or transient fetch error, leave those points empty.
        pass
    return results


def sample_landcover(points: list[tuple[float, float]], workers: int = 8) -> list[tuple[int | None, str | None]]:
    """Return (code, label) per point. Tiles are sampled in parallel (network bound)."""
    out: list[tuple[int | None, str | None]] = [(None, None)] * len(points)
    groups: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for i, (lon, lat) in enumerate(points):
        groups[_tile(lon, lat)].append((i, lon, lat))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(lambda kv: _sample_tile(*kv), groups.items()):
            for idx, code, label in res:
                out[idx] = (code, label)
    return out
