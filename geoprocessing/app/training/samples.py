"""Build leakage-safe training samples on the grid (Phase 5).

One row per (cell, prediction_time). Features are fire history strictly at or before
the cutoff; the label is whether a new fire occurs in the cell in the next window.
Features are past, the label is future: never mix them (the anti-leakage rule).
"""
from __future__ import annotations

from app.db import pool
from app.training.weather_hist import fetch_weather_at

_INSERT = """
INSERT INTO grid_sample
  (cell_id, prediction_time, det_past_24h, det_past_48h, det_past_72h,
   frp_past_24h, had_fire, label_fire_next_24h, dataset_version)
SELECT c.id, %(pt)s,
  count(d.id) FILTER (WHERE d.acq_time >  %(pt)s - interval '24 hours' AND d.acq_time <= %(pt)s),
  count(d.id) FILTER (WHERE d.acq_time >  %(pt)s - interval '48 hours' AND d.acq_time <= %(pt)s),
  count(d.id) FILTER (WHERE d.acq_time >  %(pt)s - interval '72 hours' AND d.acq_time <= %(pt)s),
  COALESCE(sum(d.frp) FILTER (WHERE d.acq_time > %(pt)s - interval '24 hours' AND d.acq_time <= %(pt)s), 0),
  COALESCE(bool_or(d.acq_time <= %(pt)s), false),
  COALESCE(bool_or(d.acq_time > %(pt)s AND d.acq_time <= %(pt)s + (%(w)s * interval '1 hour')), false),
  %(v)s
FROM grid_cell c
LEFT JOIN fire_detection d ON ST_Contains(c.geom, d.geom)
GROUP BY c.id
ON CONFLICT (cell_id, prediction_time, dataset_version) DO NOTHING
"""


def _prediction_times(cur, window_hours: int, step_hours: int) -> list:
    row = cur.execute(
        "SELECT min(acq_time), max(acq_time) FROM fire_detection"
    ).fetchone()
    if not row or not row[0]:
        return []
    # Daily-anchored cutoffs where a full future window still has data.
    return cur.execute(
        """
        SELECT gs FROM generate_series(
          date_trunc('day', %(mn)s) + interval '12 hours',
          %(mx)s - (%(w)s * interval '1 hour'),
          (%(step)s * interval '1 hour')
        ) AS gs
        """,
        {"mn": row[0], "mx": row[1], "w": window_hours, "step": step_hours},
    ).fetchall()


# Neighborhood fire pressure: past-24h detections in nearby cells (spatial context
# for spread and clustering). Computed as a grid self-join.
_NEIGH = """
UPDATE grid_sample s SET neigh_det_24h = n.cnt
FROM (
  SELECT a.id AS cell_id, COALESCE(sum(sb.det_past_24h), 0) AS cnt
  FROM grid_cell a
  JOIN grid_cell b ON b.id <> a.id AND ST_DWithin(a.centroid, b.centroid, %(r)s)
  JOIN grid_sample sb ON sb.cell_id = b.id
       AND sb.prediction_time = %(pt)s AND sb.dataset_version = %(v)s
  GROUP BY a.id
) n
WHERE s.cell_id = n.cell_id AND s.prediction_time = %(pt)s AND s.dataset_version = %(v)s
"""


def build_samples(version: str, window_hours: int = 24, step_hours: int = 12,
                  neighbor_radius_deg: float = 0.3) -> dict:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM grid_sample WHERE dataset_version = %s", (version,))
            times = [r[0] for r in _prediction_times(cur, window_hours, step_hours)]
            for pt in times:
                cur.execute(_INSERT, {"pt": pt, "w": window_hours, "v": version})
                cur.execute(_NEIGH, {"pt": pt, "v": version, "r": neighbor_radius_deg})
            cur.execute(
                "UPDATE grid_sample SET neigh_det_24h = COALESCE(neigh_det_24h, 0)"
                " WHERE dataset_version = %s", (version,))
            total, pos = cur.execute(
                """SELECT count(*), count(*) FILTER (WHERE label_fire_next_24h)
                     FROM grid_sample WHERE dataset_version = %s""",
                (version,),
            ).fetchone()
    return {
        "version": version, "prediction_times": len(times),
        "samples": total, "positives": pos,
        "positive_rate": round(pos / total, 4) if total else 0,
        "window_hours": window_hours,
    }


def enrich_weather(version: str) -> dict:
    """Fill weather observed at each prediction_time (NASA POWER). Leakage safe:
    values are at the cutoff, not the future. Fetch is outside the DB transaction."""
    with pool.connection() as conn:
        times = [r[0] for r in conn.execute(
            "SELECT DISTINCT prediction_time FROM grid_sample WHERE dataset_version=%s"
            " ORDER BY prediction_time", (version,)).fetchall()]
        cells = conn.execute(
            "SELECT id, ST_X(centroid), ST_Y(centroid) FROM grid_cell").fetchall()
    ids = [c[0] for c in cells]
    points = [(c[1], c[2]) for c in cells]

    updated = 0
    for pt in times:
        weather = fetch_weather_at(points, pt)  # network, outside transaction
        rows = [(w["temp_c"], w["rh"], w["wind_speed_kmh"], w["precip_mm"],
                 w["vpd_kpa"], w["soil_moist_surface"], cid, pt, version)
                for cid, w in zip(ids, weather) if w]
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """UPDATE grid_sample SET temp_c=%s, rh=%s, wind_speed_kmh=%s,
                       precip_mm=%s, vpd_kpa=%s, soil_moist_surface=%s
                       WHERE cell_id=%s AND prediction_time=%s AND dataset_version=%s""",
                    rows)
                updated += len(rows)
    return {"version": version, "prediction_times": len(times), "updated_rows": updated}
