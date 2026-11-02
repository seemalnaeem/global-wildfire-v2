import { useEffect, useRef, useState } from 'react';
import { FaLayerGroup, FaEye, FaEyeSlash, FaGripVertical } from 'react-icons/fa6';
import { LANDCOVER_LEGEND, DEM_RESCALE, NDVI_GRADIENT, RISK_GRADIENT, SPREAD_GRADIENT, SMOKE_GRADIENT } from '../map/layers.js';
import { BACKEND_URL } from '../lib/env.js';

// Short UTC stamp for the forecast issue-time, e.g. "30 Sep 09:26 UTC".
function fmtIssued(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    timeZone: 'UTC', hour12: false,
  }) + ' UTC';
}

const LABELS = {
  events: 'Fire events',
  detections: 'Detections',
  risk: 'Fire risk (next 24h)',
  spread: 'Fire spread (next 24h)',
  landcover: 'Land cover',
  ndvi: 'Vegetation (NDVI)',
  dem: 'Terrain (DEM)',
  smoke: 'Smoke / aerosol',
};

// Approximates the terrain colormap: low green, mid tan/brown, high white.
const DEM_GRADIENT = 'linear-gradient(to right, #2e8b57, #a9ba5a, #d9c27e, #a6763c, #ffffff)';

// Layer panel: drag rows to reorder draw order (top = on top of the map), and use the
// eye to show or hide. Each layer's legend/info appears right under its own row.
export default function LayersControl({ visible, order, onToggle, onReorder }) {
  const [riskMeta, setRiskMeta] = useState(null);
  const [overIdx, setOverIdx] = useState(null);
  const dragIdx = useRef(null);

  // Load the forecast issue-time when the risk layer is turned on.
  useEffect(() => {
    if (!visible.risk || riskMeta) return;
    let ok = true;
    fetch(`${BACKEND_URL}/risk/meta`)
      .then((r) => r.json())
      .then((m) => { if (ok) setRiskMeta(m); })
      .catch(() => {});
    return () => { ok = false; };
  }, [visible.risk, riskMeta]);

  function drop(toIdx) {
    const from = dragIdx.current;
    dragIdx.current = null;
    setOverIdx(null);
    if (from == null || from === toIdx) return;
    const next = [...order];
    const [moved] = next.splice(from, 1);
    next.splice(toIdx, 0, moved);
    onReorder(next);
  }

  // Each layer's own legend/info, rendered directly under its row when switched on.
  function legendFor(key) {
    switch (key) {
      case 'landcover':
        return (
          <>
            <ul className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-sm text-white">
              {LANDCOVER_LEGEND.map(([code, label, hex]) => (
                <li key={code} className="flex items-center gap-1">
                  <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: hex }} />
                  {label}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-white">Source: ESA WorldCover, 10 m, 2020 (static).</p>
          </>
        );
      case 'risk':
        return (
          <>
            <div className="h-2 w-full rounded" style={{ background: RISK_GRADIENT }} />
            <div className="mt-0.5 flex justify-between text-sm text-white">
              <span>low</span><span>high</span>
            </div>
            <p className="mt-1 break-words text-xs text-white">
              Issued {fmtIssued(riskMeta?.issued_at) || '...'} UTC. A 24h forecast,
              separate from the 24/48/72h detection filter above.
            </p>
          </>
        );
      case 'spread':
        return (
          <>
            <div className="h-2 w-full rounded" style={{ background: SPREAD_GRADIENT }} />
            <div className="mt-0.5 flex justify-between text-sm text-white">
              <span>low</span><span>high</span>
            </div>
            <p className="mt-1 break-words text-xs text-white">
              A 24h forecast from active fires (wind, fuel, dryness), separate from the
              time filter above. Click a cell for details.
            </p>
          </>
        );
      case 'ndvi':
        return (
          <>
            <div className="h-2 w-full rounded" style={{ background: NDVI_GRADIENT }} />
            <div className="mt-0.5 flex justify-between text-sm text-white">
              <span>sparse / dry</span><span>dense</span>
            </div>
            <p className="mt-1 text-xs text-white">Source: NASA GIBS MODIS Terra, 8-day composite (latest).</p>
          </>
        );
      case 'dem':
        return (
          <>
            <div className="h-2 w-full rounded" style={{ background: DEM_GRADIENT }} />
            <div className="mt-0.5 flex justify-between text-sm text-white">
              <span>{DEM_RESCALE[0]} m</span><span>{DEM_RESCALE[1]}+ m</span>
            </div>
            <p className="mt-1 text-xs text-white">Source: SRTM GL1, 30 m (NASA/USGS, static).</p>
          </>
        );
      case 'smoke':
        return (
          <>
            <div className="h-2 w-full rounded" style={{ background: SMOKE_GRADIENT }} />
            <div className="mt-0.5 flex justify-between text-sm text-white">
              <span>clear</span><span>smoky</span>
            </div>
            <p className="mt-1 break-words text-xs text-white">
              Source: NASA GIBS MODIS, daily AOD (latest). Patchy by nature: shown only
              where a clear-sky retrieval exists (gaps = cloud / no overpass).
            </p>
          </>
        );
      default:
        return null;
    }
  }

  return (
    <div className="scrollbar-thin max-h-[85vh] w-72 overflow-y-auto rounded-xl border border-slate-700/50 bg-slate-900/70 p-3 text-base text-white shadow-xl shadow-black/40 backdrop-blur-md">
      <p className="sticky -top-3 z-10 mb-2 flex items-center gap-2 rounded-lg bg-slate-800/95 px-2 py-1.5 font-semibold shadow-sm backdrop-blur-md">
        <FaLayerGroup className="text-orange-400" /> Layers
      </p>
      <ul className="space-y-0.5">
        {order.map((key, i) => {
          const on = visible[key];
          const legend = on ? legendFor(key) : null;
          return (
            <li key={key}>
              <div
                draggable
                onDragStart={() => { dragIdx.current = i; }}
                onDragOver={(e) => { e.preventDefault(); setOverIdx(i); }}
                onDragLeave={() => setOverIdx((v) => (v === i ? null : v))}
                onDrop={() => drop(i)}
                className={`group flex cursor-grab items-center gap-2 rounded-lg px-1.5 py-1.5 transition-colors duration-150 active:cursor-grabbing hover:bg-slate-700/50 ${overIdx === i ? 'bg-slate-700/60 ring-1 ring-orange-500/40' : ''}`}
              >
                <FaGripVertical
                  title="Drag to reorder"
                  className="shrink-0 text-sm text-slate-400 transition-colors group-hover:text-orange-300"
                />
                <span className={`flex-1 select-none font-semibold ${on ? 'text-white' : 'text-slate-400'}`}>{LABELS[key]}</span>
                <button
                  onClick={() => onToggle(key)}
                  title={on ? 'Hide' : 'Show'}
                  className={`rounded-md p-1 transition-colors duration-150 ${on ? 'text-orange-400 hover:bg-slate-700/70 hover:text-orange-300' : 'text-slate-500 hover:bg-slate-700/70 hover:text-slate-300'}`}
                >
                  {on ? <FaEye /> : <FaEyeSlash />}
                </button>
              </div>
              {legend && (
                <div className="ml-1.5 mt-1 mb-2 rounded-lg bg-slate-800/50 p-2 ring-1 ring-slate-700/50">
                  {legend}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
