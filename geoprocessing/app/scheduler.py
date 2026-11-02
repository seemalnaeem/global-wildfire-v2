"""Embedded scheduler (APScheduler). No extra container, runs inside FastAPI.

Off by default (SCHEDULER_ENABLED=true to enable). When on, it keeps the fire data
current: a periodic refresh prunes stale detections, pulls fresh FIRMS, re-clusters,
enriches land cover, and re-classifies. Without this the time filters (24/48/72h)
go empty as the snapshot ages.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger("gwf.scheduler")
scheduler = AsyncIOScheduler(timezone="UTC")

SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "false").lower() == "true"
REFRESH_HOURS = float(os.environ.get("FIRMS_REFRESH_HOURS", "6"))
RETENTION_DAYS = int(os.environ.get("FIRMS_RETENTION_DAYS", "5"))


def _heartbeat() -> None:
    log.info("scheduler heartbeat")


def _prune_old_detections() -> None:
    from app.db import pool
    with pool.connection() as conn:
        conn.execute(
            "DELETE FROM fire_detection WHERE acq_time < now() - (%s * interval '1 day')",
            (RETENTION_DAYS,),
        )


def refresh_fires() -> dict:
    """Prune stale detections, pull fresh FIRMS, enrich land cover, classify.

    The FIRMS connector run already clusters and classifies; new events lack land
    cover, so enrich then classify again. Safe to call manually too.
    """
    from app.connectors import get_connector
    from app.enrich.service import enrich_events
    from app.events.classify import classify_events

    log.info("fire refresh: start (retention=%sd)", RETENTION_DAYS)
    _prune_old_detections()
    ingest = get_connector("firms_viirs").run({"days": os.environ.get("FIRMS_DAYS", "1")})
    enriched = enrich_events(limit=1_000_000)
    classified = classify_events()
    # Re-issue the live risk forecast so the map reflects the fresh fire situation.
    # Best effort: the model may not be trained yet on a first boot.
    forecast = None
    try:
        from app.model.train import predict_live
        forecast = predict_live()
    except Exception:  # noqa: BLE001 forecast is best effort, keep the refresh alive
        log.exception("live forecast skipped")
    # Phase 7: re-run spread forecasts from the freshly updated active fires.
    spread = None
    try:
        from app.spread.simulate import forecast_spread
        spread = forecast_spread()
    except Exception:  # noqa: BLE001 best effort
        log.exception("spread forecast skipped")
    # Phase 8: re-evaluate alerts from the fresh events + spread.
    alerts = None
    try:
        from app.alerts.engine import evaluate_alerts
        alerts = evaluate_alerts()
    except Exception:  # noqa: BLE001 best effort
        log.exception("alert evaluation skipped")
    log.info("fire refresh: done ingest=%s enriched=%s classified=%s forecast=%s "
             "spread=%s alerts=%s", ingest, enriched, classified, forecast, spread, alerts)
    return {"ingest": ingest, "enriched": enriched, "classified": classified,
            "forecast": forecast, "spread": spread, "alerts": alerts}


def _refresh_job() -> None:
    try:
        refresh_fires()
    except Exception:  # noqa: BLE001 keep the scheduler alive on failure
        log.exception("fire refresh failed")


def register_jobs() -> None:
    scheduler.add_job(_heartbeat, "interval", minutes=15, id="heartbeat",
                      replace_existing=True)
    # First run fires one interval after start, not on boot (the job is heavy).
    scheduler.add_job(_refresh_job, "interval", hours=REFRESH_HOURS,
                      id="firms_refresh", replace_existing=True)


def start() -> None:
    register_jobs()
    if SCHEDULER_ENABLED:
        scheduler.start()
        log.info("scheduler started, FIRMS refresh every %s h", REFRESH_HOURS)
    else:
        log.info("scheduler configured but disabled (set SCHEDULER_ENABLED=true)")


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
