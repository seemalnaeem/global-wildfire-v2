"""Enrichment orchestration. Samples terrain and land cover for events and upserts
fire_event_context. `enrich_events` fills events lacking context in bulk;
`enrich_one` handles a single event on demand (lazy, from the details view)."""
from __future__ import annotations

from typing import Any

from app.db import pool
from app.enrich.landcover import sample_landcover
from app.enrich.terrain import sample_terrain
from app.enrich.weather import fetch_weather
from app.enrich.vegetation import fetch_indices

_WEATHER_UPSERT = """
    INSERT INTO fire_event_weather
      (event_id, temp_c, rh, dew_point_c, wind_speed_kmh, wind_dir_deg,
       wind_gust_kmh, precip_mm, pressure_hpa, soil_moist_surface, soil_moist_root,
       soil_temp_c, vpd_kpa, weather_time, fetched_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
    ON CONFLICT (event_id) DO UPDATE SET
      temp_c = EXCLUDED.temp_c, rh = EXCLUDED.rh, dew_point_c = EXCLUDED.dew_point_c,
      wind_speed_kmh = EXCLUDED.wind_speed_kmh, wind_dir_deg = EXCLUDED.wind_dir_deg,
      wind_gust_kmh = EXCLUDED.wind_gust_kmh, precip_mm = EXCLUDED.precip_mm,
      pressure_hpa = EXCLUDED.pressure_hpa,
      soil_moist_surface = EXCLUDED.soil_moist_surface,
      soil_moist_root = EXCLUDED.soil_moist_root, soil_temp_c = EXCLUDED.soil_temp_c,
      vpd_kpa = EXCLUDED.vpd_kpa, weather_time = EXCLUDED.weather_time,
      fetched_at = now()
"""


def enrich_weather_one(event_id: int) -> dict:
    """Fetch current weather for one event and upsert. Used lazily on event open."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT ST_X(centroid), ST_Y(centroid) FROM fire_event WHERE id = %s",
            (event_id,),
        ).fetchone()
    if not row:
        return {"weather": 0}
    w = fetch_weather([(row[0], row[1])])[0]
    if not w:
        return {"weather": 0}
    with pool.connection() as conn:
        conn.execute(_WEATHER_UPSERT, (
            event_id, w["temp_c"], w["rh"], w["dew_point_c"], w["wind_speed_kmh"],
            w["wind_dir_deg"], w["wind_gust_kmh"], w["precip_mm"], w["pressure_hpa"],
            w["soil_moist_surface"], w["soil_moist_root"], w["soil_temp_c"],
            w["vpd_kpa"], w["weather_time"],
        ))
    return {"weather": 1, "event_id": event_id, "temp_c": w["temp_c"]}

_UPSERT = """
    INSERT INTO fire_event_context
      (event_id, elevation, slope, aspect, landcover_code, landcover_label)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (event_id) DO UPDATE SET
      elevation = EXCLUDED.elevation, slope = EXCLUDED.slope,
      aspect = EXCLUDED.aspect, landcover_code = EXCLUDED.landcover_code,
      landcover_label = EXCLUDED.landcover_label, enriched_at = now()
"""


def _write(cur, ids: list[int], terrain: list[dict], landcover: list[tuple]) -> None:
    for i, eid in enumerate(ids):
        t = terrain[i]
        code, label = landcover[i]
        cur.execute(_UPSERT, (eid, t.get("elevation"), t.get("slope"),
                              t.get("aspect"), code, label))


def enrich_events(limit: int = 500) -> dict[str, int]:
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id, ST_X(e.centroid), ST_Y(e.centroid)
              FROM fire_event e
              LEFT JOIN fire_event_context c ON c.event_id = e.id
             WHERE c.event_id IS NULL
             ORDER BY e.last_detected DESC
             LIMIT %s
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return {"enriched": 0, "remaining": 0}

    ids = [r[0] for r in rows]
    points = [(r[1], r[2]) for r in rows]
    terrain = sample_terrain(points)
    landcover = sample_landcover(points)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            _write(cur, ids, terrain, landcover)
        remaining = conn.execute(
            """
            SELECT count(*) FROM fire_event e
             LEFT JOIN fire_event_context c ON c.event_id = e.id
             WHERE c.event_id IS NULL
            """
        ).fetchone()[0]

    return {"enriched": len(ids), "remaining": remaining}


def enrich_one(event_id: int) -> dict[str, Any]:
    """Enrich a single event on demand. Used lazily when its details are opened."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT id, ST_X(centroid), ST_Y(centroid) FROM fire_event WHERE id = %s",
            (event_id,),
        ).fetchone()
    if not row:
        return {"enriched": 0}

    points = [(row[1], row[2])]
    terrain = sample_terrain(points)
    landcover = sample_landcover(points)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            _write(cur, [event_id], terrain, landcover)
    return {"enriched": 1, "event_id": event_id, "landcover": landcover[0][1]}


def enrich_vegetation_one(event_id: int) -> dict:
    """Fetch Sentinel-2 NDVI/NDMI/NBR for one event and upsert. Lazy, on open."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT ST_X(centroid), ST_Y(centroid) FROM fire_event WHERE id = %s",
            (event_id,),
        ).fetchone()
    if not row:
        return {"vegetation": 0}
    v = fetch_indices(row[0], row[1])
    if not v:
        return {"vegetation": 0}
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO fire_event_vegetation (event_id, ndvi, ndmi, nbr, obs_date, fetched_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (event_id) DO UPDATE SET
              ndvi = EXCLUDED.ndvi, ndmi = EXCLUDED.ndmi, nbr = EXCLUDED.nbr,
              obs_date = EXCLUDED.obs_date, fetched_at = now()
            """,
            (event_id, v["ndvi"], v["ndmi"], v["nbr"], v["obs_date"]),
        )
    return {"vegetation": 1, "event_id": event_id, "ndvi": v["ndvi"], "obs_date": v["obs_date"]}
