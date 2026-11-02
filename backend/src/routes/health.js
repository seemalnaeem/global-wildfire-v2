import { Router } from 'express';
import { pool } from '../db/pool.js';

export const health = Router();

// Liveness: process is up (no dependencies checked). For orchestrators.
health.get('/live', (req, res) => res.json({ status: 'ok' }));

// Readiness: the service can serve requests (DB reachable).
health.get('/', async (req, res, next) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', service: 'backend' });
  } catch (err) {
    err.status = 503;
    err.code = 'db_unavailable';
    next(err);
  }
});
