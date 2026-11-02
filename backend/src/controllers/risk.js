import { pool } from '../db/pool.js';

const MODEL_VERSION = 'm1';

// Metadata for the fire-risk layer: when the current forecast was issued and how
// many cells it covers. The map uses this to label the risk legend so a forecast
// (forward looking) is not mistaken for the past-window detection filter.
export async function getRiskMeta(req, res, next) {
  try {
    const { rows } = await pool.query(
      `SELECT max(prediction_time) AS issued_at,
              count(*) FILTER (
                WHERE prediction_time = (
                  SELECT max(prediction_time) FROM grid_prediction WHERE model_version = $1
                )
              ) AS cells
         FROM grid_prediction WHERE model_version = $1`,
      [MODEL_VERSION],
    );
    res.json({
      model_version: MODEL_VERSION,
      issued_at: rows[0].issued_at,
      cells: Number(rows[0].cells),
    });
  } catch (err) { next(err); }
}
