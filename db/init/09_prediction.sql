-- Phase 6: fire-risk model output. One risk value per (cell, prediction_time).

CREATE TABLE IF NOT EXISTS grid_prediction (
  cell_id         bigint REFERENCES grid_cell(id) ON DELETE CASCADE,
  prediction_time timestamptz NOT NULL,
  risk            double precision NOT NULL,  -- calibrated probability 0..1
  model_version   text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (cell_id, prediction_time, model_version)
);
