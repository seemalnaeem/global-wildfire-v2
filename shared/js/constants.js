// Shared constants for all JS services. Import, do not redefine.

export const SRID_STORAGE = 4326; // lon/lat WGS84
export const SRID_TILE = 3857; // web mercator
export const TILE_EXTENT = 4096; // MVT tile extent
export const TILE_BUFFER = 64; // MVT tile buffer in pixels

export const PORTS = {
  db: 5440,
  backend: 3040,
  geoprocessing: 3041,
  titiler: 3042,
  frontend: 5180,
};
