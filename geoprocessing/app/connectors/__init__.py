"""Connector registry. Provider-specific ingestion isolated behind a common shape.

The frontend never talks to providers. Connectors fetch, save provenance, validate,
and load into PostGIS. Express exposes the clean internal API to the map.
"""
from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.demo import DemoConnector
from app.connectors.firms import FirmsViirsConnector

# name -> connector class. Providers register here.
REGISTRY: dict[str, type[BaseConnector]] = {
    DemoConnector.name: DemoConnector,
    FirmsViirsConnector.name: FirmsViirsConnector,
}


def get_connector(name: str) -> BaseConnector:
    if name not in REGISTRY:
        raise KeyError(name)
    return REGISTRY[name]()


def list_connectors() -> list[str]:
    return sorted(REGISTRY)
