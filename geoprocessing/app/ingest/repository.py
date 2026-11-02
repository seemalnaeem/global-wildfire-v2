"""Provenance repository. Records sources, runs, and raw files in PostGIS.

This is the audit backbone from the proposal: every fetched original is registered
so any dataset can be traced back to its source and run.
"""
from __future__ import annotations

import json
from typing import Any

from app.db import pool
from app.storage import StoredObject


def upsert_source(name: str, kind: str, provider: str | None = None,
                  config: dict[str, Any] | None = None) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO data_source (name, kind, provider, config)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
              SET kind = EXCLUDED.kind, provider = EXCLUDED.provider,
                  config = EXCLUDED.config
            RETURNING id
            """,
            (name, kind, provider, json.dumps(config or {})),
        ).fetchone()
        return row[0]


def start_run(source_id: int, connector: str, params: dict[str, Any] | None = None) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO ingest_run (source_id, connector, params) VALUES (%s, %s, %s) RETURNING id",
            (source_id, connector, json.dumps(params or {})),
        ).fetchone()
        return row[0]


def finish_run(run_id: int, status: str, rows_in: int | None = None,
               rows_out: int | None = None, message: str | None = None) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE ingest_run
               SET status = %s, rows_in = %s, rows_out = %s, message = %s,
                   finished_at = now()
             WHERE id = %s
            """,
            (status, rows_in, rows_out, message, run_id),
        )


def register_raw_file(run_id: int, obj: StoredObject, meta: dict[str, Any] | None = None) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO raw_file (run_id, uri, bytes, checksum, content_type, meta)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (run_id, obj.uri, obj.bytes, obj.checksum, obj.content_type, json.dumps(meta or {})),
        ).fetchone()
        return row[0]


def recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    with pool.connection() as conn:
        cur = conn.execute(
            """
            SELECT r.id, s.name AS source, r.connector, r.status,
                   r.rows_in, r.rows_out, r.message, r.started_at, r.finished_at
              FROM ingest_run r LEFT JOIN data_source s ON s.id = r.source_id
             ORDER BY r.started_at DESC LIMIT %s
            """,
            (limit,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
