"""Global Wildfire Portal geoprocessing service (FastAPI + GDAL/OGR).

Also hosts the Phase 1 ingestion framework: connectors, provenance, and an
embedded scheduler. Express stays the browser-facing API, connectors never
touch the frontend.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import scheduler
from app.db import open_pool, close_pool
from app.routers import health, ingest, connectors, events, training, model, spread, alerts

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    scheduler.start()
    yield
    scheduler.shutdown()
    close_pool()


app = FastAPI(title="gwf-geoprocessing", version="0.2.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(connectors.router)
app.include_router(events.router)
app.include_router(training.router)
app.include_router(model.router)
app.include_router(spread.router)
app.include_router(alerts.router)
