"""Classify fire events as wildfire vs other.

Density and energy are already enforced when events form (see cluster.py: DBSCAN
minpoints and the FRP-sum gate). What remains is the surface: a wildfire burns
wildland fuel, not built-up, bare, water, snow, or (by default) cropland. So an
event is a wildfire if its land cover is in the configured wildland set.

Events without land cover yet stay 'unclassified' until enriched.
"""
from __future__ import annotations

import os

from app.db import pool

# ESA WorldCover codes counted as wildland fuel. Default: tree, shrub, grass.
# Excludes built-up (50), bare (60), snow (70), water (80), moss (100) and
# cropland (40, agricultural). Tune with WILDFIRE_LANDCOVER_CODES.
WILDLAND = [int(x) for x in os.environ.get("WILDFIRE_LANDCOVER_CODES", "10,20,30").split(",") if x.strip()]


def classify_events() -> dict:
    with pool.connection() as conn:
        cur = conn.execute(
            """
            UPDATE fire_event e SET category = sub.cat, updated_at = now()
            FROM (
              SELECT ev.id,
                CASE
                  WHEN c.event_id IS NULL THEN 'unclassified'
                  WHEN c.landcover_code = ANY(%(w)s) THEN 'wildfire'
                  ELSE 'other'
                END AS cat
              FROM fire_event ev
              LEFT JOIN fire_event_context c ON c.event_id = ev.id
            ) sub
            WHERE e.id = sub.id AND e.category IS DISTINCT FROM sub.cat
            """,
            {"w": WILDLAND},
        )
        updated = cur.rowcount
        rows = conn.execute(
            "SELECT category, count(*) FROM fire_event GROUP BY category"
        ).fetchall()
    return {"updated": updated, "counts": {k: v for k, v in rows},
            "wildland_codes": WILDLAND}
