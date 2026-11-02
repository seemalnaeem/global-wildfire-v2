import { useEffect, useState } from 'react';
import { FaBell, FaTriangleExclamation, FaCircleInfo } from 'react-icons/fa6';
import { api } from '../lib/api.js';

const SEVERITY = {
  critical: {
    icon: FaTriangleExclamation, iconWrap: 'bg-red-500/15 ring-1 ring-red-500/30 text-red-400',
    text: 'text-red-400', badge: 'bg-red-500/15 ring-1 ring-red-500/30', label: 'Critical',
  },
  warning: {
    icon: FaTriangleExclamation, iconWrap: 'bg-amber-500/15 ring-1 ring-amber-500/30 text-amber-400',
    text: 'text-amber-400', badge: 'bg-amber-500/15 ring-1 ring-amber-500/30', label: 'Warning',
  },
  info: {
    icon: FaCircleInfo, iconWrap: 'bg-sky-500/15 ring-1 ring-sky-500/30 text-sky-400',
    text: 'text-sky-400', badge: 'bg-sky-500/15 ring-1 ring-sky-500/30', label: 'Info',
  },
};

function timeAgo(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

// Notifications bell with an alert list. Polls the backend; clicking an alert flies
// the map to it (and opens the event). Self-contained, in-app only.
export default function AlertsPanel({ onSelect }) {
  const [alerts, setAlerts] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let active = true;
    const load = () => api.listAlerts().then((d) => { if (active) setAlerts(d.alerts || []); }).catch(() => {});
    load();
    const t = setInterval(load, 60000);  // refresh every minute
    return () => { active = false; clearInterval(t); };
  }, []);

  const critical = alerts.filter((a) => a.severity === 'critical').length;

  return (
    <div className="w-64">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-xl border border-slate-700/50 bg-slate-900/70 px-3 py-2 text-base font-semibold text-white shadow-xl shadow-black/40 backdrop-blur-md transition-colors duration-150 hover:border-slate-600"
      >
        <span className="relative flex items-center">
          <FaBell className="text-orange-400" />
          {critical > 0 && (
            <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
          )}
        </span>
        Alerts
        {alerts.length > 0 && (
          <span className={`ml-auto rounded-full px-1.5 text-sm font-semibold text-white shadow-sm ${critical ? 'bg-red-600' : 'bg-amber-600'}`}>
            {alerts.length}
          </span>
        )}
      </button>

      {open && (
        <div className="animate-fade-in-down mt-1.5 overflow-hidden rounded-xl border border-slate-700/50 bg-slate-900/90 shadow-xl shadow-black/40 backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-slate-700/60 px-3 py-2">
            <span className="text-sm font-semibold text-white">Active alerts</span>
            <span className="text-xs text-slate-400">{alerts.length} total</span>
          </div>

          {alerts.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-slate-400">No active alerts.</p>
          ) : (
            <ul className="scrollbar-thin max-h-[80vh] divide-y divide-slate-700/40 overflow-y-auto">
              {alerts.map((a) => {
                const sev = SEVERITY[a.severity] || SEVERITY.info;
                const Icon = sev.icon;
                return (
                  <li key={a.id}>
                    <button
                      onClick={() => onSelect(a)}
                      className="flex w-full gap-2.5 px-3 py-2.5 text-left transition-colors duration-150 hover:bg-slate-700/40"
                    >
                      <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm ${sev.iconWrap}`}>
                        <Icon />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate font-medium text-white">{a.title}</span>
                          <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${sev.text} ${sev.badge}`}>{sev.label}</span>
                        </span>
                        <span className="mt-0.5 block line-clamp-2 break-words text-sm leading-tight text-slate-300">{a.message}</span>
                        <span className="mt-1 block text-xs text-slate-500">{timeAgo(a.updated_at)}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
