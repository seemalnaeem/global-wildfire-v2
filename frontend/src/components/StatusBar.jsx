import { useEffect, useState } from 'react';
import { FaSatelliteDish, FaCloudSun, FaFire, FaBell } from 'react-icons/fa6';
import { api } from '../lib/api.js';

function ago(from, now) {
  if (!from) return 'no data';
  const s = Math.max(0, (new Date(now).getTime() - new Date(from).getTime()) / 1000);
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

function fmt(iso) {
  return iso ? new Date(iso).toISOString().replace('T', ' ').slice(0, 16) + ' UTC' : '-';
}

// Small freshness bar: when the fire data and forecast were last updated, plus live
// counts. Polls every 60s. Turns amber when data is older than 24h (stale).
export default function StatusBar() {
  const [s, setS] = useState(null);

  useEffect(() => {
    let active = true;
    const load = () => api.getStatus().then((d) => { if (active) setS(d); }).catch(() => {});
    load();
    const t = setInterval(load, 60000);
    return () => { active = false; clearInterval(t); };
  }, []);

  if (!s) return null;
  const stale = s.data_updated
    && (new Date(s.server_now).getTime() - new Date(s.data_updated).getTime()) > 86400000;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-700/50 bg-slate-900/70 px-3.5 py-2 text-sm text-white shadow-xl shadow-black/40 backdrop-blur-md">
      <span className="flex items-center gap-1.5" title={`Latest detection: ${fmt(s.data_updated)}`}>
        <FaSatelliteDish className="text-slate-400" />
        <span className={`h-2 w-2 rounded-full ${stale ? 'bg-amber-500' : 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.8)]'}`} />
        Fire data {ago(s.data_updated, s.server_now)}
        {stale && <span className="font-medium text-amber-400">(stale)</span>}
      </span>
      <span className="h-4 w-px bg-slate-600/80" />
      <span className="flex items-center gap-1.5" title={`Forecast issued: ${fmt(s.forecast_issued)}`}>
        <FaCloudSun className="text-slate-400" /> Forecast {ago(s.forecast_issued, s.server_now)}
      </span>
      <span className="h-4 w-px bg-slate-600/80" />
      <span className="flex items-center gap-1.5">
        <FaFire className="text-orange-400" /> {s.wildfires.toLocaleString()} wildfires
      </span>
      <span className="h-4 w-px bg-slate-600/80" />
      <span className="flex items-center gap-1.5">
        <FaBell className="text-slate-400" /> {s.alerts_active} alerts
      </span>
    </div>
  );
}
