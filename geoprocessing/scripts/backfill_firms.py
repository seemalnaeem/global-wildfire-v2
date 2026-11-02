"""Backfill several days of FIRMS world detections, day by day, then cluster once.

A single world request for a large day-range 400s (too big), so this loops one day
at a time (day_range=1 + an explicit start date, newest to oldest) and reuses the
connector's parse_and_validate plus the same COPY+dedupe insert. Idempotent
(ON CONFLICT DO NOTHING), so re-running only adds missing rows.

Run inside the geoprocessing container:
    docker cp geoprocessing/scripts/backfill_firms.py gwf-geoprocessing:/tmp/bf.py
    docker exec gwf-geoprocessing python /tmp/bf.py
(On Git Bash prefix with MSYS_NO_PATHCONV=1 so /tmp is not path-mangled.)

Env knobs: BACKFILL_DAYS (default 10), BACKFILL_END (YYYY-MM-DD, default the
container's today).
"""
import json
import os
import time
import urllib.request
from datetime import date, timedelta

from app.connectors.firms import FirmsViirsConnector
from app.db import pool, open_pool
from app.enrich.service import enrich_events
from app.events.cluster import cluster_detections
from app.events.classify import classify_events

open_pool()  # standalone script: the FastAPI lifespan is not running here
conn_obj = FirmsViirsConnector()
key = os.environ["FIRMS_MAP_KEY"]
src = os.environ.get("FIRMS_SOURCE", "VIIRS_SNPP_NRT")

DAYS = int(os.environ.get("BACKFILL_DAYS", "10"))
end_env = os.environ.get("BACKFILL_END")
END = date.fromisoformat(end_env) if end_env else date.today()
starts = [(END - timedelta(days=i)).isoformat() for i in range(DAYS)]

cols = ("run_id", "lon", "lat", "acq_time", "satellite", "sensor",
        "confidence", "frp", "brightness", "daynight", "quality")

def _fetch(url: str, tries: int = 4) -> bytes | None:
    """World CSVs are large and the endpoint is flaky (IncompleteRead / timeouts).
    Retry with backoff before giving up on a day."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt + 1}/{tries} failed: {e!r}", flush=True)
            time.sleep(5 * (attempt + 1))
    return None


total = 0
for sd in starts:
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/world/1/{sd}"
    raw = _fetch(url)
    if raw is None:
        print(f"{sd}: fetch failed after retries", flush=True)
        continue
    records = conn_obj.parse_and_validate(raw)
    if not records:
        print(f"{sd}: 0 records", flush=True)
        continue
    with pool.connection() as c:
        with c.cursor() as cur:
            cur.execute(
                "CREATE TEMP TABLE _load (run_id bigint, lon float8, lat float8,"
                " acq_time timestamptz, satellite text, sensor text, confidence text,"
                " frp float8, brightness float8, daynight text, quality jsonb)"
                " ON COMMIT DROP")
            with cur.copy(f"COPY _load ({','.join(cols)}) FROM STDIN") as copy:
                for r in records:
                    copy.write_row((None, r["lon"], r["lat"], r["acq_time"],
                                    r["satellite"], r["sensor"], r["confidence"],
                                    r["frp"], r["brightness"], r["daynight"],
                                    json.dumps(r["quality"])))
            cur.execute(
                """INSERT INTO fire_detection
                     (run_id, lon, lat, geom, acq_time, satellite, sensor,
                      confidence, frp, brightness, daynight, quality)
                   SELECT run_id, lon, lat, ST_SetSRID(ST_MakePoint(lon, lat), 4326),
                          acq_time, satellite, sensor, confidence, frp, brightness,
                          daynight, quality
                     FROM _load
                   ON CONFLICT (satellite, acq_time, lon, lat) DO NOTHING""")
    print(f"{sd}: parsed {len(records)}", flush=True)
    total += len(records)

with pool.connection() as c:
    span = c.execute(
        "SELECT count(*), min(acq_time), max(acq_time) FROM fire_detection").fetchone()
print(f"backfill parsed total={total}; table now count={span[0]} "
      f"span {span[1]} .. {span[2]}", flush=True)
# Rebuild events, then enrich (land cover + terrain) so classification has what it
# needs, then classify. Without the enrich step every event stays 'unclassified' and
# the wildfire-only map layers come up empty.
print("clustering once ...", flush=True)
print("cluster", cluster_detections(), flush=True)
print("enriching (land cover + terrain) ...", flush=True)
print("enrich", enrich_events(limit=10_000_000), flush=True)
print("classify", classify_events(), flush=True)
