import pg from 'pg';

// Single shared pool for the whole backend. Never open ad hoc clients.
export const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
});

pool.on('error', (err) => {
  console.error('pg pool error', err.message);
});
