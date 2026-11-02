"""Ingest endpoints. Long jobs should run in the background, not block the request."""
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from shared.py.geo import to_cog, load_vector

router = APIRouter(prefix="/ingest")

DATA_DIR = os.environ.get("DATA_DIR", "/data")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


class RasterJob(BaseModel):
    src: str  # file name inside DATA_DIR, for example "slope.tif"


class VectorJob(BaseModel):
    src: str  # file name inside DATA_DIR
    table: str


def _safe_path(name: str) -> str:
    path = os.path.normpath(os.path.join(DATA_DIR, name))
    if not path.startswith(os.path.abspath(DATA_DIR)):
        raise HTTPException(400, "path escapes data dir")
    return path


@router.post("/raster")
def ingest_raster(job: RasterJob, tasks: BackgroundTasks):
    src = _safe_path(job.src)
    dst = src.rsplit(".", 1)[0] + ".cog.tif"
    tasks.add_task(to_cog, src, dst)
    return {"status": "started", "output": os.path.basename(dst)}


@router.post("/vector")
def ingest_vector(job: VectorJob, tasks: BackgroundTasks):
    src = _safe_path(job.src)
    tasks.add_task(load_vector, src, job.table, DATABASE_URL)
    return {"status": "started", "table": job.table}
