"""Phase 6 endpoints: train the fire-risk model and write per-cell risk."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.model.train import train, predict, predict_live

router = APIRouter(prefix="/model")


class TrainBody(BaseModel):
    version: str = "v1"        # dataset version
    model_version: str = "m1"


class PredictBody(BaseModel):
    version: str = "v1"
    model_version: str = "m1"


class ForecastBody(BaseModel):
    model_version: str = "m1"
    neighbor_radius_deg: float = 0.75


@router.post("/train")
def train_model(body: TrainBody):
    """Train and evaluate (time-based split) on the dataset. Returns metrics."""
    return train(body.version, body.model_version)


@router.post("/predict")
def predict_risk(body: PredictBody):
    """Write per-cell fire risk for a labeled dataset cutoff into grid_prediction."""
    return predict(body.version, body.model_version)


@router.post("/forecast")
def forecast_risk(body: ForecastBody):
    """Write a live next-24h risk map anchored to the latest detections (fresh)."""
    return predict_live(body.model_version, body.neighbor_radius_deg)
