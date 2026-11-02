"""Build the study-area grid and its static features (Phase 5).

Cells come from PostGIS ST_SquareGrid. Static features (terrain, land cover) are
sampled from the local COGs at each cell centroid, so this is fast and offline.
Terrain COGs are regional (null outside their extent); land cover is global.
"""
from __future__ import annotations

import os

import rasterio
from rasterio.warp import transform as warp_transform

from app.db import pool
from app.enrich.landcover import CLASSES

DATA_DIR = os.environ.get("DATA_DIR", "/data")
# Local 4326 terrain COGs, sampled directly with lon/lat. Vegetation greenness is a
# global 4326 COG too (MODIS-NDVI-derived, nodata 255), so it samples the same way.
TERRAIN = [("elevation.cog.tif", "elevation"), ("slope.cog.tif", "slope"),
           ("aspect.cog.tif", "aspect"), ("veg_greenness.cog.tif", "veg_greenness")]
VEG_NODATA = 255
LC_COG = "worldcover_global.cog.tif"  # global, EPSG:3857


def build_grid(bbox: tuple[float, float, float, float], size_deg: float = 0.1,
               land_only: bool = False) -> dict:
    west, south, east, north = bbox
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM grid_cell")
            cur.execute(
                """
                INSERT INTO grid_cell (geom, centroid)
                SELECT g.geom, ST_Centroid(g.geom)
                  FROM ST_SquareGrid(%s, ST_MakeEnvelope(%s, %s, %s, %s, 4326)) AS g
                """,
                (size_deg, west, south, east, north),
            )
            rows = cur.execute(
                "SELECT id, ST_X(centroid), ST_Y(centroid) FROM grid_cell"
            ).fetchall()

    ids = [r[0] for r in rows]
    lons = [r[1] for r in rows]
    lats = [r[2] for r in rows]
    feats: dict[int, dict] = {i: {} for i in ids}

    for fname, key in TERRAIN:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        with rasterio.open(path) as ds:
            nod, b = ds.nodata, ds.bounds
            for i, (lon, lat, val) in enumerate(zip(lons, lats, ds.sample(zip(lons, lats)))):
                if not (b.left <= lon <= b.right and b.bottom <= lat <= b.top):
                    continue
                v = float(val[0])
                if nod is None or v != nod:
                    feats[ids[i]][key] = v

    lc_path = os.path.join(DATA_DIR, LC_COG)
    if os.path.exists(lc_path):
        with rasterio.open(lc_path) as ds:
            xs, ys = warp_transform("EPSG:4326", ds.crs, lons, lats)
            for i, val in enumerate(ds.sample(zip(xs, ys))):
                code = int(val[0])
                if code in CLASSES:
                    feats[ids[i]]["landcover_code"] = code
                    feats[ids[i]]["landcover_label"] = CLASSES[code]

    # Bulk update via COPY into a temp table then UPDATE FROM (scales to big grids).
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE _gf (id bigint, elevation float8, slope float8,"
                        " aspect float8, landcover_code smallint, landcover_label text,"
                        " veg_greenness smallint) ON COMMIT DROP")
            with cur.copy("COPY _gf (id, elevation, slope, aspect, landcover_code, landcover_label, veg_greenness) FROM STDIN") as copy:
                for i, f in feats.items():
                    g = f.get("veg_greenness")
                    copy.write_row((i, f.get("elevation"), f.get("slope"), f.get("aspect"),
                                    f.get("landcover_code"), f.get("landcover_label"),
                                    int(g) if g is not None else None))
            cur.execute("""UPDATE grid_cell c SET elevation=g.elevation, slope=g.slope,
                           aspect=g.aspect, landcover_code=g.landcover_code,
                           landcover_label=g.landcover_label, veg_greenness=g.veg_greenness
                           FROM _gf g WHERE c.id=g.id""")
            removed = 0
            if land_only:
                # Drop ocean / no-data cells (no land cover) to keep the grid small.
                cur.execute("DELETE FROM grid_cell WHERE landcover_code IS NULL OR landcover_code = 80")
                removed = cur.rowcount
            kept = cur.execute("SELECT count(*) FROM grid_cell").fetchone()[0]
    return {"cells": kept, "removed": removed, "bbox": bbox, "size_deg": size_deg}
