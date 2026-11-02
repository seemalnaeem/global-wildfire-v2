"""Internal API for the ingestion framework. Trigger connectors, inspect runs.

These endpoints are internal (called by operators, the scheduler, or Express),
not by the browser directly.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.connectors import get_connector, list_connectors
from app.ingest import repository as repo
from app.scheduler import refresh_fires

router = APIRouter(prefix="/connectors")


class RunBody(BaseModel):
    params: dict = {}
    background: bool = False


@router.get("")
def connectors():
    return {"connectors": list_connectors()}


@router.post("/refresh")
def refresh(tasks: BackgroundTasks):
    """Run the full fire refresh now (prune, ingest, enrich, classify) in the
    background. Same work the scheduler does periodically."""
    tasks.add_task(refresh_fires)
    return {"status": "started"}


@router.get("/runs")
def runs(limit: int = 20):
    return {"runs": repo.recent_runs(limit)}


@router.post("/{name}/run")
def run_connector(name: str, body: RunBody, tasks: BackgroundTasks):
    try:
        connector = get_connector(name)
    except KeyError:
        raise HTTPException(404, f"unknown connector: {name}")
    if body.background:
        tasks.add_task(connector.run, body.params)
        return {"status": "started", "connector": name}
    return connector.run(body.params)
