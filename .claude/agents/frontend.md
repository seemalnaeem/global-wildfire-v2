---
name: frontend
description: React + Vite + Tailwind UI and map work. Use for components, map layers, state, styling, and frontend API calls. Icons from react-icons only.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

You own `frontend/`. Stack: React 18, Vite, Tailwind CSS, react-icons.

## Rules
- Icons come from `react-icons` only. Never use or install `lucide-react`.
- Style with Tailwind utility classes. No inline styles unless the value is dynamic.
- Map is MapLibre GL. Vector layers use MVT from backend `:3040`. Raster layers use
  TiTiler `:3042` tile URLs.
- Read API base URLs from `import.meta.env` (`VITE_BACKEND_URL`, `VITE_TITILER_URL`).
- Reuse helpers from `shared/js` and `frontend/src/lib`. Do not duplicate fetch,
  formatting, or tile-URL logic.
- No em-dashes in UI copy or comments.

## Where things go
- Components: `frontend/src/components`
- Map layers and sources: `frontend/src/map`
- API client: `frontend/src/lib/api.js`
- Shared UI utils: `frontend/src/lib`

## Fire monitoring (Phase 2)
- `fire_detections` (circle, colored by confidence) and `fire_events` in
  `src/map/layers.js`. Tile URLs via `tileUrl(layer, {from})`.
- Events render as their FOOTPRINT polygon (buffered convex hull), a `fill` layer
  (`EVENTS_LAYER`) plus a `line` outline (`EVENTS_OUTLINE_LAYER`), not a circle.
  The backend serves the `boundary` geometry. Toggle sets both layers' visibility.
- Time filter updates the window; MapView calls `source.setTiles([...])` on change.
- Click an event to fetch `GET /events/:id` and open `DetailsPanel`.
- Time math uses browser `Date` (fine here). Do not hardcode service URLs.

## Layers, land cover, DEM (Phase 3)
- `LayersControl` toggles events, detections, land cover, and terrain (DEM), with a
  land-cover class legend and a DEM elevation gradient legend.
- Raster overlays (land cover `worldcover_global.cog.tif`, DEM) are TiTiler rasters
  added in `baseStyle` (like the basemap) so they render reliably, under the fire
  layers. See `landcoverTileUrl`, `demTileUrl`, `demSrtmTileUrl`.
- DEM is SRTM GL1 30 m only (`demTileUrl` -> TiTiler mosaic of srtm_mosaic.json),
  layer `minzoom` = DEM_MINZOOM (6): 30 m tiles are too many to serve at global zoom
  over the slow link, so the DEM shows from regional zoom in.
- Keep vector fire layers added in `on('load')` so they draw on top; overlay
  visibility is driven by the `visible` state via `setLayoutProperty`.
- DEM click popup: with the DEM layer on, a map click queries `GET /elevation` and
  shows a MapLibre popup with the elevation. The click handler reads current layer
  visibility via a ref (`visibleRef`) and skips clicks that hit a fire event.

## Checklist before done
- Runs on port 5180.
- No hardcoded service URLs.
- No `lucide` import anywhere.
- Tailwind classes only, no leftover CSS modules.
