-- Phase 2: live fire monitoring. Raw detections and grouped fire events.

-- A fire event groups many nearby detections over time. Its id is permanent.
CREATE TABLE IF NOT EXISTS fire_event (
  id              bigserial PRIMARY KEY,
  centroid        geometry(Point, 4326) NOT NULL,
  first_detected  timestamptz NOT NULL,
  last_detected   timestamptz NOT NULL,
  detection_count integer NOT NULL DEFAULT 0,
  max_frp         double precision,
  frp_sum         double precision,     -- combined FRP of all detections
  boundary        geometry(Polygon, 4326), -- convex hull of the cluster
  status          text NOT NULL DEFAULT 'active',
  -- Wildfire classification: 'wildfire' | 'other' | 'unclassified'.
  category        text NOT NULL DEFAULT 'unclassified',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fire_event_centroid_gix ON fire_event USING gist (centroid);
CREATE INDEX IF NOT EXISTS fire_event_last_idx ON fire_event (last_detected DESC);
CREATE INDEX IF NOT EXISTS fire_event_category_idx ON fire_event (category);

-- Every original satellite detection. Kept forever for provenance and history.
CREATE TABLE IF NOT EXISTS fire_detection (
  id          bigserial PRIMARY KEY,
  run_id      bigint REFERENCES ingest_run(id) ON DELETE SET NULL,
  event_id    bigint REFERENCES fire_event(id) ON DELETE SET NULL,
  lon         double precision NOT NULL,
  lat         double precision NOT NULL,
  geom        geometry(Point, 4326) NOT NULL,
  acq_time    timestamptz NOT NULL,
  satellite   text NOT NULL DEFAULT 'unknown',
  sensor      text,                       -- instrument, for example VIIRS
  confidence  text,                        -- VIIRS: l | n | h
  frp         double precision,            -- Fire Radiative Power (MW)
  brightness  double precision,            -- bright_ti4
  daynight    char(1),                     -- D | N
  quality     jsonb NOT NULL DEFAULT '{}', -- extra flags kept for provenance
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fire_detection_geom_gix ON fire_detection USING gist (geom);
CREATE INDEX IF NOT EXISTS fire_detection_acq_idx ON fire_detection (acq_time DESC);
CREATE INDEX IF NOT EXISTS fire_detection_event_idx ON fire_detection (event_id);

-- Dedupe key: the same detection can arrive across runs. Ignore repeats on load.
CREATE UNIQUE INDEX IF NOT EXISTS fire_detection_natural_uid
  ON fire_detection (satellite, acq_time, lon, lat);
