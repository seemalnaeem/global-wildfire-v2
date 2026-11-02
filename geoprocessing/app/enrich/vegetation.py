"""Vegetation indices from Sentinel-2 via Copernicus Data Space (Sentinel Hub).

Computes NDVI, NDMI, NBR at a fire point using the Statistical API with an SCL
cloud mask, and returns the most recent cloud-free observation. Needs CDSE OAuth
credentials (client id + secret). The frontend never calls Copernicus directly,
this module is the connector boundary.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

EVALSCRIPT = """//VERSION=3
function setup(){return{input:[{bands:["B04","B08","B11","B12","SCL","dataMask"]}],
 output:[{id:"idx",bands:3,sampleType:"FLOAT32"},{id:"dataMask",bands:1}]}}
function evaluatePixel(s){
 var ndvi=(s.B08-s.B04)/(s.B08+s.B04);
 var ndmi=(s.B08-s.B11)/(s.B08+s.B11);
 var nbr=(s.B08-s.B12)/(s.B08+s.B12);
 var m=s.dataMask; var c=s.SCL;
 if(c==0||c==1||c==3||c==8||c==9||c==10||c==11)m=0;
 return {idx:[ndvi,ndmi,nbr], dataMask:[m]};
}"""

_token = {"value": None, "exp": 0.0}


def _get_token() -> str | None:
    cid = os.environ.get("CDSE_CLIENT_ID")
    secret = os.environ.get("CDSE_CLIENT_SECRET")
    if not cid or not secret:
        return None
    now = time.time()
    if _token["value"] and _token["exp"] - 60 > now:
        return _token["value"]
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": cid, "client_secret": secret,
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as resp:
        d = json.load(resp)
    _token["value"] = d["access_token"]
    _token["exp"] = now + float(d.get("expires_in", 1800))
    return _token["value"]


def _mean(interval: dict, band: str) -> float | None:
    try:
        v = float(interval["outputs"]["idx"]["bands"][band]["stats"]["mean"])
        return None if math.isnan(v) else v
    except (KeyError, ValueError, TypeError):
        return None


def fetch_indices(lon: float, lat: float, lookback_days: int = 365,
                  buffer_deg: float = 0.003) -> dict | None:
    """Most recent cloud-free NDVI/NDMI/NBR near (lon, lat), or None."""
    token = _get_token()
    if not token:
        return None
    now = datetime.now(timezone.utc)
    d = buffer_deg
    poly = [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
             [lon - d, lat + d], [lon - d, lat - d]]]
    body = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": poly},
                       "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
            "data": [{"type": "sentinel-2-l2a"}],
        },
        "aggregation": {
            "timeRange": {
                "from": (now - timedelta(days=lookback_days)).strftime("%Y-%m-%dT00:00:00Z"),
                "to": (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
            },
            "aggregationInterval": {"of": "P30D"},
            "evalscript": EVALSCRIPT, "resx": 10, "resy": 10,
        },
    }
    req = urllib.request.Request(
        STATS_URL, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError:
        return None

    clear = [it for it in data.get("data", []) if _mean(it, "B0") is not None]
    if not clear:
        return None
    it = clear[-1]  # most recent interval with valid data
    return {
        "ndvi": _mean(it, "B0"), "ndmi": _mean(it, "B1"), "nbr": _mean(it, "B2"),
        "obs_date": it["interval"]["to"],
    }
