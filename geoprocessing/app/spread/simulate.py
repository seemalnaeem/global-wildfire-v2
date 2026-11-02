"""Phase 7: fire-spread forecasting with uncertainty.

For each active fire complex we run a Monte Carlo cellular-automaton spread model on
a local fine grid. Spread is driven by wind (direction and speed), fuel (land cover
times vegetation greenness) and dryness (VPD). Each ensemble member perturbs the wind
a little, so the fraction of members that burn a cell is its burn probability: the
uncertainty comes out of the ensemble, not a single deterministic run.

This adds beside the existing stack (it reuses the COGs, the weather connector and the
fire_event clustering); it does not change the risk model or the tiling.
"""
from __future__ import annotations

import os

import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform

from app.db import pool
from app.enrich.weather import fetch_weather

DATA_DIR = os.environ.get("DATA_DIR", "/data")
LC_COG = "worldcover_global.cog.tif"  # global, EPSG:3857
VEG_COG = "veg_greenness.cog.tif"     # global, EPSG:4326, 0..100, nodata 255
SLOPE_COG = "slope.cog.tif"           # regional, EPSG:4326 (null elsewhere)

# Flammability per WorldCover class: grass and shrub carry fire fastest, water and
# built-up do not burn. Keyed by class code.
FUEL = {
    10: 0.6,   # tree cover
    20: 0.9,   # shrubland
    30: 1.0,   # grassland
    40: 0.5,   # cropland
    50: 0.05,  # built-up
    60: 0.1,   # bare / sparse
    70: 0.0,   # snow and ice
    80: 0.0,   # water
    90: 0.3,   # herbaceous wetland
    95: 0.4,   # mangroves
    100: 0.3,  # moss / lichen
}

# 8-neighbour offsets (dy, dx) and their compass bearing (degrees, 0 = north).
_DIRS = [
    (-1, 0, 0.0), (-1, 1, 45.0), (0, 1, 90.0), (1, 1, 135.0),
    (1, 0, 180.0), (1, -1, 225.0), (0, -1, 270.0), (-1, -1, 315.0),
]


def _active_complexes(cur, hours: int, limit: int) -> list[dict]:
    """Recently active fire complexes to spread from, biggest fires first."""
    rows = cur.execute(
        """
        SELECT e.id, ST_X(e.centroid), ST_Y(e.centroid),
               ST_XMin(e.boundary), ST_YMin(e.boundary),
               ST_XMax(e.boundary), ST_YMax(e.boundary), e.frp_sum
          FROM fire_event e
         WHERE e.boundary IS NOT NULL
           AND e.last_detected >= (SELECT max(acq_time) FROM fire_detection)
                                  - (%(h)s * interval '1 hour')
         ORDER BY e.frp_sum DESC NULLS LAST
         LIMIT %(lim)s
        """,
        {"h": hours, "lim": limit},
    ).fetchall()
    return [{"event_id": r[0], "clon": r[1], "clat": r[2],
             "w": r[3], "s": r[4], "e": r[5], "n": r[6]} for r in rows]


def _sample_cog(path, lons, lats, warp_to=None, nodata_skip=None):
    """Sample a COG at lon/lat points. Returns a float array, NaN where off-extent or
    nodata. warp_to reprojects the points into the COG CRS first (for 3857 COGs)."""
    out = np.full(len(lons), np.nan)
    full = os.path.join(DATA_DIR, path)
    if not os.path.exists(full):
        return out
    with rasterio.open(full) as ds:
        xs, ys = (warp_transform("EPSG:4326", ds.crs, lons, lats)
                  if warp_to else (lons, lats))
        b = ds.bounds
        nod = ds.nodata if nodata_skip is None else nodata_skip
        for i, (x, y, val) in enumerate(zip(xs, ys, ds.sample(zip(xs, ys)))):
            if not (b.left <= x <= b.right and b.bottom <= y <= b.top):
                continue
            v = float(val[0])
            if nod is not None and v == nod:
                continue
            out[i] = v
    return out


def _fuel_grid(lons_flat, lats_flat, shape):
    """Fuel load per cell = land-cover flammability scaled by vegetation greenness."""
    lc = _sample_cog(LC_COG, lons_flat, lats_flat, warp_to=True)
    veg = _sample_cog(VEG_COG, lons_flat, lats_flat, nodata_skip=255)
    flam = np.zeros(len(lons_flat))
    for code, f in FUEL.items():
        flam[lc == code] = f
    veg_factor = 0.6 + 0.4 * np.clip(np.nan_to_num(veg, nan=20.0) / 50.0, 0, 1)
    return (flam * veg_factor).reshape(shape)


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Shift a 2D array, filling exposed edges with False/0 (no wrap-around)."""
    out = np.zeros_like(a)
    ys = slice(max(dy, 0), a.shape[0] + min(dy, 0))
    xs = slice(max(dx, 0), a.shape[1] + min(dx, 0))
    ys2 = slice(max(-dy, 0), a.shape[0] + min(-dy, 0))
    xs2 = slice(max(-dx, 0), a.shape[1] + min(-dx, 0))
    out[ys, xs] = a[ys2, xs2]
    return out


def _wind_factors(wind_from_deg: float, wind_kmh: float) -> list[float]:
    """Per-direction multiplier: strong downwind, suppressed upwind. wind_from_deg is
    the meteorological direction the wind blows FROM, so fire pushes toward +180."""
    downwind = (wind_from_deg + 180.0) % 360.0
    strength = float(np.clip(wind_kmh / 30.0, 0.0, 1.5))
    factors = []
    for _, _, bearing in _DIRS:
        align = np.cos(np.radians(bearing - downwind))  # 1 downwind, -1 upwind
        factors.append(float(np.exp(1.3 * strength * align)))
    return factors


def _simulate_one(fuel, slope, seed, wind_from, wind_kmh, dry, steps, ensemble,
                  base_p, rng, active_steps=4):
    """Monte Carlo CA with fuel burnout. A cell spreads only while it is a fresh front
    (ignited within the last `active_steps` steps), so the fire is a moving front, not
    a blob that fills everything. The ensemble spread gives the burn probability.
    Returns (burn_prob, mean_arrival_h) arrays over the grid."""
    diag = {45, 135, 225, 315}  # diagonal neighbours are 1/sqrt(2) closer-rate
    burned_count = np.zeros(fuel.shape)
    arrival_sum = np.zeros(fuel.shape)
    speed = dry * (1.0 + np.nan_to_num(slope, nan=0.0) / 45.0)  # steeper = faster

    for _ in range(ensemble):
        wf = _wind_factors(wind_from + rng.uniform(-20, 20),
                           max(0.0, wind_kmh * rng.uniform(0.7, 1.3)))
        ignite_step = np.where(seed, 0, -1).astype(np.int16)  # -1 = unburned
        for step in range(1, steps + 1):
            # Only the recently ignited front still spreads (older cells burn out).
            active = (ignite_step >= 0) & (ignite_step >= step - active_steps)
            if not active.any():
                break
            p_none = np.ones(fuel.shape)
            for (dy, dx, bearing), f in zip(_DIRS, wf):
                src = _shift(active, dy, dx)  # target has an active-front neighbour
                dist = 0.7071 if bearing in diag else 1.0
                p = base_p * fuel * f * speed * dist
                p_none *= np.where(src, 1.0 - np.clip(p, 0, 0.9), 1.0)
            p_catch = 1.0 - p_none
            ignite = (rng.random(fuel.shape) < p_catch) & (ignite_step < 0) & (fuel > 0)
            ignite_step[ignite] = step
        burned = ignite_step >= 0
        burned_count += burned
        arrival_sum += np.where(burned, ignite_step, 0)

    burn_prob = burned_count / ensemble
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_arrival = np.where(burned_count > 0, arrival_sum / burned_count, np.nan)
    return burn_prob, mean_arrival


def forecast_spread(hours: int = 24, max_complexes: int = 20, cell_deg: float = 0.02,
                    ensemble: int = 30, step_hours: int = 1, base_p: float = 0.12,
                    min_prob: float = 0.05, pad_deg: float = 0.3) -> dict:
    """Run spread forecasts for the most active fire complexes and store burn cells."""
    rng = np.random.default_rng(12345)  # fixed seed: reproducible (no wallclock in CA)
    steps = max(1, hours // step_hours)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            complexes = _active_complexes(cur, hours, max_complexes)
    if not complexes:
        return {"complexes": 0, "cells": 0, "note": "no recently active fire events"}

    # One batched weather call for all complex centroids (wind + dryness). Best effort:
    # if the provider is down (rate limit / 503), fall back to neutral wind per complex
    # rather than failing the whole forecast.
    try:
        weather = fetch_weather([(c["clon"], c["clat"]) for c in complexes])
    except Exception:  # noqa: BLE001
        weather = [None] * len(complexes)

    out_rows: list[tuple] = []
    used = 0
    for c, w in zip(complexes, weather):
        # Local grid: boundary bbox padded by the plausible spread distance.
        west, south = c["w"] - pad_deg, c["s"] - pad_deg
        east, north = c["e"] + pad_deg, c["n"] + pad_deg
        nx = max(3, int(round((east - west) / cell_deg)))
        ny = max(3, int(round((north - south) / cell_deg)))
        if nx * ny > 20000:  # guardrail against a runaway grid
            continue
        lon_c = west + (np.arange(nx) + 0.5) * cell_deg
        lat_c = south + (np.arange(ny) + 0.5) * cell_deg
        lon_g, lat_g = np.meshgrid(lon_c, lat_c)  # (ny, nx), row 0 = south
        fuel = _fuel_grid(lon_g.ravel(), lat_g.ravel(), (ny, nx))
        slope = _sample_cog(SLOPE_COG, lon_g.ravel(), lat_g.ravel()).reshape(ny, nx)

        # Seed ignition: cells inside the event boundary bbox (the current fire).
        seed = ((lon_g >= c["w"]) & (lon_g <= c["e"])
                & (lat_g >= c["s"]) & (lat_g <= c["n"]) & (fuel > 0))
        if not seed.any():
            j = np.argmin((lon_c - c["clon"]) ** 2)
            i = np.argmin((lat_c - c["clat"]) ** 2)
            seed[i, j] = True

        wind_from = w["wind_dir_deg"] if w and w.get("wind_dir_deg") is not None else 0.0
        wind_kmh = w["wind_speed_kmh"] if w and w.get("wind_speed_kmh") is not None else 10.0
        vpd = w.get("vpd_kpa") if w else None
        dry = float(np.clip(1.0 + 0.3 * (vpd if vpd is not None else 1.0), 0.6, 2.0))

        burn_prob, arrival = _simulate_one(
            fuel, slope, seed, float(wind_from), float(wind_kmh), dry,
            steps, ensemble, base_p, rng)

        ys, xs = np.where(burn_prob >= min_prob)
        for i, j in zip(ys, xs):
            out_rows.append((
                c["event_id"], float(lon_c[j] - cell_deg / 2), float(lat_c[i] - cell_deg / 2),
                float(lon_c[j] + cell_deg / 2), float(lat_c[i] + cell_deg / 2),
                float(burn_prob[i, j]),
                None if np.isnan(arrival[i, j]) else float(arrival[i, j] * step_hours),
                hours))
        used += 1

    params = {"cell_deg": cell_deg, "ensemble": ensemble, "step_hours": step_hours,
              "base_p": base_p, "min_prob": min_prob, "pad_deg": pad_deg}
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fire_spread_forecast")
            if out_rows:
                import json
                cur.execute("CREATE TEMP TABLE _sp (event_id bigint, w float8, s float8,"
                            " e float8, n float8, burn_prob float8, arrival_h float8,"
                            " horizon_h int) ON COMMIT DROP")
                with cur.copy("COPY _sp (event_id, w, s, e, n, burn_prob, arrival_h, horizon_h) FROM STDIN") as cp:
                    for r in out_rows:
                        cp.write_row(r)
                cur.execute(
                    """INSERT INTO fire_spread_forecast
                         (event_id, geom, burn_prob, arrival_h, horizon_h, params)
                       SELECT event_id, ST_MakeEnvelope(w, s, e, n, 4326),
                              burn_prob, arrival_h, horizon_h, %s
                         FROM _sp""",
                    (json.dumps(params),))
    return {"complexes": used, "cells": len(out_rows), "horizon_h": hours,
            "ensemble": ensemble}
