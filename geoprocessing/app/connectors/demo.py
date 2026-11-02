"""Demo connector. Proves the ingestion loop end to end with no external network.

It emits a tiny in-memory CSV of sample detections, saves it to object storage,
validates, and loads into fire_incidents. Replace this pattern with the FIRMS
connector in Phase 2. It does not fetch anything remote.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import BaseConnector
from app.db import pool
from app.ingest import validation as v


class DemoConnector(BaseConnector):
    name = "demo"
    kind = "api"
    provider = "internal-sample"
    content_type = "text/csv"

    # Deterministic sample points near the elevation/slope data extent.
    _SAMPLE = [
        (70.10, 30.05, 0.88),
        (71.40, 31.20, 0.72),
        (69.30, 29.50, 0.95),
        (200.0, 30.0, 0.50),   # invalid lon, must be dropped by validation
    ]

    def fetch(self, params: dict[str, Any]) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["longitude", "latitude", "confidence", "acq_datetime"])
        now = datetime.now(timezone.utc).isoformat()
        for lon, lat, conf in self._SAMPLE:
            w.writerow([lon, lat, conf, now])
        return buf.getvalue().encode()

    def storage_key(self, params: dict[str, Any]) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"raw/{self.name}/{stamp}.csv"

    def parse_and_validate(self, raw: bytes) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(raw.decode()))
        for row in reader:
            lon, lat = float(row["longitude"]), float(row["latitude"])
            ts = datetime.fromisoformat(row["acq_datetime"])
            if not v.valid_coords(lon, lat):
                continue
            if not v.not_future(ts):
                continue
            records.append({"lon": lon, "lat": lat,
                            "confidence": float(row["confidence"]), "observed_at": ts})
        return records

    def load(self, run_id: int, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for r in records:
                    cur.execute(
                        """
                        INSERT INTO fire_incidents (name, observed_at, confidence, geom)
                        VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                        """,
                        (f"demo:{self.name}", r["observed_at"], r["confidence"], r["lon"], r["lat"]),
                    )
        return len(records)
