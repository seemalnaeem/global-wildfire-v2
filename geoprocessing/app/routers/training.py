"""Phase 5 endpoints: build the grid and the leakage-safe training dataset."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.training.grid import build_grid
from app.training.samples import build_samples, enrich_weather

router = APIRouter(prefix="/training")


class GridBody(BaseModel):
    bbox: tuple[float, float, float, float]  # west, south, east, north
    size_deg: float = 0.1
    land_only: bool = False


class SamplesBody(BaseModel):
    version: str = "v1"
    window_hours: int = 24
    step_hours: int = 12
    neighbor_radius_deg: float = 0.3


@router.post("/grid")
def grid(body: GridBody):
    """Build the study-area grid and its static features."""
    return build_grid(tuple(body.bbox), body.size_deg, body.land_only)


@router.post("/samples")
def samples(body: SamplesBody):
    """Build training rows (features known at each cutoff, next-window fire label)."""
    return build_samples(body.version, body.window_hours, body.step_hours,
                         body.neighbor_radius_deg)


class VersionBody(BaseModel):
    version: str = "v1"


@router.post("/enrich-weather")
def enrich_weather_endpoint(body: VersionBody):
    """Fill weather observed at each prediction_time (NASA POWER)."""
    return enrich_weather(body.version)
