"""Database access for the geoprocessing service. One shared connection pool."""
from __future__ import annotations

import os

from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Opened lazily on first use, closed on app shutdown.
pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=5, open=False)


def open_pool() -> None:
    pool.open()


def close_pool() -> None:
    pool.close()
