"""Phase 8: alert engine. Evaluates rules against the live data and keeps the `alert`
table in sync: qualifying events upsert an alert, and alerts whose event no longer
qualifies are resolved. Idempotent, so it is safe to run on every scheduler refresh.

Rules (all env-tunable):
  large_fire     - an active wildfire whose summed FRP is large (warning/critical).
  spread_threat  - a fire whose spread forecast covers many high-probability cells.
"""
from __future__ import annotations

import os

from app.db import pool

FRP_WARNING = float(os.environ.get("ALERT_FRP_WARNING", "2000"))
FRP_CRITICAL = float(os.environ.get("ALERT_FRP_CRITICAL", "5000"))
# Alert on any significant wildfire still in the dataset (i.e. still shown on the map).
# The DB is pruned to the FIRMS retention window, so matching that window means every
# displayed event is eligible; a new data update then refreshes/resolves alerts.
_RETENTION_DAYS = int(os.environ.get("FIRMS_RETENTION_DAYS", "5"))
ACTIVE_HOURS = int(os.environ.get("ALERT_ACTIVE_HOURS", str(_RETENTION_DAYS * 24)))
SPREAD_CELLS = int(os.environ.get("ALERT_SPREAD_CELLS", "300"))
SPREAD_PROB = float(os.environ.get("ALERT_SPREAD_PROB", "0.5"))

# Large active wildfire: strong summed FRP and detected within the active window.
_LARGE_FIRE = """
INSERT INTO alert (kind, severity, event_id, centroid, title, message, value, status, updated_at)
SELECT 'large_fire',
       CASE WHEN e.frp_sum >= %(crit)s THEN 'critical' ELSE 'warning' END,
       e.id, e.centroid, 'Large active wildfire',
       'Wildfire with ' || round(e.frp_sum)::text || ' MW total fire power ('
         || e.detection_count::text || ' detections).',
       e.frp_sum, 'active', now()
  FROM fire_event e
 WHERE e.category = 'wildfire' AND e.frp_sum >= %(warn)s
   AND e.last_detected >= (SELECT max(acq_time) FROM fire_detection)
                          - (%(hrs)s * interval '1 hour')
ON CONFLICT (kind, event_id) DO UPDATE SET
  severity = EXCLUDED.severity, centroid = EXCLUDED.centroid,
  message = EXCLUDED.message, value = EXCLUDED.value,
  status = 'active', updated_at = now()
"""

# Spread threat: the spread forecast covers many high-probability cells for this fire.
_SPREAD_THREAT = """
INSERT INTO alert (kind, severity, event_id, centroid, title, message, value, status, updated_at)
SELECT 'spread_threat',
       CASE WHEN s.cells >= %(cells)s * 2 THEN 'critical' ELSE 'warning' END,
       e.id, e.centroid, 'Fire forecast to spread',
       'Spread forecast covers ' || s.cells::text
         || ' cells at >= ' || (%(prob)s * 100)::int::text || '%% burn probability (next 24h).',
       s.cells, 'active', now()
  FROM (SELECT event_id, count(*) AS cells FROM fire_spread_forecast
         WHERE burn_prob >= %(prob)s GROUP BY event_id HAVING count(*) >= %(cells)s) s
  JOIN fire_event e ON e.id = s.event_id
ON CONFLICT (kind, event_id) DO UPDATE SET
  severity = EXCLUDED.severity, centroid = EXCLUDED.centroid,
  message = EXCLUDED.message, value = EXCLUDED.value,
  status = 'active', updated_at = now()
"""

# Resolve alerts of a kind whose event no longer qualifies (keeps the list current).
_RESOLVE = """
UPDATE alert SET status = 'resolved', updated_at = now()
 WHERE kind = %(kind)s AND status = 'active'
   AND event_id NOT IN (SELECT event_id FROM _qualify)
"""


def evaluate_alerts() -> dict:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_LARGE_FIRE, {"warn": FRP_WARNING, "crit": FRP_CRITICAL,
                                      "hrs": ACTIVE_HOURS})
            # Resolve stale large_fire alerts.
            cur.execute("""CREATE TEMP TABLE _qualify ON COMMIT DROP AS
                SELECT e.id AS event_id FROM fire_event e
                 WHERE e.category='wildfire' AND e.frp_sum >= %(warn)s
                   AND e.last_detected >= (SELECT max(acq_time) FROM fire_detection)
                                          - (%(hrs)s * interval '1 hour')""",
                        {"warn": FRP_WARNING, "hrs": ACTIVE_HOURS})
            cur.execute(_RESOLVE, {"kind": "large_fire"})
            cur.execute("DROP TABLE _qualify")

            cur.execute(_SPREAD_THREAT, {"cells": SPREAD_CELLS, "prob": SPREAD_PROB})
            cur.execute("""CREATE TEMP TABLE _qualify ON COMMIT DROP AS
                SELECT event_id FROM fire_spread_forecast WHERE burn_prob >= %(prob)s
                 GROUP BY event_id HAVING count(*) >= %(cells)s""",
                        {"cells": SPREAD_CELLS, "prob": SPREAD_PROB})
            cur.execute(_RESOLVE, {"kind": "spread_threat"})
            cur.execute("DROP TABLE _qualify")

            counts = cur.execute(
                """SELECT severity, count(*) FROM alert WHERE status='active'
                   GROUP BY severity""").fetchall()
    return {"active": {s: n for s, n in counts}}
