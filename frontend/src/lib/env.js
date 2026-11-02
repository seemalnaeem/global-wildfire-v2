// Service URLs from Vite env, never hardcoded.
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://172.18.1.60:3040';
export const TITILER_URL = import.meta.env.VITE_TITILER_URL || 'http://172.18.1.60:3042';
// Mapbox basemap token (public pk.* token). Empty means no basemap.
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';
