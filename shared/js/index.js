// Shared JS helpers used across backend and frontend. One place, no duplication.

export * from './constants.js';

// Validate and coerce z/x/y tile coordinates. Throws on bad input.
export function parseTileCoords(z, x, y) {
  const zi = Number(z), xi = Number(x), yi = Number(y);
  if (![zi, xi, yi].every(Number.isInteger)) throw new Error('tile coords must be integers');
  if (zi < 0 || zi > 24) throw new Error('zoom out of range');
  const max = 2 ** zi;
  if (xi < 0 || xi >= max || yi < 0 || yi >= max) throw new Error('tile x/y out of range');
  return { z: zi, x: xi, y: yi };
}

// Build a MapLibre-style tile template for a backend MVT layer.
export function mvtTemplate(backendUrl, layer) {
  return `${backendUrl}/tiles/${layer}/{z}/{x}/{y}.mvt`;
}

// Build a TiTiler COG tile template. TiTiler needs the TileMatrixSet in the path.
export function cogTemplate(titilerUrl, cogPath, params = {}, matrixSet = 'WebMercatorQuad') {
  const qs = new URLSearchParams({ url: cogPath, ...params }).toString();
  return `${titilerUrl}/cog/tiles/${matrixSet}/{z}/{x}/{y}.png?${qs}`;
}
