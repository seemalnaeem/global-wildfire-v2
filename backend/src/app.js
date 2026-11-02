import express from 'express';
import helmet from 'helmet';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import { requestLog } from './middleware/request-log.js';
import { corsAllow } from './middleware/cors.js';
import { errorHandler } from './middleware/error.js';
import { health } from './routes/health.js';
import { tiles } from './routes/tiles.js';
import { events } from './routes/events.js';
import { risk } from './routes/risk.js';
import { alerts } from './routes/alerts.js';
import { status } from './routes/status.js';
import { getElevation } from './controllers/terrain.js';

// Generous per-IP limit for the JSON API. Tiles and health are excluded (the map
// pulls many tiles, probes hit health often), so normal use is never throttled.
const apiLimiter = rateLimit({
  windowMs: 60_000, max: 600, standardHeaders: true, legacyHeaders: false,
  message: { error: { code: 'rate_limited', message: 'Too many requests, slow down.' } },
});

// Middleware order: security, compress, log, cors, parse, route, error.
export function createApp() {
  const app = express();
  // Security headers. No CSP (this serves JSON/MVT, not HTML) and cross-origin
  // resource policy so the separate-origin frontend can read tiles and API.
  app.use(helmet({
    contentSecurityPolicy: false,
    crossOriginResourcePolicy: { policy: 'cross-origin' },
    crossOriginEmbedderPolicy: false,
  }));
  app.use(compression());           // gzip JSON and MVT responses
  app.use(requestLog);
  app.use(corsAllow);
  app.use(express.json({ limit: '1mb' }));
  app.use('/health', health);
  app.use('/tiles', tiles);
  app.use('/events', apiLimiter, events);
  app.use('/risk', apiLimiter, risk);
  app.use('/alerts', apiLimiter, alerts);
  app.use('/status', apiLimiter, status);
  app.get('/elevation', apiLimiter, getElevation);
  app.use(errorHandler);
  return app;
}
