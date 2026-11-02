"""Shared Python helpers for geoprocessing. Import, do not duplicate."""
from __future__ import annotations

import subprocess

SRID_STORAGE = 4326  # lon/lat WGS84
SRID_TILE = 3857  # web mercator


def run(cmd: list[str]) -> str:
    """Run a GDAL/OGR command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def to_cog(src: str, dst: str) -> str:
    """Convert a GeoTIFF to a Cloud Optimized GeoTIFF. Safe for multi-GB files."""
    return run([
        "gdal_translate", src, dst, "-of", "COG",
        "-co", "COMPRESS=DEFLATE", "-co", "BIGTIFF=YES",
        "-co", "NUM_THREADS=ALL_CPUS",
    ])


def load_vector(src: str, table: str, database_url: str) -> str:
    """Load a vector source into PostGIS as EPSG:4326 with a geom column."""
    return run([
        "ogr2ogr", "-f", "PostgreSQL", f"PG:{database_url}", src,
        "-nln", table, "-nlt", "PROMOTE_TO_MULTI",
        "-t_srs", f"EPSG:{SRID_STORAGE}",
        "-lco", "GEOMETRY_NAME=geom", "-lco", "FID=id",
    ])
