"""NASA FIRMS / VIIRS active-fire connector.

Fetches VIIRS active-fire detections from the FIRMS area API. Needs a free MAP_KEY
(https://firms.modaps.eosdis.nasa.gov/). Without a key it falls back to a bundled
sample so the pipeline stays testable offline. Provider details stay in here, the
frontend never calls FIRMS directly.
"""
from __future__ import annotations

import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.connectors.base import BaseConnector
from app.db import pool
from app.events.cluster import cluster_detections
from app.events.classify import classify_events
from app.ingest import validation as v

_SAMPLE = Path(__file__).parent / "samples" / "firms_viirs_sample.csv"

# Point filter threshold: keep detections with FRP strictly greater than this.
FRP_MIN = float(os.environ.get("FIRMS_MIN_FRP", "2"))


class FirmsViirsConnector(BaseConnector):
    name = "firms_viirs"
    kind = "api"
    provider = "NASA FIRMS"
    content_type = "text/csv"

    # Env config. AREA is 'world' or a 'west,south,east,north' bbox. DAYS 1..10.
    map_key = os.environ.get("FIRMS_MAP_KEY", "")
    source = os.environ.get("FIRMS_SOURCE", "VIIRS_SNPP_NRT")
    area = os.environ.get("FIRMS_AREA", "world")
    days = os.environ.get("FIRMS_DAYS", "1")

    def config(self) -> dict[str, Any]:
        return {"source": self.source, "area": self.area, "days": self.days,
                "mode": "live" if self.map_key else "sample"}

    def storage_key(self, params: dict[str, Any]) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"raw/{self.name}/{self.source}/{stamp}.csv"

    def fetch(self, params: dict[str, Any]) -> bytes:
        if not self.map_key:
            # Offline sample mode. Set FIRMS_MAP_KEY to go live.
            return _SAMPLE.read_bytes()
        source = params.get("source", self.source)
        area = params.get("area", self.area)
        days = params.get("days", self.days)
        url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
               f"{self.map_key}/{source}/{area}/{days}")
        with urllib.request.urlopen(url, timeout=120) as resp:
            return resp.read()

    def parse_and_validate(self, raw: bytes) -> list[dict[str, Any]]:
        import csv
        import io

        records: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(raw.decode()))
        for row in reader:
            try:
                lon, lat = float(row["longitude"]), float(row["latitude"])
            except (KeyError, ValueError):
                continue
            if not v.valid_coords(lon, lat):
                continue
            ts = self._acq_time(row.get("acq_date"), row.get("acq_time"))
            if ts is None or not v.not_future(ts):
                continue
            # Point filters (FIRMS_point_filtering.md): drop weak and low-confidence.
            frp = _num(row.get("frp"))
            if frp is None or frp <= FRP_MIN:
                continue
            confidence = (row.get("confidence") or "").strip().lower()
            if confidence not in ("n", "h"):
                continue
            records.append({
                "lon": lon, "lat": lat, "acq_time": ts,
                "satellite": row.get("satellite") or "unknown",
                "sensor": row.get("instrument"),
                "confidence": confidence,
                "frp": frp,
                "brightness": _num(row.get("bright_ti4")),
                "daynight": (row.get("daynight") or "")[:1] or None,
                "quality": {"bright_ti5": row.get("bright_ti5"),
                            "scan": row.get("scan"), "track": row.get("track"),
                            "version": row.get("version")},
            })
        return records

    def load(self, run_id: int, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        import json

        cols = ("run_id", "lon", "lat", "acq_time", "satellite", "sensor",
                "confidence", "frp", "brightness", "daynight", "quality")
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # COPY into a temp table, then one INSERT with geom + dedupe. Much
                # faster than per-row inserts for world-sized batches.
                cur.execute(
                    "CREATE TEMP TABLE _load (run_id bigint, lon float8, lat float8,"
                    " acq_time timestamptz, satellite text, sensor text, confidence text,"
                    " frp float8, brightness float8, daynight text, quality jsonb)"
                    " ON COMMIT DROP"
                )
                with cur.copy(f"COPY _load ({','.join(cols)}) FROM STDIN") as copy:
                    for r in records:
                        copy.write_row((
                            run_id, r["lon"], r["lat"], r["acq_time"], r["satellite"],
                            r["sensor"], r["confidence"], r["frp"], r["brightness"],
                            r["daynight"], json.dumps(r["quality"]),
                        ))
                cur.execute(
                    """
                    INSERT INTO fire_detection
                      (run_id, lon, lat, geom, acq_time, satellite, sensor,
                       confidence, frp, brightness, daynight, quality)
                    SELECT run_id, lon, lat, ST_SetSRID(ST_MakePoint(lon, lat), 4326),
                           acq_time, satellite, sensor, confidence, frp, brightness,
                           daynight, quality
                      FROM _load
                    ON CONFLICT (satellite, acq_time, lon, lat) DO NOTHING
                    """
                )
                written = cur.execute(
                    "SELECT count(*) FROM fire_detection WHERE run_id = %s", (run_id,)
                ).fetchone()[0]
        # Group new detections into events, then classify wildfire vs other.
        # New events without land cover stay 'unclassified' until enriched.
        cluster_detections()
        classify_events()
        return written

    @staticmethod
    def _acq_time(acq_date: str | None, acq_time: str | None) -> datetime | None:
        if not acq_date:
            return None
        hhmm = (acq_time or "0000").zfill(4)
        try:
            return datetime.strptime(f"{acq_date} {hhmm}", "%Y-%m-%d %H%M").replace(
                tzinfo=timezone.utc)
        except ValueError:
            return None


def _num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None
