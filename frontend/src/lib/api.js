import { BACKEND_URL } from './env.js';

// Thin fetch wrapper. Reuse this, do not scatter fetch calls.
async function get(path) {
  const res = await fetch(`${BACKEND_URL}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  health: () => get('/health'),
  listEvents: (limit = 50) => get(`/events?limit=${limit}`),
  getEvent: (id) => get(`/events/${id}`),
  getElevation: (lon, lat) => get(`/elevation?lon=${lon}&lat=${lat}`),
  listAlerts: (limit = 50) => get(`/alerts?limit=${limit}`),
  getStatus: () => get('/status'),
};
