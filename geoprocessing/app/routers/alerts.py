"""Phase 8 endpoint: (re)evaluate alert rules against the live data."""
from fastapi import APIRouter

from app.alerts.engine import evaluate_alerts

router = APIRouter(prefix="/alerts")


@router.post("/evaluate")
def evaluate():
    """Recompute alerts from current events + spread forecasts. Idempotent."""
    return evaluate_alerts()
