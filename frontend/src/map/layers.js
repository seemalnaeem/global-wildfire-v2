import { BACKEND_URL, TITILER_URL, MAPBOX_TOKEN } from '../lib/env.js';

// Global view by default. Live fire monitoring spans the whole world.
export const INITIAL_VIEW = { center: [30, 20], zoom: 1.6 };

// Base style. Uses a Mapbox raster basemap when a token is set, else a dark fill.
// MapLibre renders the Mapbox tiles, the architecture stays MapLibre + Vite.
// Raster overlays (land cover, DEM). Part of the base style like the basemap so
// they render reliably. Initial visibility off, the toggles turn them on.
function overlaySourcesAndLayers() {
  const sources = {
    [LANDCOVER_LAYER]: { type: 'raster', tiles: [landcoverTileUrl()], tileSize: 256 },
    [NDVI_LAYER]: { type: 'raster', tiles: [ndviTileUrl()], tileSize: 256, maxzoom: 9 },
    [DEM_LAYER]: { type: 'raster', tiles: [demTileUrl()], tileSize: 256, maxzoom: 13 },
    [SMOKE_LAYER]: { type: 'raster', tiles: [smokeTileUrl()], tileSize: 256, maxzoom: 6 },
  };
  const hidden = { visibility: 'none' };
  const layers = [
    { id: LANDCOVER_LAYER, type: 'raster', source: LANDCOVER_LAYER,
      paint: { 'raster-opacity': 0.75 }, layout: hidden },
    { id: NDVI_LAYER, type: 'raster', source: NDVI_LAYER,
      paint: { 'raster-opacity': 0.8 }, layout: hidden },
    // SRTM 30 m, only from regional zoom in (too many tiles to serve globally).
    { id: DEM_LAYER, type: 'raster', source: DEM_LAYER, minzoom: DEM_MINZOOM,
      paint: { 'raster-opacity': 0.85 }, layout: hidden },
    // Smoke / aerosol (over the fires), semi-transparent so fires stay visible.
    { id: SMOKE_LAYER, type: 'raster', source: SMOKE_LAYER,
      paint: { 'raster-opacity': 0.7 }, layout: hidden },
  ];
  return { sources, layers };
}

export function baseStyle(mapboxStyle = 'dark-v11') {
  const overlay = overlaySourcesAndLayers();

  if (MAPBOX_TOKEN) {
    const url = `https://api.mapbox.com/styles/v1/mapbox/${mapboxStyle}/tiles/256/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`;
    return {
      version: 8,
      sources: {
        basemap: { type: 'raster', tiles: [url], tileSize: 256,
          attribution: '(c) Mapbox (c) OpenStreetMap' },
        ...overlay.sources,
      },
      // Dark fill under the basemap so the map still reads if tiles are blocked.
      layers: [
        { id: 'bg', type: 'background', paint: { 'background-color': '#0b1020' } },
        { id: 'basemap', type: 'raster', source: 'basemap' },
        ...overlay.layers,
      ],
    };
  }
  return {
    version: 8,
    sources: overlay.sources,
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#0b1020' } },
      ...overlay.layers,
    ],
  };
}

// Backend MVT tile URL for a layer, with an optional time window (?from=ISO).
export function tileUrl(layer, { from } = {}) {
  const base = `${BACKEND_URL}/tiles/${layer}/{z}/{x}/{y}.mvt`;
  return from ? `${base}?from=${encodeURIComponent(from)}` : base;
}

// Phase 2 layers: raw detections and grouped fire events.
export const DETECTIONS_LAYER = 'fire_detections';
export const EVENTS_LAYER = 'fire_events';           // fill of the event footprint
export const EVENTS_OUTLINE_LAYER = 'fire_events_outline'; // its red outline
export const LANDCOVER_LAYER = 'landcover';
export const RISK_LAYER = 'fire_risk';  // Phase 6 model: predicted next-24h fire risk
export const NDVI_LAYER = 'ndvi';  // MODIS NDVI (vegetation greenness) from NASA GIBS

// Fire-risk fill, green (low) to red (high) by the cell risk value.
export const riskPaint = {
  'fill-color': [
    'interpolate', ['linear'], ['get', 'risk'],
    0, '#1a9850', 0.15, '#a6d96a', 0.3, '#fee08b', 0.5, '#fdae61', 0.75, '#d73027',
  ],
  'fill-opacity': 0.55,
};
export const RISK_GRADIENT = 'linear-gradient(to right, #1a9850, #a6d96a, #fee08b, #fdae61, #d73027)';

// Phase 7: fire-spread forecast. Local cells shaded by ensemble burn probability
// (yellow = low chance of burning in the next 24h, dark red = near certain).
export const SPREAD_LAYER = 'fire_spread';
export const spreadPaint = {
  'fill-color': [
    'interpolate', ['linear'], ['get', 'burn_prob'],
    0.05, '#ffffb2', 0.25, '#fecc5c', 0.5, '#fd8d3c', 0.75, '#f03b20', 1, '#bd0026',
  ],
  'fill-opacity': 0.5,
};
export const SPREAD_GRADIENT = 'linear-gradient(to right, #ffffb2, #fecc5c, #fd8d3c, #f03b20, #bd0026)';
export const DEM_LAYER = 'dem';    // SRTM GL1 30 m mosaic

// NASA GIBS MODIS Terra NDVI (8 day), colored greenness, public, no auth, global.
// 'default' time resolves to the latest available composite. Level 9 max (~250 m).
export function ndviTileUrl() {
  return 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_NDVI_8Day/default/default/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png';
}
export const NDVI_GRADIENT = 'linear-gradient(to right, #8c510a, #d8b365, #f6e8c3, #7fbf7b, #1a9850)';
export const DEM_MINZOOM = 6;      // gate: 30 m tiles are too many to serve globally

// Phase 8: smoke / air quality. Aerosol Optical Depth (a smoke + haze proxy) from
// NASA GIBS (MODIS Combined, public, no auth, global). CAMS (PM2.5 dispersion) can
// drop in later by setting VITE_SMOKE_TILE_URL to a CAMS WMS/WMTS template.
export const SMOKE_LAYER = 'smoke';
export function smokeTileUrl() {
  return import.meta.env.VITE_SMOKE_TILE_URL
    || 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Combined_Value_Added_AOD/default/default/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png';
}
export const SMOKE_GRADIENT = 'linear-gradient(to right, #ffffb2, #fecc5c, #fd8d3c, #e31a1c, #800026)';

// Digital elevation model (SRTM GL1 30 m), served by TiTiler mosaic with a terrain
// colormap. Rescale spans 0..6000 m, sea level and below map to the low (blue) end.
export const DEM_RESCALE = [0, 6000];
export function demTileUrl() {
  const [lo, hi] = DEM_RESCALE;
  return `${TITILER_URL}/mosaicjson/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=/data/srtm_mosaic.json&rescale=${lo},${hi}&colormap_name=terrain`;
}

// ESA WorldCover land cover, served by TiTiler from a downsampled global COG.
// Palette carries the official class colors, no colormap param needed. Enrichment
// still samples full 10 m resolution separately.
export function landcoverTileUrl() {
  return `${TITILER_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=/data/worldcover_global.cog.tif`;
}

// WorldCover classes for the legend (code, label, hex).
export const LANDCOVER_LEGEND = [
  [10, 'Tree cover', '#006400'], [20, 'Shrubland', '#ffbb22'],
  [30, 'Grassland', '#ffff4c'], [40, 'Cropland', '#f096ff'],
  [50, 'Built-up', '#fa0000'], [60, 'Bare / sparse', '#b4b4b4'],
  [70, 'Snow and ice', '#f0f0f0'], [80, 'Water', '#0064c8'],
  [90, 'Herb. wetland', '#0096a0'], [95, 'Mangroves', '#00cf75'],
  [100, 'Moss / lichen', '#fae6a0'],
];

// MapLibre paint for detection points, colored by VIIRS confidence.
export const detectionPaint = {
  'circle-radius': 3,
  'circle-color': [
    'match', ['get', 'confidence'],
    'h', '#dc2626', 'n', '#f97316', 'l', '#facc15',
    '#f97316',
  ],
  'circle-opacity': 0.85,
};

// Event footprint: translucent red fill with a solid red outline.
export const eventFillPaint = {
  'fill-color': '#dc2626',
  'fill-opacity': 0.25,
};
export const eventLinePaint = {
  'line-color': '#ef4444',
  'line-width': 1.5,
};

// Map each layer toggle key to its MapLibre layer id(s), used for drag reordering.
// The order of ids within a key sets their relative stack (later = on top).
export const LAYER_IDS = {
  events: [EVENTS_LAYER, EVENTS_OUTLINE_LAYER],
  detections: [DETECTIONS_LAYER],
  spread: [SPREAD_LAYER],
  risk: [RISK_LAYER],
  smoke: [SMOKE_LAYER],
  ndvi: [NDVI_LAYER],
  landcover: [LANDCOVER_LAYER],
  dem: [DEM_LAYER],
};

// Default stack, top of the list = drawn on top of the map.
export const DEFAULT_LAYER_ORDER = [
  'events', 'detections', 'spread', 'risk', 'smoke', 'ndvi', 'landcover', 'dem',
];
