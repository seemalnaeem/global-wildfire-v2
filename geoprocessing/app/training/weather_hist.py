"""Historical weather for grid samples, from NASA POWER (free, no auth).

Point based, but POWER's grid is ~0.5 deg, so we dedupe cell centroids to that
resolution, fetch the unique points in parallel, and map back. Values are for the
prediction hour (observed at the cutoff, not the future), so they are leakage safe.
Open-Meteo is the alternative but its free daily quota is small.
"""
from __future__ import annotations

import json
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor

POWER = "https://power.larc.nasa.gov/api/temporal/hourly/point"
PARAMS = "T2M,RH2M,WS10M,PRECTOTCORR,GWETTOP"


def _key(lon: float, lat: float) -> tuple[float, float]:
    return (round(lon * 2) / 2, round(lat * 2) / 2)


def _vpd(t: float | None, rh: float | None) -> float | None:
    if t is None or rh is None:
        return None
    es = 0.6108 * math.exp(17.27 * t / (t + 237.3))
    return round(es * (1 - rh / 100.0), 3)


def _fetch_point(lon: float, lat: float, date: str, hourkey: str) -> dict | None:
    url = (f"{POWER}?parameters={PARAMS}&community=AG&longitude={lon}&latitude={lat}"
           f"&start={date}&end={date}&format=JSON&time-standard=UTC")
    try:
        with urllib.request.urlopen(url, timeout=40) as resp:
            p = json.load(resp)["properties"]["parameter"]
    except Exception:
        return None

    def g(name: str) -> float | None:
        v = p.get(name, {}).get(hourkey)
        return None if v is None or v <= -900 else v

    t, rh, ws = g("T2M"), g("RH2M"), g("WS10M")
    return {
        "temp_c": t, "rh": rh,
        "wind_speed_kmh": round(ws * 3.6, 2) if ws is not None else None,
        "precip_mm": g("PRECTOTCORR"),
        "soil_moist_surface": g("GWETTOP"),
        "vpd_kpa": _vpd(t, rh),
    }


def fetch_weather_at(points: list[tuple[float, float]], when, workers: int = 8) -> list[dict | None]:
    """Weather at each point at `when` (UTC). Dedupes to the POWER grid."""
    date = when.strftime("%Y%m%d")
    hourkey = when.strftime("%Y%m%d%H")
    keys = {_key(lon, lat) for lon, lat in points}
    klist = list(keys)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda k: _fetch_point(k[0], k[1], date, hourkey), klist))
    lookup = dict(zip(klist, results))
    return [lookup.get(_key(lon, lat)) for lon, lat in points]
