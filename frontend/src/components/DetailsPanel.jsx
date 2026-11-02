import {
  FaCircleInfo, FaMountain, FaCloudSun, FaDroplet, FaLeaf, FaSatellite, FaXmark,
} from 'react-icons/fa6';

// Compass label for a wind direction in degrees.
function compass(deg) {
  if (deg == null) return '';
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(deg / 45) % 8];
}

function fmt(ts) {
  return ts ? new Date(ts).toISOString().replace('T', ' ').slice(0, 16) + ' UTC' : '';
}

function num(v, unit = '') {
  return v == null ? '-' : `${Math.round(v * 10) / 10}${unit}`;
}

// Two decimals, for index values like NDVI.
function num2(v) {
  return v == null ? '-' : v.toFixed(2);
}

// A section card: icon + uppercase label, then whatever content is passed in.
function Section({ icon, title, children }) {
  return (
    <div className="mx-3 mt-3 rounded-lg bg-slate-800/60 p-3 ring-1 ring-slate-700/50">
      <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300">
        {icon} {title}
      </p>
      {children}
    </div>
  );
}

// Slide-in panel showing one fire event and its detections.
export default function DetailsPanel({ data, loading, onClose }) {
  const ev = data?.event;
  return (
    <aside className="flex h-full w-80 flex-col border-l border-slate-700 bg-slate-900 text-base text-white shadow-2xl shadow-black/50">
      <div className={`h-1 w-full shrink-0 ${ev?.category === 'wildfire' ? 'bg-gradient-to-r from-red-600 via-orange-500 to-red-600' : 'bg-gradient-to-r from-slate-600 to-slate-700'}`} />
      <header className="flex items-center justify-between border-b border-slate-700 bg-gradient-to-b from-slate-800/60 to-slate-900/95 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold">{ev ? `Fire event #${ev.id}` : 'Fire event'}</span>
          {ev?.category === 'wildfire' && (
            <span className="rounded-full bg-red-600/90 px-2 py-0.5 text-xs font-semibold shadow-sm ring-1 ring-red-400/40">
              Wildfire
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded-full p-1.5 text-slate-400 transition-colors duration-150 hover:bg-slate-700/70 hover:text-white"
        >
          <FaXmark />
        </button>
      </header>

      {loading && (
        <div className="flex items-center gap-2 p-4 text-sm text-slate-300">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-orange-500" />
          Loading event details...
        </div>
      )}

      {ev && (
        <div className="scrollbar-thin flex-1 overflow-y-auto pb-4">
          <Section icon={<FaCircleInfo className="text-orange-400" />} title="Overview">
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-base">
              <dt className="text-slate-300">Detections</dt><dd>{ev.detection_count}</dd>
              <dt className="text-slate-300">Total FRP</dt><dd>{num(ev.frp_sum, ' MW')}</dd>
              <dt className="text-slate-300">Max FRP</dt><dd>{ev.max_frp ?? '-'} MW</dd>
              <dt className="text-slate-300">Status</dt><dd className="capitalize">{ev.status}</dd>
              <dt className="text-slate-300">First</dt><dd>{fmt(ev.first_detected)}</dd>
              <dt className="text-slate-300">Latest</dt><dd>{fmt(ev.last_detected)}</dd>
              <dt className="text-slate-300">Center</dt><dd>{ev.lat.toFixed(3)}, {ev.lon.toFixed(3)}</dd>
            </dl>
          </Section>

          <Section icon={<FaMountain className="text-emerald-400" />} title="Environment">
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-base">
              <dt className="text-slate-300">Land cover</dt>
              <dd>{ev.landcover_label || 'unknown'}</dd>
              <dt className="text-slate-300">Elevation</dt><dd>{num(ev.elevation, ' m')}</dd>
              <dt className="text-slate-300">Slope</dt><dd>{num(ev.slope, ' deg')}</dd>
              <dt className="text-slate-300">Aspect</dt><dd>{num(ev.aspect, ' deg')}</dd>
            </dl>
            {!ev.enriched_at && (
              <p className="mt-2 text-sm text-slate-400">Context not yet enriched for this event.</p>
            )}
          </Section>

          <Section icon={<FaCloudSun className="text-sky-400" />} title="Current weather">
            {ev.weather_time ? (
              <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-base">
                <dt className="text-slate-300">Temp</dt><dd>{num(ev.temp_c, ' C')}</dd>
                <dt className="text-slate-300">Humidity</dt><dd>{num(ev.rh, ' %')}</dd>
                <dt className="text-slate-300">Dew point</dt><dd>{num(ev.dew_point_c, ' C')}</dd>
                <dt className="text-slate-300">Wind</dt><dd>{num(ev.wind_speed_kmh, ' km/h')} {compass(ev.wind_dir_deg)}</dd>
                <dt className="text-slate-300">Gusts</dt><dd>{num(ev.wind_gust_kmh, ' km/h')}</dd>
                <dt className="text-slate-300">Precip</dt><dd>{num(ev.precip_mm, ' mm')}</dd>
              </dl>
            ) : (
              <p className="text-sm text-slate-400">Weather unavailable for this event.</p>
            )}
          </Section>

          <Section icon={<FaDroplet className="text-cyan-400" />} title="Moisture and dryness">
            {ev.weather_time ? (
              <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-base">
                <dt className="text-slate-300">Soil (surface)</dt><dd>{ev.soil_moist_surface == null ? '-' : `${(ev.soil_moist_surface * 100).toFixed(0)} %vol`}</dd>
                <dt className="text-slate-300">Soil (root)</dt><dd>{ev.soil_moist_root == null ? '-' : `${(ev.soil_moist_root * 100).toFixed(0)} %vol`}</dd>
                <dt className="text-slate-300">Soil temp</dt><dd>{num(ev.soil_temp_c, ' C')}</dd>
                <dt className="text-slate-300">VPD</dt><dd>{num(ev.vpd_kpa, ' kPa')}</dd>
              </dl>
            ) : (
              <p className="text-sm text-slate-400">Not available for this event.</p>
            )}
          </Section>

          <Section icon={<FaLeaf className="text-lime-400" />} title="Vegetation (Sentinel-2)">
            {ev.obs_date ? (
              <>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-base">
                  <dt className="text-slate-300">NDVI</dt><dd>{num2(ev.ndvi)}</dd>
                  <dt className="text-slate-300">NDMI</dt><dd>{num2(ev.ndmi)}</dd>
                  <dt className="text-slate-300">NBR</dt><dd>{num2(ev.nbr)}</dd>
                </dl>
                <p className="mt-1 text-sm text-slate-400">Clear scene: {fmt(ev.obs_date).slice(0, 10)}</p>
              </>
            ) : (
              <p className="text-sm text-slate-400">No recent clear Sentinel-2 scene.</p>
            )}
          </Section>

          <Section icon={<FaSatellite className="text-violet-400" />} title={`Detections (${data.detections.length})`}>
            <ul className="space-y-1 text-sm">
              {data.detections.map((d) => (
                <li key={d.id} className="flex justify-between gap-2 rounded-md bg-slate-900/60 px-2 py-1 ring-1 ring-slate-700/40 transition-colors duration-150 hover:ring-slate-500/60">
                  <span className="text-slate-300">{fmt(d.acq_time)}</span>
                  <span className="text-white">{d.satellite} - {(d.confidence || '?').toUpperCase()} - {d.frp ?? '-'} MW</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      )}
    </aside>
  );
}
