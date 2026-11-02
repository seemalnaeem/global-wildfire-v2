---
name: add-connector
description: Add an external data-source connector to the FastAPI ingestion framework. Use when wiring a new provider (FIRMS, ERA5, Sentinel-2, etc.) behind the internal API.
---

# Add a connector

Connectors isolate provider logic. The frontend never calls providers. Each
connector fetches, saves provenance, validates, and loads into PostGIS.

## 1. Subclass BaseConnector
Create `geoprocessing/app/connectors/<name>.py`. Set `name`, `kind`
(`api`|`vector`|`raster`), `provider`, `content_type`. Implement:
- `fetch(params) -> bytes`: provider call. Read secrets from env, never hardcode.
- `storage_key(params) -> str`: object key, add date partitions.
- `parse_and_validate(raw) -> list[dict]`: use `app.ingest.validation` helpers,
  drop bad coords/time/quality rows.
- `load(run_id, records) -> int`: parameterized inserts via `app.db.pool`.

`run()` from the base wires provenance and the `ingest_run` record for you.

## 2. Register it
Add the class to `REGISTRY` in `app/connectors/__init__.py`.

## 3. Domain table
If the target table does not exist, add it in `db/init/NN_<name>.sql`, geometry in
4326 with a GiST index (db agent). Apply to the running DB with psql.

## 4. Schedule (optional)
Add a job in `app/scheduler.py` (`scheduler.add_job(...)`). Enable with
`SCHEDULER_ENABLED=true`.

## Verify
```bash
curl -X POST :3041/connectors/<name>/run -d '{"params":{}}' -H 'Content-Type: application/json'
curl :3041/connectors/runs
```
Check the run is `success`, a `raw_file` row exists, and rows landed in the table.

## Leakage rule (for training data later)
Never load future observations as model inputs. Future values are labels only.
