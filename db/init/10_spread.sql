-- Phase 7: fire-spread forecasting. For each active fire complex we run a Monte
-- Carlo cellular-automaton spread simulation on a local fine grid. Each output row
-- is one local cell with its ensemble burn probability (the uncertainty) and the
-- mean hours until the fire reaches it. Rebuilt per run (delete + insert).

CREATE TABLE IF NOT EXISTS fire_spread_forecast (
  id         bigserial PRIMARY KEY,
  event_id   bigint REFERENCES fire_event(id) ON DELETE CASCADE,
  geom       geometry(Polygon, 4326) NOT NULL,  -- one local spread cell
  burn_prob  double precision NOT NULL,         -- 0..1 across the ensemble
  arrival_h  double precision,                  -- mean hours until ignition
  horizon_h  integer NOT NULL,                  -- forecast horizon (hours)
  run_time   timestamptz NOT NULL DEFAULT now(),
  params     jsonb
);
CREATE INDEX IF NOT EXISTS fire_spread_geom_gix ON fire_spread_forecast USING gist (geom);
CREATE INDEX IF NOT EXISTS fire_spread_event_idx ON fire_spread_forecast (event_id);
