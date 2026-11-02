"""Phase 7 endpoint: run fire-spread forecasts for active fire complexes."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.spread.simulate import forecast_spread

router = APIRouter(prefix="/spread")


class SpreadBody(BaseModel):
    hours: int = 24               # forecast horizon
    max_complexes: int = 20       # cap for cost: biggest active fires first
    cell_deg: float = 0.02        # local grid resolution (~2 km)
    ensemble: int = 30            # Monte Carlo members (drives the uncertainty)
    step_hours: int = 1
    min_prob: float = 0.05        # store cells at/above this burn probability


@router.post("/forecast")
def spread_forecast(body: SpreadBody):
    """Simulate next-horizon spread from active fires, store per-cell burn probability."""
    return forecast_spread(hours=body.hours, max_complexes=body.max_complexes,
                           cell_deg=body.cell_deg, ensemble=body.ensemble,
                           step_hours=body.step_hours, min_prob=body.min_prob)
