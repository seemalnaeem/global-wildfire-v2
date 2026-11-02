import { pool } from '../db/pool.js';

const GEO_URL = process.env.GEOPROCESSING_URL || 'http://geoprocessing:3041';

const EVENT_SELECT = `
  SELECT e.id, ST_X(e.centroid) AS lon, ST_Y(e.centroid) AS lat,
         e.first_detected, e.last_detected, e.detection_count, e.max_frp, e.frp_sum,
         e.status, e.category,
         c.elevation, c.slope, c.aspect, c.landcover_code, c.landcover_label,
         c.enriched_at,
         w.temp_c, w.rh, w.dew_point_c, w.wind_speed_kmh, w.wind_dir_deg,
         w.wind_gust_kmh, w.precip_mm, w.pressure_hpa, w.weather_time, w.fetched_at,
         w.soil_moist_surface, w.soil_moist_root, w.soil_temp_c, w.vpd_kpa,
         v.ndvi, v.ndmi, v.nbr, v.obs_date, v.fetched_at AS veg_fetched_at
    FROM fire_event e
    LEFT JOIN fire_event_context c ON c.event_id = e.id
    LEFT JOIN fire_event_weather w ON w.event_id = e.id
    LEFT JOIN fire_event_vegetation v ON v.event_id = e.id
   WHERE e.id = $1`;

// Weather refetched hourly; vegetation weekly (clear satellite scenes are rare).
const WEATHER_TTL_MS = 60 * 60 * 1000;
const VEG_TTL_MS = 7 * 24 * 60 * 60 * 1000;

// Recent fire events, newest activity first. Optional ?limit.
export async function listEvents(req, res, next) {
  try {
    const limit = Math.min(Number(req.query.limit) || 50, 500);
    const { rows } = await pool.query(
      `SELECT e.id, ST_X(e.centroid) AS lon, ST_Y(e.centroid) AS lat,
              e.first_detected, e.last_detected, e.detection_count, e.max_frp, e.status,
              c.landcover_label
         FROM fire_event e LEFT JOIN fire_event_context c ON c.event_id = e.id
        ORDER BY e.last_detected DESC LIMIT $1`,
      [limit],
    );
    res.json({ events: rows });
  } catch (err) { next(err); }
}

// One event plus its detections, for the details panel.
export async function getEvent(req, res, next) {
  try {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
      return res.status(400).json({ error: { code: 'bad_id', message: 'id must be an integer' } });
    }
    let ev = await pool.query(EVENT_SELECT, [id]);
    if (!ev.rows[0]) {
      return res.status(404).json({ error: { code: 'not_found', message: 'event not found' } });
    }
    // Lazy enrichment: fill terrain and land cover on first open, then re-read.
    if (!ev.rows[0].enriched_at) {
      try {
        await fetch(`${GEO_URL}/events/${id}/enrich`, { method: 'POST' });
        ev = await pool.query(EVENT_SELECT, [id]);
      } catch { /* enrichment is best effort, return what we have */ }
    }
    // Lazy weather: fetch current conditions if missing or stale.
    const fetchedAt = ev.rows[0].fetched_at ? new Date(ev.rows[0].fetched_at).getTime() : 0;
    if (Date.now() - fetchedAt > WEATHER_TTL_MS) {
      try {
        await fetch(`${GEO_URL}/events/${id}/enrich-weather`, { method: 'POST' });
        ev = await pool.query(EVENT_SELECT, [id]);
      } catch { /* weather is best effort */ }
    }
    // Lazy vegetation: fetch Sentinel-2 indices if missing or stale.
    const vegAt = ev.rows[0].veg_fetched_at ? new Date(ev.rows[0].veg_fetched_at).getTime() : 0;
    if (Date.now() - vegAt > VEG_TTL_MS) {
      try {
        await fetch(`${GEO_URL}/events/${id}/enrich-vegetation`, { method: 'POST' });
        ev = await pool.query(EVENT_SELECT, [id]);
      } catch { /* vegetation is best effort */ }
    }
    const det = await pool.query(
      `SELECT id, lon, lat, acq_time, satellite, sensor, confidence, frp, daynight
         FROM fire_detection WHERE event_id = $1 ORDER BY acq_time DESC LIMIT 500`,
      [id],
    );
    res.json({ event: ev.rows[0], detections: det.rows });
  } catch (err) { next(err); }
}
