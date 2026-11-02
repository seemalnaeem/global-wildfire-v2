-- Phase 3: environmental context for each fire event.
-- Terrain from local DEM COGs, land cover from ESA WorldCover.

CREATE TABLE IF NOT EXISTS fire_event_context (
  event_id        bigint PRIMARY KEY REFERENCES fire_event(id) ON DELETE CASCADE,
  elevation       double precision,   -- meters, from elevation DEM
  slope           double precision,   -- degrees, from slope raster
  aspect          double precision,   -- degrees 0..360, from derived aspect
  landcover_code  smallint,           -- ESA WorldCover class code
  landcover_label text,               -- human label for the code
  enriched_at     timestamptz NOT NULL DEFAULT now()
);
