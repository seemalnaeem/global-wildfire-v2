import { useState, useEffect } from 'react';
import MapView from './map/MapView.jsx';
import TimeFilter from './components/TimeFilter.jsx';
import LayersControl from './components/LayersControl.jsx';
import DetailsPanel from './components/DetailsPanel.jsx';
import AlertsPanel from './components/AlertsPanel.jsx';
import StatusBar from './components/StatusBar.jsx';
import { DEFAULT_LAYER_ORDER } from './map/layers.js';
import { api } from './lib/api.js';

// Icons come from react-icons only. Styling is Tailwind only.
export default function App() {
  const [time, setTime] = useState({ key: 'all', from: null });
  const [visible, setVisible] = useState({ events: true, detections: true, risk: false, spread: false, landcover: false, ndvi: false, dem: false, smoke: false });
  const [order, setOrder] = useState(DEFAULT_LAYER_ORDER);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [focus, setFocus] = useState(null);

  // Clicking an alert flies the map to it and opens the linked event.
  const onSelectAlert = (a) => {
    setFocus({ lon: a.lon, lat: a.lat, at: Date.now() });
    if (a.event_id != null) setSelectedId(Number(a.event_id));
  };

  useEffect(() => {
    if (selectedId == null) { setDetail(null); return; }
    let active = true;
    setLoading(true);
    api.getEvent(selectedId)
      .then((d) => { if (active) setDetail(d); })
      .catch(() => { if (active) setDetail(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selectedId]);

  const toggle = (key) => setVisible((v) => ({ ...v, [key]: !v[key] }));

  return (
    <div className="flex h-full flex-col bg-slate-950 text-slate-100">
      <header className="relative flex items-center justify-between border-b border-slate-700/80 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 px-5 py-3 shadow-lg shadow-black/30">
        <img
          src="https://i.postimg.cc/dQgn5wHB/ndma-logo.png"
          alt="NDMA"
          className="h-11 w-auto rounded-md bg-white/95 p-1 shadow-sm"
        />
        <h1 className="absolute left-1/2 -translate-x-1/2 text-center text-2xl font-bold tracking-wide text-white sm:text-3xl">
          Global Wildfire Monitoring Portal
        </h1>
        <span className="flex items-center gap-1.5 rounded-full bg-slate-800/80 px-3 py-1 text-xs font-medium text-emerald-400 ring-1 ring-emerald-500/30">
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
          LIVE
        </span>
      </header>

      <div className="relative flex flex-1 overflow-hidden">
        <main className="relative flex-1">
          <MapView timeFrom={time.from} visible={visible} order={order} focus={focus} onSelectEvent={setSelectedId} />
          <div className="absolute left-3 top-3 flex flex-col gap-2">
            <TimeFilter value={time.key} onChange={setTime} />
            <LayersControl visible={visible} order={order} onToggle={toggle} onReorder={setOrder} />
          </div>
          <div className="absolute right-3 top-3">
            <AlertsPanel onSelect={onSelectAlert} />
          </div>
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2">
            <StatusBar />
          </div>
        </main>

        <div
          className={`overflow-hidden transition-all duration-300 ease-in-out ${
            selectedId != null ? 'w-80 opacity-100' : 'w-0 opacity-0'
          }`}
        >
          <DetailsPanel data={detail} loading={loading} onClose={() => setSelectedId(null)} />
        </div>
      </div>
    </div>
  );
}

