"""Fire-event clustering, per FIRMS_point_filtering.md.

A cluster becomes an event only if it is a dense knot of detections that is also
energetically significant:
  1. DBSCAN at `eps` metres, `minpoints` (default 1 km, 5). Isolated / noise
     detections (below the density threshold) never become events.
  2. FRP-sum gate: the cluster's combined FRP must be >= `min_cluster_frp` (20 MW).
  3. Merge pass: events whose convex-hull boundaries intersect and whose centroids
     are within `merge_m` (2.5 km) are merged (DBSCAN can split one fire).

This is a full recompute over all detections (the document recomputes each run),
so it clears and rebuilds `fire_event`. Enrichment (context/weather/vegetation)
cascades away and is repopulated afterwards.
"""
from __future__ import annotations

import os

from app.db import pool

EPS_M = float(os.environ.get("FIRE_CLUSTER_DISTANCE_M", "1000"))
MIN_POINTS = int(os.environ.get("FIRE_CLUSTER_MIN_POINTS", "5"))
MIN_CLUSTER_FRP = float(os.environ.get("FIRE_MIN_CLUSTER_FRP", "20"))
MERGE_M = float(os.environ.get("FIRE_MERGE_DISTANCE_M", "2500"))
# Point filter, applied to the clustering input so events form only from strong,
# confident detections. Raw detections stay stored for provenance.
FRP_MIN = float(os.environ.get("FIRMS_MIN_FRP", "2"))
# Event footprint: convex hull of the detections, buffered so it reads as a shape.
BUFFER_M = float(os.environ.get("FIRE_BOUNDARY_BUFFER_M", "400"))
# An event is 'active' if it was still detected within this many hours of the latest
# observation, else 'inactive'. Otherwise every event stays 'active' by default.
ACTIVE_HOURS = int(os.environ.get("EVENT_ACTIVE_HOURS", "24"))

_AGG_SELECT = f"""
  ST_Centroid(ST_Collect(geom)) AS centroid,
  ST_Buffer(ST_ConvexHull(ST_Collect(geom))::geography, {BUFFER_M})::geometry AS boundary,
  min(acq_time) AS first_detected, max(acq_time) AS last_detected,
  count(*) AS n, max(frp) AS max_frp, sum(frp) AS frp_sum
"""


def _recompute_aggregates(cur) -> None:
    cur.execute(
        f"""
        UPDATE fire_event e SET
          centroid = s.centroid, boundary = s.boundary,
          first_detected = s.first_detected, last_detected = s.last_detected,
          detection_count = s.n, max_frp = s.max_frp, frp_sum = s.frp_sum,
          updated_at = now()
        FROM (SELECT event_id, {_AGG_SELECT}
                FROM fire_detection WHERE event_id IS NOT NULL GROUP BY event_id) s
        WHERE e.id = s.event_id
        """
    )


def _merge_pass(cur) -> int:
    """Merge overlapping neighbour events. Returns how many events were removed."""
    removed = 0
    for _ in range(10):  # iterate until stable
        cur.execute(
            """
            SELECT a.id, b.id FROM fire_event a JOIN fire_event b ON a.id < b.id
             WHERE ST_DWithin(a.centroid::geography, b.centroid::geography, %(m)s)
               AND a.boundary IS NOT NULL AND b.boundary IS NOT NULL
               AND ST_Intersects(a.boundary, b.boundary)
            """,
            {"m": MERGE_M},
        )
        pairs = cur.fetchall()
        if not pairs:
            break
        # Union-find over this round's pairs.
        parent: dict[int, int] = {}

        def find(x: int) -> int:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in pairs:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        groups: dict[int, list[int]] = {}
        for node in list(parent):
            groups.setdefault(find(node), []).append(node)

        for root, members in groups.items():
            others = [m for m in members if m != root]
            if not others:
                continue
            cur.execute("UPDATE fire_detection SET event_id = %s WHERE event_id = ANY(%s)",
                        (root, others))
            cur.execute("DELETE FROM fire_event WHERE id = ANY(%s)", (others,))
            removed += len(others)
        _recompute_aggregates(cur)
    return removed


def cluster_detections() -> dict[str, int]:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Rebuild from scratch. Detaches detections (FK SET NULL) and cascades
            # enrichment away.
            cur.execute("DELETE FROM fire_event")

            # One DBSCAN run, shared by aggregation and assignment.
            cur.execute(
                """
                CREATE TEMP TABLE _clus ON COMMIT DROP AS
                SELECT id, frp, acq_time, geom,
                       ST_ClusterDBSCAN(ST_Transform(geom, 3857),
                            eps := %(eps)s, minpoints := %(mp)s) OVER () AS cid
                  FROM fire_detection
                 WHERE frp > %(frpmin)s
                   AND lower(coalesce(confidence, '')) IN ('n', 'h')
                """,
                {"eps": EPS_M, "mp": MIN_POINTS, "frpmin": FRP_MIN},
            )
            # Aggregate per cluster, gate on summed FRP, pre-allocate event ids.
            cur.execute(
                f"""
                CREATE TEMP TABLE _agg ON COMMIT DROP AS
                SELECT cid, nextval('fire_event_id_seq') AS event_id, {_AGG_SELECT}
                  FROM _clus WHERE cid IS NOT NULL
                 GROUP BY cid HAVING sum(frp) >= %(minfrp)s
                """,
                {"minfrp": MIN_CLUSTER_FRP},
            )
            cur.execute(
                """
                INSERT INTO fire_event
                  (id, centroid, boundary, first_detected, last_detected,
                   detection_count, max_frp, frp_sum)
                SELECT event_id, centroid, boundary, first_detected, last_detected,
                       n, max_frp, frp_sum FROM _agg
                """
            )
            created = cur.rowcount
            # Assign detections in qualifying clusters to their event.
            cur.execute(
                """
                UPDATE fire_detection d SET event_id = a.event_id
                  FROM _clus c JOIN _agg a ON a.cid = c.cid
                 WHERE d.id = c.id
                """
            )
            merged = _merge_pass(cur)
            # Derive status from recency: active only if detected within the window of
            # the latest observation. Replaces the static 'active' default.
            cur.execute(
                """UPDATE fire_event SET status = CASE
                     WHEN last_detected >= (SELECT max(acq_time) FROM fire_detection)
                                           - (%(h)s * interval '1 hour')
                     THEN 'active' ELSE 'inactive' END""",
                {"h": ACTIVE_HOURS},
            )
    return {"events": created, "merged_away": merged}
