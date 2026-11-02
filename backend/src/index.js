import { createApp } from './app.js';
import { pool } from './db/pool.js';

const port = process.env.PORT || 3040;
const app = createApp();

const server = app.listen(port, () => {
  console.log(`gwf-backend listening on ${port}`);
});

// Graceful shutdown: stop accepting connections, then close the DB pool, so the
// container exits cleanly on SIGTERM/SIGINT instead of being killed mid-request.
function shutdown(signal) {
  console.log(`${signal} received, shutting down`);
  server.close(() => {
    pool.end().finally(() => process.exit(0));
  });
  // Hard stop if connections do not drain in time.
  setTimeout(() => process.exit(1), 10_000).unref();
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
