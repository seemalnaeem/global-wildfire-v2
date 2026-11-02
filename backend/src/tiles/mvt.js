import { pool } from '../db/pool.js';
import { parseTileCoords } from '#shared';

// Whitelist of layer name -> table, properties, geometry column, optional time
// column. Prevents arbitrary table access and keeps queries parameterized.
const LAYERS = {
  fire_incidents: { table: 'fire_incidents', geom: 'geom', props: 'name, observed_at, confidence' },
  risk_zones: { table: 'risk_zones', geom: 'geom', props: 'name, severity' },
  // Only wildfire events (and their detections) are shown on the map. Other
  // thermal anomalies (flares, industrial, agricultural) are stored but filtered.
  fire_detections: {
    table: 'fire_detection', geom: 'geom', time: 'acq_time',
    props: 'acq_time, satellite, confidence, frp, daynight, event_id',
    where: "event_id IN (SELECT id FROM fire_event WHERE category = 'wildfire')",
  },
  fire_events: {
    // Rendered as the event footprint (buffered convex hull), not a point.
    table: 'fire_event', geom: 'boundary', time: 'last_detected',
    props: 'first_detected, last_detected, detection_count, max_frp, frp_sum, status, category',
    where: "category = 'wildfire'",
  },
  // Phase 6 model output: grid cells colored by predicted fire risk (latest run).
  fire_risk: {
    table: "grid_cell JOIN grid_prediction p ON p.cell_id = grid_cell.id"
      + " AND p.model_version = 'm1'"
      + " AND p.prediction_time = (SELECT max(prediction_time) FROM grid_prediction WHERE model_version = 'm1')",
    geom: 'geom', props: 'risk',
  },
  // Phase 7 model output: local cells colored by ensemble spread (burn) probability.
  fire_spread: {
    table: 'fire_spread_forecast', geom: 'geom',
    props: 'event_id, burn_prob, arrival_h, horizon_h',
  },
};

export async function getMvt(req, res, next) {
  try {
    const layer = LAYERS[req.params.layer];
    if (!layer) {
      const e = new Error('unknown layer');
      e.status = 404; e.code = 'unknown_layer';
      throw e;
    }
    const coords = parseTileCoords(req.params.z, req.params.x, req.params.y);

    // Optional time window. Applied only when the layer has a time column.
    const params = [coords.z, coords.x, coords.y, req.params.layer];
    let timeFilter = '';
    if (layer.time) {
      if (req.query.from) { params.push(req.query.from); timeFilter += ` AND ${layer.time} >= $${params.length}::timestamptz`; }
      if (req.query.to) { params.push(req.query.to); timeFilter += ` AND ${layer.time} <= $${params.length}::timestamptz`; }
    }

    const g = layer.geom;
    const extra = layer.where ? ` AND ${layer.where}` : '';
    const sql = `
      WITH bounds AS (SELECT ST_TileEnvelope($1, $2, $3) AS env)
      SELECT ST_AsMVT(t, $4) AS mvt FROM (
        SELECT id, ${layer.props},
               ST_AsMVTGeom(ST_Transform(${g}, 3857), bounds.env) AS geom
        FROM ${layer.table}, bounds
        WHERE ST_Transform(${g}, 3857) && bounds.env${timeFilter}${extra}
      ) t`;
    const { rows } = await pool.query(sql, params);

    res.setHeader('Content-Type', 'application/x-protobuf');
    res.setHeader('Cache-Control', 'public, max-age=60');
    res.send(rows[0]?.mvt || Buffer.alloc(0));
  } catch (err) {
    if (!err.status) err.status = 400;
    next(err);
  }
}
