"""Weather enrichment via Open-Meteo (free, no auth).

Open-Meteo serves ERA5-based reanalysis and forecasts. We fetch the current
fire-relevant parameters at fire points. Swap the base URL for ECMWF/ERA5 with
credentials later; the parsed shape stays the same. The frontend never calls
Open-Meteo directly, this module is the connector boundary.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

log = logging.getLogger("gwf.weather")

BASE = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
CURRENT = ",".join([
    "temperature_2m", "relative_humidity_2m", "dew_point_2m",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    "precipitation", "surface_pressure",
    # Moisture and dryness (fire relevant).
    "soil_moisture_0_to_1cm", "soil_moisture_3_to_9cm",
    "soil_temperature_0cm", "vapour_pressure_deficit",
])


def _parse(cur: dict) -> dict:
    ts = cur.get("time")
    return {
        "temp_c": cur.get("temperature_2m"),
        "rh": cur.get("relative_humidity_2m"),
        "dew_point_c": cur.get("dew_point_2m"),
        "wind_speed_kmh": cur.get("wind_speed_10m"),
        "wind_dir_deg": cur.get("wind_direction_10m"),
        "wind_gust_kmh": cur.get("wind_gusts_10m"),
        "precip_mm": cur.get("precipitation"),
        "pressure_hpa": cur.get("surface_pressure"),
        "soil_moist_surface": cur.get("soil_moisture_0_to_1cm"),
        "soil_moist_root": cur.get("soil_moisture_3_to_9cm"),
        "soil_temp_c": cur.get("soil_temperature_0cm"),
        "vpd_kpa": cur.get("vapour_pressure_deficit"),
        "weather_time": datetime.fromisoformat(ts) if ts else None,
    }


def fetch_weather(points: list[tuple[float, float]]) -> list[dict | None]:
    """Return current weather per point. Open-Meteo takes many locations per call."""
    if not points:
        return []
    lats = ",".join(f"{lat:.4f}" for _, lat in points)
    lons = ",".join(f"{lon:.4f}" for lon, _ in points)
    qs = urllib.parse.urlencode({"latitude": lats, "longitude": lons, "current": CURRENT})
    # Open-Meteo (free tier) rate-limits (HTTP 429) and has brief outages (503).
    # Degrade gracefully: return None per point so callers show "unavailable" rather
    # than crashing the request.
    try:
        with urllib.request.urlopen(f"{BASE}?{qs}", timeout=60) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as e:
        code = getattr(e, "code", None)
        log.warning("weather provider unavailable (%s), returning no data", code or e)
        return [None] * len(points)
    # One location returns an object, several return a list. Normalize to a list.
    items = data if isinstance(data, list) else [data]
    out: list[dict | None] = []
    for item in items:
        cur = item.get("current")
        out.append(_parse(cur) if cur else None)
    # Guard against a length mismatch.
    while len(out) < len(points):
        out.append(None)
    return out[:len(points)]
