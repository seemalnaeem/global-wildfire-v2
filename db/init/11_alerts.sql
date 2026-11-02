-- Phase 8: alerts. Rule-based notifications derived from the live data (large active
-- wildfires, large forecast spread). Regenerated each run: qualifying events upsert an
-- alert (one per kind+event), and alerts whose event no longer qualifies are resolved.

CREATE TABLE IF NOT EXISTS alert (
  id         bigserial PRIMARY KEY,
  kind       text NOT NULL,                 -- large_fire | spread_threat
  severity   text NOT NULL,                 -- info | warning | critical
  event_id   bigint REFERENCES fire_event(id) ON DELETE CASCADE,
  centroid   geometry(Point, 4326),
  title      text NOT NULL,
  message    text NOT NULL,
  value      double precision,              -- the triggering metric
  status     text NOT NULL DEFAULT 'active',-- active | resolved | acknowledged
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kind, event_id)                   -- one alert per rule per event
);
CREATE INDEX IF NOT EXISTS alert_status_idx ON alert (status, severity, updated_at DESC);
CREATE INDEX IF NOT EXISTS alert_centroid_gix ON alert USING gist (centroid);
