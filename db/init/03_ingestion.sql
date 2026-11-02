-- Phase 1 foundation: ingestion framework and provenance.
-- Domain tables (fire detections, events, weather, etc.) are added per later phase.

-- Registry of external and internal data sources. One row per logical source.
CREATE TABLE IF NOT EXISTS data_source (
  id         bigserial PRIMARY KEY,
  name       text UNIQUE NOT NULL,        -- for example 'nasa_firms_viirs'
  kind       text NOT NULL,               -- 'api' | 'vector' | 'raster'
  provider   text,                        -- for example 'NASA FIRMS'
  config     jsonb NOT NULL DEFAULT '{}', -- connector settings, no secrets
  enabled    boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- One row per ingestion run. The provenance and audit backbone.
CREATE TABLE IF NOT EXISTS ingest_run (
  id          bigserial PRIMARY KEY,
  source_id   bigint REFERENCES data_source(id) ON DELETE CASCADE,
  connector   text NOT NULL,
  status      text NOT NULL DEFAULT 'running', -- 'running'|'success'|'failed'
  params      jsonb NOT NULL DEFAULT '{}',
  rows_in     integer,
  rows_out    integer,
  message     text,
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS ingest_run_source_idx ON ingest_run (source_id, started_at DESC);

-- Provenance for every original file fetched. The file itself lives in object
-- storage (local volume now, S3/MinIO later). This row keeps the pointer.
CREATE TABLE IF NOT EXISTS raw_file (
  id           bigserial PRIMARY KEY,
  run_id       bigint REFERENCES ingest_run(id) ON DELETE CASCADE,
  uri          text NOT NULL,             -- storage key or path, backend agnostic
  bytes        bigint,
  checksum     text,                      -- sha256 hex
  content_type text,
  meta         jsonb NOT NULL DEFAULT '{}',
  fetched_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS raw_file_run_idx ON raw_file (run_id);
