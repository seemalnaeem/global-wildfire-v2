const TITILER_URL = process.env.TITILER_URL || 'http://titiler:3042';

const finite = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

// Query the SRTM mosaic (30 m, global) for the value at a point.
async function mosaicValue(mosaic, lon, lat) {
  const url = `${TITILER_URL}/mosaicjson/point/${lon},${lat}?url=${encodeURIComponent(mosaic)}`;
  const res = await fetch(url);
  if (!res.ok) return null;
  const data = await res.json();
  const asset = (data?.assets || []).find((a) => finite(a?.values?.[0]) !== null);
  return asset ? finite(asset.values[0]) : null;
}

// GET /elevation?lon=&lat= -> elevation in meters at the point.
// Prefers the precise regional DEM, falls back to the global DEM.
export async function getElevation(req, res, next) {
  try {
    const lon = Number(req.query.lon);
    const lat = Number(req.query.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat) || Math.abs(lon) > 180 || Math.abs(lat) > 90) {
      return res.status(400).json({ error: { code: 'bad_coords', message: 'lon/lat out of range' } });
    }
    // SRTM GL1 30 m everywhere it covers (60N..56S). Null outside that band.
    const elevation = await mosaicValue('/data/srtm_mosaic.json', lon, lat);
    res.json({ lon, lat, elevation: elevation === null ? null : Math.round(elevation), source: 'srtm' });
  } catch (err) { next(err); }
}
