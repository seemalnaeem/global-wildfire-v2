"""Phase 6: fire-risk model. Trains a gradient-boosting classifier on grid_sample
to predict the next-24h fire probability per cell, evaluates it leakage-safely
(train on earlier cutoffs, test on the latest), and writes per-cell risk.

The final developer rule from the proposal: the data pipeline comes first. This
only trains once the leakage-safe dataset exists.
"""
from __future__ import annotations

import os
import pickle

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from app.db import pool

MODEL_DIR = os.path.join(os.environ.get("DATA_DIR", "/data"), "models")

# Feature order. HistGradientBoosting handles NaN natively, so nulls are fine.
FEATURES = [
    "elevation", "slope", "aspect", "landcover_code", "veg_greenness",
    "det_past_24h", "det_past_48h", "det_past_72h", "frp_past_24h", "had_fire",
    "neigh_det_24h",
    "temp_c", "rh", "wind_speed_kmh", "precip_mm", "vpd_kpa", "soil_moist_surface",
]

_SELECT = """
SELECT s.cell_id, s.prediction_time,
  c.elevation, c.slope, c.aspect, c.landcover_code, c.veg_greenness,
  s.det_past_24h, s.det_past_48h, s.det_past_72h, s.frp_past_24h, (s.had_fire)::int,
  s.neigh_det_24h,
  s.temp_c, s.rh, s.wind_speed_kmh, s.precip_mm, s.vpd_kpa, s.soil_moist_surface,
  (s.label_fire_next_24h)::int
FROM grid_sample s JOIN grid_cell c ON c.id = s.cell_id
WHERE s.dataset_version = %s {extra}
ORDER BY s.prediction_time, s.cell_id
"""

_N = len(FEATURES)  # feature columns are r[2 : 2+_N], label is r[2+_N]


def _f(v) -> float:
    return float("nan") if v is None else float(v)


def _ece(y_true, p, bins: int = 10) -> float:
    """Expected calibration error: mean gap between predicted and observed fire rate
    across probability bins, weighted by bin size. Lower is better calibrated."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    n = len(p)
    err = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            err += (m.sum() / n) * abs(p[m].mean() - y_true[m].mean())
    return round(float(err), 4)


def _load(version: str, prediction_time=None):
    extra = "AND s.prediction_time = %s" if prediction_time else ""
    args = (version, prediction_time) if prediction_time else (version,)
    with pool.connection() as conn:
        rows = conn.execute(_SELECT.format(extra=extra), args).fetchall()
    cell_ids = [r[0] for r in rows]
    times = [r[1] for r in rows]
    X = np.array([[_f(v) for v in r[2:2 + _N]] for r in rows], dtype=float)
    y = np.array([r[2 + _N] for r in rows], dtype=int)
    return cell_ids, times, X, y


def train(version: str, model_version: str = "m1") -> dict:
    cell_ids, times, X, y = _load(version)
    uniq = sorted(set(times))
    if len(uniq) < 2:
        raise ValueError("need at least 2 prediction_times for a time-based split")
    test_time = uniq[-1]
    is_test = np.array([t == test_time for t in times])

    # Gradient boosting, wrapped in isotonic calibration for honest probabilities.
    base = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06,
                                          max_leaf_nodes=31, l2_regularization=1.0)
    clf = CalibratedClassifierCV(base, method="isotonic", cv=3)
    clf.fit(X[~is_test], y[~is_test])
    p = clf.predict_proba(X[is_test])[:, 1]
    yt = y[is_test]
    metrics = {
        "pr_auc": round(float(average_precision_score(yt, p)), 4),
        "roc_auc": round(float(roc_auc_score(yt, p)), 4),
        "brier": round(float(brier_score_loss(yt, p)), 4),
        "ece": _ece(yt, p),
        "base_rate": round(float(yt.mean()), 4),
        "n_cutoffs": len(uniq),
        "train_rows": int((~is_test).sum()), "test_rows": int(is_test.sum()),
        "test_time": str(test_time),
    }
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, f"fire_risk_{model_version}.pkl"), "wb") as fh:
        pickle.dump({"model": clf, "features": FEATURES}, fh)
    return {"model_version": model_version, "dataset": version, **metrics}


# Live forecast: features computed at the CURRENT fire situation (cutoff = latest
# detection), not a past training cutoff. No label needed, so the risk map stays
# fresh instead of freezing on the last labeled cutoff (which lags ~1 day).
_LIVE_FEATURES = """
CREATE TEMP TABLE _fc ON COMMIT DROP AS
SELECT c.id AS cell_id, c.centroid,
  c.elevation, c.slope, c.aspect, c.landcover_code, c.veg_greenness,
  count(d.id) FILTER (WHERE d.acq_time > %(pt)s - interval '24 hours' AND d.acq_time <= %(pt)s) AS det_past_24h,
  count(d.id) FILTER (WHERE d.acq_time > %(pt)s - interval '48 hours' AND d.acq_time <= %(pt)s) AS det_past_48h,
  count(d.id) FILTER (WHERE d.acq_time > %(pt)s - interval '72 hours' AND d.acq_time <= %(pt)s) AS det_past_72h,
  COALESCE(sum(d.frp) FILTER (WHERE d.acq_time > %(pt)s - interval '24 hours' AND d.acq_time <= %(pt)s), 0) AS frp_past_24h,
  COALESCE(bool_or(d.acq_time <= %(pt)s), false) AS had_fire
FROM grid_cell c
LEFT JOIN fire_detection d ON ST_Contains(c.geom, d.geom)
GROUP BY c.id
"""

# Neighborhood pressure as a set-based self-join (GiST index on the temp centroid).
_LIVE_SELECT = """
SELECT f.cell_id,
  f.elevation, f.slope, f.aspect, f.landcover_code, f.veg_greenness,
  f.det_past_24h, f.det_past_48h, f.det_past_72h, f.frp_past_24h, (f.had_fire)::int,
  COALESCE(n.cnt, 0)
FROM _fc f
LEFT JOIN (
  SELECT a.cell_id, sum(b.det_past_24h) AS cnt
  FROM _fc a JOIN _fc b ON b.cell_id <> a.cell_id
       AND ST_DWithin(a.centroid, b.centroid, %(r)s)
  GROUP BY a.cell_id
) n ON n.cell_id = f.cell_id
ORDER BY f.cell_id
"""

# The 11 features the live query supplies, in FEATURES order; weather (the last 6)
# is left NaN, which the global model was trained with anyway.
_LIVE_N = 11


def predict_live(model_version: str = "m1", neighbor_radius_deg: float = 0.75) -> dict:
    """Forecast next-24h risk from the current fire situation. The cutoff is the
    latest detection time, so this reflects fires burning now, not a stale cutoff."""
    with open(os.path.join(MODEL_DIR, f"fire_risk_{model_version}.pkl"), "rb") as fh:
        bundle = pickle.load(fh)
    clf, feats = bundle["model"], bundle["features"]

    with pool.connection() as conn:
        with conn.cursor() as cur:
            pt = cur.execute("SELECT max(acq_time) FROM fire_detection").fetchone()[0]
            if pt is None:
                return {"error": "no detections to forecast from"}
            cur.execute(_LIVE_FEATURES, {"pt": pt})
            cur.execute("CREATE INDEX ON _fc USING gist (centroid)")
            cur.execute("ANALYZE _fc")
            rows = cur.execute(_LIVE_SELECT, {"r": neighbor_radius_deg}).fetchall()

            cell_ids = [r[0] for r in rows]
            base = np.array([[_f(v) for v in r[1:1 + _LIVE_N]] for r in rows], dtype=float)
            pad = np.full((len(rows), len(feats) - _LIVE_N), np.nan)  # NaN weather cols
            X = np.hstack([base, pad])
            risk = clf.predict_proba(X)[:, 1]

            cur.executemany(
                """INSERT INTO grid_prediction (cell_id, prediction_time, risk, model_version)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (cell_id, prediction_time, model_version)
                   DO UPDATE SET risk = EXCLUDED.risk, created_at = now()""",
                [(cid, pt, float(rk), model_version)
                 for cid, rk in zip(cell_ids, risk)])
    return {"model_version": model_version, "issued_at": str(pt),
            "cells": len(cell_ids), "mean_risk": round(float(risk.mean()), 4),
            "max_risk": round(float(risk.max()), 4)}


def predict(version: str, model_version: str = "m1", prediction_time=None) -> dict:
    with open(os.path.join(MODEL_DIR, f"fire_risk_{model_version}.pkl"), "rb") as fh:
        bundle = pickle.load(fh)
    clf = bundle["model"]

    if prediction_time is None:  # latest cutoff in the dataset
        with pool.connection() as conn:
            prediction_time = conn.execute(
                "SELECT max(prediction_time) FROM grid_sample WHERE dataset_version=%s",
                (version,)).fetchone()[0]

    cell_ids, times, X, _ = _load(version, prediction_time)
    risk = clf.predict_proba(X)[:, 1]
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO grid_prediction (cell_id, prediction_time, risk, model_version)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (cell_id, prediction_time, model_version)
                   DO UPDATE SET risk = EXCLUDED.risk, created_at = now()""",
                [(cid, prediction_time, float(rk), model_version)
                 for cid, rk in zip(cell_ids, risk)])
    return {"model_version": model_version, "prediction_time": str(prediction_time),
            "cells": len(cell_ids), "mean_risk": round(float(risk.mean()), 4),
            "max_risk": round(float(risk.max()), 4)}
