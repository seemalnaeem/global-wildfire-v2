import { FaClock } from 'react-icons/fa6';

// Time window options. 'from' is computed relative to now when selected.
const OPTIONS = [
  { key: '24h', label: '24h', hours: 24 },
  { key: '48h', label: '48h', hours: 48 },
  { key: '72h', label: '72h', hours: 72 },
  { key: 'all', label: 'All', hours: null },
];

export default function TimeFilter({ value, onChange }) {
  function pick(opt) {
    const from = opt.hours ? new Date(Date.now() - opt.hours * 3600 * 1000).toISOString() : null;
    onChange({ key: opt.key, from });
  }

  return (
    <div className="flex items-center gap-1 rounded-xl border border-slate-700/50 bg-slate-900/70 p-1 text-base shadow-xl shadow-black/40 backdrop-blur-md">
      <FaClock className="mx-1.5 text-slate-300" />
      {OPTIONS.map((opt) => (
        <button
          key={opt.key}
          onClick={() => pick(opt)}
          className={`rounded-lg px-2.5 py-1 font-medium transition-colors duration-150 ${
            value === opt.key
              ? 'bg-orange-600 text-white shadow-sm shadow-orange-900/50'
              : 'text-slate-200 hover:bg-slate-700/70 hover:text-white'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
