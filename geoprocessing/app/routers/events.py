"""Internal endpoints for fire-event maintenance (clustering and enrichment)."""
from fastapi import APIRouter

from app.events.cluster import cluster_detections
from app.events.classify import classify_events
from app.enrich.service import (
    enrich_events, enrich_one, enrich_weather_one, enrich_vegetation_one,
)

router = APIRouter(prefix="/events")


@router.post("/cluster")
def cluster():
    """Group any unassigned detections into events. Safe to run repeatedly."""
    return cluster_detections()


@router.post("/classify")
def classify():
    """Classify events as wildfire vs other by the configured thresholds."""
    return classify_events()


@router.post("/enrich")
def enrich(limit: int = 500):
    """Enrich up to `limit` events that lack context (terrain + land cover)."""
    return enrich_events(limit)


@router.post("/{event_id}/enrich")
def enrich_event(event_id: int):
    """Enrich a single event on demand (lazy enrichment from the details view)."""
    return enrich_one(event_id)


@router.post("/{event_id}/enrich-weather")
def enrich_event_weather(event_id: int):
    """Fetch current weather for a single event (lazy, refreshed when stale)."""
    return enrich_weather_one(event_id)


@router.post("/{event_id}/enrich-vegetation")
def enrich_event_vegetation(event_id: int):
    """Fetch Sentinel-2 vegetation indices for a single event (lazy, on open)."""
    return enrich_vegetation_one(event_id)
