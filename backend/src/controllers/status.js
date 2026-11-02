import { pool } from '../db/pool.js';

// Freshness summary for the status bar: when the fire data and forecasts were last
// updated, plus current counts. data_updated is the latest satellite observation;
// server_now lets the client show a live "x ago".
export async function getStatus(req, res, next) {
  try {
    const { rows } = await pool.query(
      `SELECT
         (SELECT max(acq_time) FROM fire_detection)                              AS data_updated,
         (SELECT count(*) FROM fire_detection)                                   AS detections,
         (SELECT count(*) FROM fire_event WHERE category = 'wildfire')           AS wildfires,
         (SELECT max(prediction_time) FROM grid_prediction WHERE model_version='m1') AS forecast_issued,
         (SELECT count(*) FROM alert WHERE status = 'active')                    AS alerts_active,
         now()                                                                   AS server_now`,
    );
    const r = rows[0];
    res.json({
      data_updated: r.data_updated,
      detections: Number(r.detections),
      wildfires: Number(r.wildfires),
      forecast_issued: r.forecast_issued,
      alerts_active: Number(r.alerts_active),
      server_now: r.server_now,
    });
  } catch (err) { next(err); }
}
