import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  INITIAL_VIEW, baseStyle, tileUrl,
  DETECTIONS_LAYER, EVENTS_LAYER, EVENTS_OUTLINE_LAYER, LANDCOVER_LAYER, NDVI_LAYER, DEM_LAYER,
  SMOKE_LAYER, RISK_LAYER, SPREAD_LAYER, LAYER_IDS, detectionPaint, eventFillPaint,
  eventLinePaint, riskPaint, spreadPaint,
} from './layers.js';
import { api } from '../lib/api.js';

// Renders land cover, fire detections, and fire events. Reacts to the time window
// and layer toggles, and reports the clicked event id upward. The map talks only
// to Express and TiTiler, never to external providers.
export default function MapView({ timeFrom, visible, order, focus, onSelectEvent }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const visibleRef = useRef(visible);
  useEffect(() => { visibleRef.current = visible; }, [visible]);

  useEffect(() => {
    const map = new maplibregl.Map({
      container: ref.current,
      style: baseStyle(),
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
    });
    mapRef.current = map;

    map.on('load', () => {
      // Raster overlays (land cover, DEM) are already in the base style, under the
      // fires. Apply their initial visibility, then add the fire layers on top.
      map.setLayoutProperty(LANDCOVER_LAYER, 'visibility', visible.landcover ? 'visible' : 'none');
      map.setLayoutProperty(NDVI_LAYER, 'visibility', visible.ndvi ? 'visible' : 'none');
      map.setLayoutProperty(DEM_LAYER, 'visibility', visible.dem ? 'visible' : 'none');
      map.setLayoutProperty(SMOKE_LAYER, 'visibility', visible.smoke ? 'visible' : 'none');

      // Fire-risk grid, under the fire layers.
      map.addSource(RISK_LAYER, { type: 'vector', tiles: [tileUrl(RISK_LAYER)], minzoom: 0, maxzoom: 14 });
      map.addLayer({ id: RISK_LAYER, type: 'fill', source: RISK_LAYER, 'source-layer': RISK_LAYER, paint: riskPaint, layout: { visibility: visible.risk ? 'visible' : 'none' } });

      // Fire-spread forecast cells (Phase 7), above risk, below the active fires.
      map.addSource(SPREAD_LAYER, { type: 'vector', tiles: [tileUrl(SPREAD_LAYER)], minzoom: 0, maxzoom: 14 });
      map.addLayer({ id: SPREAD_LAYER, type: 'fill', source: SPREAD_LAYER, 'source-layer': SPREAD_LAYER, paint: spreadPaint, layout: { visibility: visible.spread ? 'visible' : 'none' } });

      map.addSource(DETECTIONS_LAYER, { type: 'vector', tiles: [tileUrl(DETECTIONS_LAYER, { from: timeFrom })], minzoom: 0, maxzoom: 14 });
      map.addSource(EVENTS_LAYER, { type: 'vector', tiles: [tileUrl(EVENTS_LAYER, { from: timeFrom })], minzoom: 0, maxzoom: 14 });

      map.addLayer({ id: DETECTIONS_LAYER, type: 'circle', source: DETECTIONS_LAYER, 'source-layer': DETECTIONS_LAYER, paint: detectionPaint, layout: { visibility: visible.detections ? 'visible' : 'none' } });
      const evVis = { visibility: visible.events ? 'visible' : 'none' };
      map.addLayer({ id: EVENTS_LAYER, type: 'fill', source: EVENTS_LAYER, 'source-layer': EVENTS_LAYER, paint: eventFillPaint, layout: evVis });
      map.addLayer({ id: EVENTS_OUTLINE_LAYER, type: 'line', source: EVENTS_LAYER, 'source-layer': EVENTS_LAYER, paint: eventLinePaint, layout: evVis });

      map.on('click', EVENTS_LAYER, (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id != null) onSelectEvent(Number(id));
      });
      map.on('mouseenter', EVENTS_LAYER, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', EVENTS_LAYER, () => { map.getCanvas().style.cursor = ''; });

      // Spread cell click: show the burn probability and mean arrival time.
      map.on('click', SPREAD_LAYER, (e) => {
        const p = e.features?.[0]?.properties;
        if (!p) return;
        const style = 'font:13px system-ui,sans-serif;color:#e2e8f0;line-height:1.5';
        const arr = p.arrival_h == null ? 'n/a' : `~${Math.round(p.arrival_h)} h`;
        new maplibregl.Popup({ closeButton: true, maxWidth: '220px' })
          .setLngLat(e.lngLat)
          .setHTML(`<div style="${style}"><b style="color:#fb923c">Fire-spread forecast</b><br>`
            + `Burn probability: ${Math.round(p.burn_prob * 100)}%<br>`
            + `Time to arrival: ${arr}<br>`
            + `<span style="color:#94a3b8">next ${p.horizon_h} h</span></div>`)
          .addTo(map);
      });
      map.on('mouseenter', SPREAD_LAYER, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', SPREAD_LAYER, () => { map.getCanvas().style.cursor = ''; });

      // With the DEM layer on, clicking the map shows the elevation at that point.
      map.on('click', async (e) => {
        if (!visibleRef.current.dem) return;
        // Let event clicks open the details panel instead.
        if (map.queryRenderedFeatures(e.point, { layers: [EVENTS_LAYER] }).length) return;
        const { lng, lat } = e.lngLat;
        const style = 'font:13px system-ui,sans-serif;color:#e2e8f0;line-height:1.5';
        const popup = new maplibregl.Popup({ closeButton: true, maxWidth: '200px' })
          .setLngLat(e.lngLat)
          .setHTML(`<div style="${style}">Elevation: loading...</div>`)
          .addTo(map);
        try {
          const d = await api.getElevation(lng.toFixed(5), lat.toFixed(5));
          const val = d.elevation == null ? 'no data here'
            : d.elevation < 0 ? `${Math.abs(d.elevation)} m below sea level`
            : `${d.elevation} m`;
          popup.setHTML(`<div style="${style}"><b style="color:#38bdf8">Elevation</b><br>${val}<br>`
            + `<span style="color:#94a3b8">${lat.toFixed(3)}, ${lng.toFixed(3)}</span></div>`);
        } catch {
          popup.setHTML(`<div style="${style}">Elevation: unavailable</div>`);
        }
      });
    });

    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update tile sources when the time window changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    for (const layer of [DETECTIONS_LAYER, EVENTS_LAYER]) {
      const src = map.getSource(layer);
      if (src) src.setTiles([tileUrl(layer, { from: timeFrom })]);
    }
  }, [timeFrom]);

  // Reorder map layers when the panel order changes. order[0] = drawn on top, so
  // iterate bottom-to-top moving each layer to the top; the last moved ends on top.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || !order) return;
    [...order].reverse().forEach((key) => {
      (LAYER_IDS[key] || []).forEach((id) => {
        if (map.getLayer(id)) map.moveLayer(id);
      });
    });
  }, [order]);

  // Fly to a selected alert/location when `focus` changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus || focus.lon == null) return;
    map.flyTo({ center: [focus.lon, focus.lat], zoom: Math.max(map.getZoom(), 6) });
  }, [focus]);

  // Toggle layer visibility.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const on = (id, show) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none');
    on(RISK_LAYER, visible.risk);
    on(SPREAD_LAYER, visible.spread);
    on(LANDCOVER_LAYER, visible.landcover);
    on(NDVI_LAYER, visible.ndvi);
    on(DEM_LAYER, visible.dem);
    on(SMOKE_LAYER, visible.smoke);
    on(DETECTIONS_LAYER, visible.detections);
    on(EVENTS_LAYER, visible.events);
    on(EVENTS_OUTLINE_LAYER, visible.events);
  }, [visible]);

  return <div ref={ref} className="h-full w-full" />;
}
