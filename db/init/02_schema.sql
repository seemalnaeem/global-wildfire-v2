-- Baseline schema. Store geometry in EPSG:4326, index with GiST.
-- Example wildfire feature table. Replace/extend as real sources land.

CREATE TABLE IF NOT EXISTS fire_incidents (
  id          bigserial PRIMARY KEY,
  name        text,
  observed_at timestamptz,
  confidence  double precision,
  geom        geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS fire_incidents_geom_gix
  ON fire_incidents USING gist (geom);

CREATE TABLE IF NOT EXISTS risk_zones (
  id       bigserial PRIMARY KEY,
  name     text,
  severity smallint,
  geom     geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS risk_zones_geom_gix
  ON risk_zones USING gist (geom);
