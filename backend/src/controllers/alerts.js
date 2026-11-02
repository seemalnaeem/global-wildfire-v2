import { pool } from '../db/pool.js';

// Active alerts for the notifications panel, most severe and most recent first.
export async function listAlerts(req, res, next) {
  try {
    const limit = Math.min(Number(req.query.limit) || 50, 200);
    const { rows } = await pool.query(
      `SELECT a.id, a.kind, a.severity, a.event_id, a.title, a.message, a.value,
              a.updated_at, ST_X(a.centroid) AS lon, ST_Y(a.centroid) AS lat
         FROM alert a
        WHERE a.status = 'active'
        ORDER BY (a.severity = 'critical') DESC, a.value DESC NULLS LAST, a.updated_at DESC
        LIMIT $1`,
      [limit],
    );
    res.json({ alerts: rows });
  } catch (err) { next(err); }
}
