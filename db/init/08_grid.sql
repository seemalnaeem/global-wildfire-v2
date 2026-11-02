-- Phase 5: historical fire dataset on a common grid.
-- grid_cell holds the study-area cells with static features. grid_sample holds one
-- training row per (cell, prediction_time): features known at prediction_time and a
-- label for the next window. Features are past/present, the label is future: this
-- separation is the anti-leakage rule.

CREATE TABLE IF NOT EXISTS grid_cell (
  id             bigserial PRIMARY KEY,
  geom           geometry(Polygon, 4326) NOT NULL,
  centroid       geometry(Point, 4326) NOT NULL,
  elevation      double precision,   -- static terrain
  slope          double precision,
  aspect         double precision,
  landcover_code smallint,           -- static land cover (WorldCover)
  landcover_label text,
  veg_greenness  smallint            -- MODIS-NDVI-derived greenness index (0..100)
);
CREATE INDEX IF NOT EXISTS grid_cell_geom_gix ON grid_cell USING gist (geom);
CREATE INDEX IF NOT EXISTS grid_cell_centroid_gix ON grid_cell USING gist (centroid);

CREATE TABLE IF NOT EXISTS grid_sample (
  id              bigserial PRIMARY KEY,
  cell_id         bigint REFERENCES grid_cell(id) ON DELETE CASCADE,
  prediction_time timestamptz NOT NULL,     -- feature cutoff, label is after this
  -- Features known at prediction_time (fire history in the cell, strictly past).
  det_past_24h    integer,
  det_past_48h    integer,
  det_past_72h    integer,
  frp_past_24h    double precision,
  had_fire        boolean,                   -- any detection at or before cutoff
  neigh_det_24h   integer,                   -- past-24h detections in nearby cells
  -- Environmental conditions observed AT the cutoff (not future).
  temp_c          double precision,
  rh              double precision,
  wind_speed_kmh  double precision,
  precip_mm       double precision,
  vpd_kpa         double precision,
  soil_moist_surface double precision,
  -- Label: did a new fire occur in the cell in (prediction_time, +24h]? (future)
  label_fire_next_24h boolean,
  dataset_version text NOT NULL,
  UNIQUE (cell_id, prediction_time, dataset_version)
);
CREATE INDEX IF NOT EXISTS grid_sample_label_idx
  ON grid_sample (dataset_version, label_fire_next_24h);
