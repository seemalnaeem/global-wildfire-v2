"""Generic validators shared by connectors. Reuse, do not duplicate per source."""
from __future__ import annotations

from datetime import datetime, timezone


def valid_lon(lon: float) -> bool:
    return -180.0 <= lon <= 180.0


def valid_lat(lat: float) -> bool:
    return -90.0 <= lat <= 90.0


def valid_coords(lon: float, lat: float) -> bool:
    return valid_lon(lon) and valid_lat(lat)


def not_future(ts: datetime, skew_seconds: int = 3600) -> bool:
    """Detection time must not be in the future beyond a small clock skew."""
    now = datetime.now(timezone.utc)
    return (ts - now).total_seconds() <= skew_seconds


def in_range(value: float, low: float, high: float) -> bool:
    return low <= value <= high
